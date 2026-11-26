from base64 import b64decode
from binascii import Error
from email.message import EmailMessage
from logging import getLogger

import aiosmtplib
from fastapi import HTTPException
from httpx import AsyncClient, RequestError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.infrastructure.mail import send_smtp_message

from .schemas import ReniecRecord, SendEmail

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
logger = getLogger(__name__)
SCRALL_ACCOUNT_ERRORS = {
    "you dont have enough queries": "La cuenta de Scrall no tiene créditos para esta consulta.",
    "not authorized for this information": "La clave de Scrall no tiene acceso a RENIEC Básico.",
    "plan not allowed": "El plan de Scrall no tiene acceso a RENIEC Básico.",
    "key deactivated": "La clave de Scrall está desactivada.",
    "unverified user": "La cuenta de Scrall todavía no está verificada.",
    "banned user": "La cuenta de Scrall está suspendida.",
}


def decode_attachment(value: str) -> bytes:
    if value.startswith("data:"):
        header, separator, value = value.partition(",")
        if not separator or not header.endswith(";base64"):
            raise HTTPException(422, "La URL de datos del adjunto debe usar base64.")
    if len(value) > 4 * ((MAX_ATTACHMENT_BYTES + 2) // 3):
        raise HTTPException(413, "El adjunto supera los 10 MiB.")
    try:
        content = b64decode(value, validate=True)
    except (Error, ValueError) as exc:
        raise HTTPException(422, "El adjunto debe estar codificado en base64 válido.") from exc
    if not content:
        raise HTTPException(422, "El adjunto está vacío.")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(413, "El adjunto supera los 10 MiB.")
    return content


async def deliver_email(data: SendEmail) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from_email:
        raise HTTPException(503, "El envío de correo no está configurado.")
    message = EmailMessage()
    message["From"] = str(settings.smtp_from_email)
    message["To"] = data.email
    message["Subject"] = data.asunto
    message.set_content(data.mensaje)
    if data.archivo is not None:
        content = await run_in_threadpool(decode_attachment, data.archivo)
        subtype, filename = (
            ("pdf", "adjunto.pdf")
            if content.startswith(b"%PDF-")
            else ("octet-stream", "adjunto.bin")
        )
        message.add_attachment(content, maintype="application", subtype=subtype, filename=filename)
    try:
        await send_smtp_message(message)
    except (aiosmtplib.SMTPException, OSError, TimeoutError):
        raise HTTPException(502, "El servidor SMTP no confirmó el envío.") from None


async def consult_reniec(dni: str) -> ReniecRecord:
    settings = get_settings()
    token = settings.token_reniec.get_secret_value().strip() if settings.token_reniec else ""
    scheme, _, credentials = token.partition(" ")
    if scheme.lower() == "basic":
        token = credentials.strip()
    if not token or settings.reniec_api_url.scheme != "https":
        raise HTTPException(503, "La consulta RENIEC no está configurada.")
    try:
        async with AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.post(
                str(settings.reniec_api_url),
                headers={"Authorization": f"Basic {token}", "Accept": "application/json"},
                json={"dni": dni},
            )
    except RequestError as exc:
        logger.warning("Falló la conexión con Scrall: %s.", type(exc).__name__)
        raise HTTPException(502, "No se pudo consultar el servicio RENIEC.") from None
    if response.status_code == 404:
        raise NotFoundError("DNI no encontrado.")
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "")
        headers = (
            {"Retry-After": retry_after}
            if retry_after.isascii() and retry_after.isdecimal()
            else None
        )
        raise HTTPException(429, "Se alcanzó el límite de consultas RENIEC.", headers=headers)
    if response.status_code in (401, 403):
        raise HTTPException(503, "Scrall rechazó la clave configurada o su acceso a RENIEC Básico.")
    if response.status_code != 200:
        logger.warning(
            "Scrall no completó la consulta RENIEC. Estado HTTP %s.", response.status_code
        )
        raise HTTPException(502, "El servicio RENIEC no pudo completar la consulta.")
    try:
        body = response.json()
    except ValueError:
        logger.warning("Scrall devolvió una respuesta RENIEC que no es JSON.")
        raise HTTPException(502, "Scrall devolvió una respuesta que no es JSON.") from None
    if not isinstance(body, dict):
        logger.warning("Scrall devolvió una respuesta RENIEC que no es un objeto JSON.")
        raise HTTPException(502, "Scrall devolvió un JSON que no es un objeto.")

    message = str(body.get("message", "")).strip().lower()
    if message == "not found data":
        raise NotFoundError("DNI no encontrado.")
    if message in SCRALL_ACCOUNT_ERRORS:
        raise HTTPException(503, SCRALL_ACCOUNT_ERRORS[message])
    if message == "internal error":
        logger.warning("Scrall informó un error interno durante la consulta RENIEC.")
        raise HTTPException(502, "Scrall informó un error interno durante la consulta RENIEC.")
    result = body.get("result")
    if not isinstance(result, dict):
        logger.warning("Scrall no devolvió un objeto en el campo result.")
        raise HTTPException(502, "Scrall no devolvió un registro RENIEC en el campo result.")
    try:
        record = ReniecRecord.model_validate(result)
    except ValidationError as exc:
        fields = [error["loc"] for error in exc.errors(include_input=False)]
        logger.warning("Respuesta RENIEC inválida de Scrall. Campos rechazados: %s.", fields)
        raise HTTPException(502, "Scrall devolvió un registro RENIEC con campos inválidos.") from None
    if record.nuDni != dni:
        logger.warning("Scrall devolvió un DNI diferente al consultado.")
        raise HTTPException(502, "El resultado RENIEC no corresponde al DNI consultado.")
    return record
