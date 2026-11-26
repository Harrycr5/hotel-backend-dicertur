from base64 import b64decode
from binascii import Error

from fastapi import HTTPException

from .choices import MediaType

MAX_MEDIA_BYTES = {MediaType.VIDEO: 20 * 1024 * 1024, MediaType.PDF: 10 * 1024 * 1024}


def decode_media(encoded: str, kind: MediaType) -> tuple[bytes, str]:
    declared_type = None
    if encoded.startswith("data:"):
        header, separator, encoded = encoded.partition(",")
        if not separator or not header.endswith(";base64"):
            raise HTTPException(422, "La URL de datos debe usar base64.")
        declared_type = header[5:-7]
    limit = MAX_MEDIA_BYTES[kind]
    if len(encoded) > 4 * ((limit + 2) // 3):
        raise HTTPException(413, "El archivo supera el tamaño permitido.")
    try:
        content = b64decode(encoded, validate=True)
    except (Error, ValueError) as exc:
        raise HTTPException(422, "El archivo debe estar codificado en base64 válido.") from exc
    if len(content) > limit:
        raise HTTPException(413, "El archivo supera el tamaño permitido.")

    if (
        kind == MediaType.PDF
        and content.startswith(b"%PDF-")
        and content.rstrip().endswith(b"%%EOF")
    ):
        content_type = "application/pdf"
    elif kind == MediaType.VIDEO and content[4:8] == b"ftyp" and len(content) >= 16:
        content_type = "video/mp4"
    elif (
        kind == MediaType.VIDEO
        and content.startswith(b"\x1a\x45\xdf\xa3")
        and b"\x42\x82\x84webm" in content[:256]
    ):
        content_type = "video/webm"
    else:
        raise HTTPException(415, "Formato de archivo no compatible.")
    if declared_type and declared_type != content_type:
        raise HTTPException(415, "El tipo declarado no coincide con el archivo.")
    return content, content_type
