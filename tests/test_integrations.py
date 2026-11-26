import json
from base64 import b64encode

import pytest
from httpx import AsyncClient, MockTransport, Response
from pydantic import SecretStr

from app.core.config import get_settings
from app.modules.integrations import service


async def test_send_email_with_base64_attachment(client, admin_headers, monkeypatch):
    settings = get_settings().model_copy(
        update={"smtp_host": "smtp.example.com", "smtp_from_email": "hotel@example.com"}
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    messages = []

    async def send(message):
        messages.append(message)

    monkeypatch.setattr(service, "send_smtp_message", send)
    path = "/api/v1/integrations/email"
    body = {"email": "demo@example.com", "asunto": "Reserva", "mensaje": "Tu reserva está lista."}
    assert (await client.post(path, json=body)).status_code == 401
    assert (
        await client.post(path, headers=admin_headers, json={**body, "archivo": "%%%INVALIDO"})
    ).status_code == 422
    pdf = b"%PDF-1.7\n%%EOF"
    response = await client.post(
        path, headers=admin_headers, json={**body, "archivo": b64encode(pdf).decode()}
    )
    assert response.status_code == 200, response.text
    [message] = messages
    assert message["To"] == body["email"]
    assert message["Subject"] == body["asunto"]
    [attachment] = message.iter_attachments()
    assert attachment.get_payload(decode=True) == pdf


@pytest.mark.parametrize("token", ["clave-de-prueba", "Basic clave-de-prueba"])
async def test_reniec_basic_uses_scrall_and_returns_only_success_data(
    client, admin_headers, monkeypatch, token
):
    settings = get_settings().model_copy(update={"token_reniec": SecretStr(token)})
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    upstream = None

    def scrall(request):
        assert request.method == "POST"
        assert str(request.url) == str(settings.reniec_api_url)
        assert request.headers["authorization"] == "Basic clave-de-prueba"
        assert request.headers["accept"] == "application/json"
        assert json.loads(request.content) == {"dni": "01234567"}
        if upstream is not None:
            return upstream
        return Response(
            200,
            json={
                "message": "found data",
                "result": {
                    "nuDni": "01234567",
                    "preNombres": "PERSONA DE PRUEBA",
                    "extra": "oculto",
                },
            },
        )

    monkeypatch.setattr(
        service,
        "AsyncClient",
        lambda **kwargs: AsyncClient(transport=MockTransport(scrall), **kwargs),
    )
    path = "/api/v1/integrations/reniec"
    assert (await client.post(path, json={"dni": "01234567"})).status_code == 401
    assert (await client.post(path, headers=admin_headers, json={"dni": "123"})).status_code == 422
    response = await client.post(path, headers=admin_headers, json={"dni": "01234567"})
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert set(payload) == {"success", "data"}
    assert payload["success"] is True
    assert payload["data"]["nuDni"] == "01234567"
    assert "extra" not in payload["data"]

    upstream = Response(
        200,
        json={
            "message": "found data",
            "result": {
                "D_NUDNI": 1234567,
                "D_PRENOMBRES": "PERSONA DE PRUEBA",
                "D_APEPATERNO": "EJEMPLO",
                "D_APEMATERNO": "PRUEBA",
                "D_FENACIMIENTO": "1990-05-15",
                "D_DIGITOVERIFICACION": 5,
            },
        },
    )
    response = await client.post(path, headers=admin_headers, json={"dni": "01234567"})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": True,
        "data": {
            "nuDni": "01234567",
            "preNombres": "PERSONA DE PRUEBA",
            "apePaterno": "EJEMPLO",
            "apeMaterno": "PRUEBA",
            "feNacimiento": "1990-05-15",
            "digitoVerificacion": "5",
        },
    }

    for status, message, expected_status, expected_text in (
        (200, "not found data", 404, "DNI no encontrado"),
        (200, "you dont have enough queries", 503, "no tiene créditos"),
        (200, "plan not allowed", 503, "plan de Scrall"),
        (200, "key deactivated", 503, "desactivada"),
        (401, "Unauthorized", 503, "rechazó la clave"),
        (200, "internal error", 502, "error interno"),
    ):
        upstream = Response(status, json={"message": message, "result": None})
        response = await client.post(path, headers=admin_headers, json={"dni": "01234567"})
        assert response.status_code == expected_status
        assert expected_text in response.json()["message"]
