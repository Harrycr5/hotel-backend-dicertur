from io import BytesIO

from fastapi import HTTPException, status
from PIL import Image, ImageOps

PHOTO_FORMATS = ("JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF", "AVIF")
MAX_INPUT_PIXELS = 24_000_000
MAX_OUTPUT_DIMENSIONS = (1920, 1920)


def convert_photo_to_webp(content: bytes) -> bytes:
    with BytesIO() as output:
        try:
            with Image.open(BytesIO(content), formats=PHOTO_FORMATS) as source:
                if source.width * source.height > MAX_INPUT_PIXELS:
                    raise Image.DecompressionBombError("Image exceeds the photo pixel limit")
                photo = ImageOps.exif_transpose(source)
                mode = "RGBA" if photo.has_transparency_data else "RGB"
                with photo, photo.convert(mode) as normalized:
                    normalized.thumbnail(MAX_OUTPUT_DIMENSIONS, Image.Resampling.LANCZOS)
                    normalized.save(output, format="WEBP", quality=82)
        except Image.DecompressionBombError as exc:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "La foto supera los 24 megapíxeles."
            ) from exc
        except (OSError, ValueError, SyntaxError) as exc:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                "Usa una imagen válida en JPEG, PNG, WebP, GIF, BMP, TIFF o AVIF.",
            ) from exc
        return output.getvalue()
