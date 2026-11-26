from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import selectinload, undefer
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import DbSession
from app.core.document_types import DocumentType
from app.core.exceptions import NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions
from app.modules.rooms.images import convert_photo_to_webp

from .choices import ComplaintType, MediaType, WebsiteCategory
from .models import (
    WebsiteComplaint,
    WebsiteContact,
    WebsiteDescription,
    WebsiteGallery,
    WebsiteGalleryImage,
    WebsiteMedia,
)
from .schemas import (
    ComplaintCreate,
    ComplaintRead,
    ContactCreate,
    ContactRead,
    DescriptionRead,
    DescriptionWrite,
    GalleryCreate,
    GalleryImageRead,
    GalleryRead,
    MediaRead,
    PDFCreate,
    SubmissionRead,
    VideoCreate,
    WebsiteChoicesRead,
)
from .uploads import decode_media

router = APIRouter(prefix="/website", tags=["Website"])
WEBSITE_PATH = "/api/v1/website"
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def media_read(media: WebsiteMedia) -> MediaRead:
    return MediaRead(
        id=media.id,
        kind=media.kind,
        title=media.title,
        created_at=media.created_at,
        url=f"{WEBSITE_PATH}/media/{media.id}",
    )


def image_read(image: WebsiteGalleryImage) -> GalleryImageRead:
    return GalleryImageRead(
        id=image.id,
        image=f"{WEBSITE_PATH}/galleries/{image.gallery_id}/images/{image.id}",
    )


def gallery_read(gallery: WebsiteGallery) -> GalleryRead:
    return GalleryRead(
        id=gallery.id,
        category=gallery.category,
        description=gallery.description,
        is_active=gallery.is_active,
        created_at=gallery.created_at,
        images=[image_read(image) for image in gallery.images],
    )


async def save_media(session: DbSession, kind: MediaType, title: str, encoded: str) -> MediaRead:
    content, content_type = await run_in_threadpool(decode_media, encoded, kind)
    media = WebsiteMedia(kind=kind, title=title, content_type=content_type, content=content)
    session.add(media)
    await session.commit()
    return media_read(media)


@router.get(
    "/choices",
    summary="Consultar opciones del sitio web",
    response_model=ApiResponse[WebsiteChoicesRead],
)
async def list_website_choices():
    return ApiResponse[WebsiteChoicesRead](
        data=WebsiteChoicesRead(
            categories=WebsiteCategory.choices(),
            document_types=DocumentType.choices(),
            request_types=ComplaintType.choices(),
        )
    )


@router.get("/media", summary="Listar videos y PDF", response_model=ApiResponse[list[MediaRead]])
async def list_website_media(session: DbSession, kind: MediaType | None = None):
    query = select(WebsiteMedia).order_by(WebsiteMedia.created_at.desc(), WebsiteMedia.id)
    if kind is not None:
        query = query.where(WebsiteMedia.kind == kind)
    media = await session.scalars(query)
    return ApiResponse[list[MediaRead]](data=[media_read(item) for item in media])


@router.get("/media/{media_id}", summary="Obtener archivo del sitio web", response_class=Response)
async def download_website_media(media_id: UUID, session: DbSession):
    media = await session.get(WebsiteMedia, media_id, options=[undefer(WebsiteMedia.content)])
    if media is None:
        raise NotFoundError("Archivo no encontrado.")
    headers = {"X-Content-Type-Options": "nosniff"}
    if media.kind == MediaType.PDF:
        headers["Content-Disposition"] = f'attachment; filename="{media.id}.pdf"'
    return Response(media.content, media_type=media.content_type, headers=headers)


@router.post(
    "/videos",
    summary="Publicar video en el sitio web",
    response_model=ApiResponse[MediaRead],
    status_code=201,
    dependencies=[Depends(require_permissions("website_media.create"))],
)
async def create_website_video(data: VideoCreate, session: DbSession):
    return ApiResponse[MediaRead](
        data=await save_media(session, MediaType.VIDEO, data.title, data.video)
    )


@router.post(
    "/pdfs",
    summary="Publicar PDF en el sitio web",
    response_model=ApiResponse[MediaRead],
    status_code=201,
    dependencies=[Depends(require_permissions("website_media.create"))],
)
async def create_website_pdf(data: PDFCreate, session: DbSession):
    return ApiResponse[MediaRead](
        data=await save_media(session, MediaType.PDF, data.title, data.pdf)
    )


@router.get(
    "/galleries",
    summary="Listar galerías publicadas",
    response_model=ApiResponse[list[GalleryRead]],
)
async def list_website_galleries(session: DbSession, category: WebsiteCategory | None = None):
    query = (
        select(WebsiteGallery)
        .options(selectinload(WebsiteGallery.images))
        .where(WebsiteGallery.is_active)
        .order_by(WebsiteGallery.created_at.desc(), WebsiteGallery.id)
    )
    if category is not None:
        query = query.where(WebsiteGallery.category == category)
    galleries = await session.scalars(query)
    return ApiResponse[list[GalleryRead]](data=[gallery_read(gallery) for gallery in galleries])


@router.post(
    "/galleries",
    summary="Crear galería de fotos",
    response_model=ApiResponse[GalleryRead],
    status_code=201,
    dependencies=[Depends(require_permissions("website_galleries.create"))],
)
async def create_website_gallery(data: GalleryCreate, session: DbSession):
    gallery = WebsiteGallery(**data.model_dump(), images=[])
    session.add(gallery)
    await session.commit()
    return ApiResponse[GalleryRead](data=gallery_read(gallery))


@router.put(
    "/galleries/{gallery_id}",
    summary="Actualizar galería de fotos",
    response_model=ApiResponse[GalleryRead],
    dependencies=[Depends(require_permissions("website_galleries.update"))],
)
async def update_website_gallery(gallery_id: UUID, data: GalleryCreate, session: DbSession):
    gallery = await session.get(
        WebsiteGallery, gallery_id, options=[selectinload(WebsiteGallery.images)]
    )
    if gallery is None:
        raise NotFoundError("Galería no encontrada.")
    for field, value in data.model_dump().items():
        setattr(gallery, field, value)
    await session.commit()
    return ApiResponse[GalleryRead](data=gallery_read(gallery))


@router.post(
    "/galleries/{gallery_id}/images",
    summary="Subir foto a una galería",
    response_model=ApiResponse[GalleryImageRead],
    status_code=201,
    dependencies=[Depends(require_permissions("website_galleries.update"))],
)
async def upload_website_gallery_image(gallery_id: UUID, file: UploadFile, session: DbSession):
    if await session.get(WebsiteGallery, gallery_id) is None:
        raise NotFoundError("Galería no encontrada.")
    original = await file.read(MAX_IMAGE_BYTES + 1)
    if len(original) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "La foto supera los 5 MiB.")
    content = await run_in_threadpool(convert_photo_to_webp, original)
    image = WebsiteGalleryImage(gallery_id=gallery_id, content=content)
    session.add(image)
    await session.commit()
    return ApiResponse[GalleryImageRead](data=image_read(image))


@router.get(
    "/galleries/{gallery_id}/images/{image_id}",
    summary="Ver foto de una galería",
    response_class=Response,
)
async def view_website_gallery_image(gallery_id: UUID, image_id: UUID, session: DbSession):
    image = await session.scalar(
        select(WebsiteGalleryImage)
        .join(WebsiteGallery)
        .options(undefer(WebsiteGalleryImage.content))
        .where(
            WebsiteGallery.id == gallery_id,
            WebsiteGallery.is_active,
            WebsiteGalleryImage.id == image_id,
        )
    )
    if image is None:
        raise NotFoundError("Foto no encontrada.")
    return Response(
        image.content,
        media_type="image/webp",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )


@router.get(
    "/descriptions",
    summary="Consultar descripciones del sitio web",
    response_model=ApiResponse[list[DescriptionRead]],
)
async def list_website_descriptions(session: DbSession, category: WebsiteCategory | None = None):
    query = select(WebsiteDescription).order_by(WebsiteDescription.category)
    if category is not None:
        query = query.where(WebsiteDescription.category == category)
    descriptions = await session.scalars(query)
    return ApiResponse[list[DescriptionRead]](
        data=[DescriptionRead.model_validate(item) for item in descriptions]
    )


@router.put(
    "/descriptions/{category}",
    summary="Guardar descripción de una sección web",
    response_model=ApiResponse[DescriptionRead],
    dependencies=[Depends(require_permissions("website_descriptions.update"))],
)
async def save_website_description(
    category: WebsiteCategory, data: DescriptionWrite, session: DbSession
):
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    await session.execute(
        insert(WebsiteDescription)
        .values(category=category, description=data.description)
        .on_conflict_do_update(
            index_elements=[WebsiteDescription.category],
            set_={"description": data.description, "updated_at": func.now()},
        )
    )
    await session.commit()
    return ApiResponse[DescriptionRead](
        data=DescriptionRead(category=category, description=data.description)
    )


async def submit_form(session: DbSession, submission: WebsiteComplaint | WebsiteContact):
    session.add(submission)
    await session.commit()
    return ApiResponse[SubmissionRead](data=SubmissionRead.model_validate(submission))


@router.post(
    "/complaints",
    summary="Registrar una queja o reclamo",
    status_code=201,
    response_model=ApiResponse[SubmissionRead],
)
async def submit_website_complaint(data: ComplaintCreate, session: DbSession):
    return await submit_form(session, WebsiteComplaint(**data.model_dump()))


@router.post(
    "/contacts",
    summary="Enviar mensaje de contacto",
    status_code=201,
    response_model=ApiResponse[SubmissionRead],
)
async def submit_website_contact(data: ContactCreate, session: DbSession):
    return await submit_form(session, WebsiteContact(**data.model_dump()))


async def list_submissions(session: DbSession, model, schema, pagination):
    total = await session.scalar(select(func.count()).select_from(model))
    submissions = await session.scalars(
        select(model)
        .order_by(model.created_at.desc(), model.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return Page[schema].build(
        [schema.model_validate(item) for item in submissions], total or 0, pagination
    )


@router.get(
    "/complaints",
    summary="Listar quejas y reclamos",
    response_model=ApiResponse[Page[ComplaintRead]],
    dependencies=[Depends(require_permissions("website_complaints.read"))],
)
async def list_website_complaints(session: DbSession, pagination: Pagination):
    return ApiResponse[Page[ComplaintRead]](
        data=await list_submissions(session, WebsiteComplaint, ComplaintRead, pagination)
    )


@router.get(
    "/contacts",
    summary="Listar mensajes de contacto",
    response_model=ApiResponse[Page[ContactRead]],
    dependencies=[Depends(require_permissions("website_contacts.read"))],
)
async def list_website_contacts(session: DbSession, pagination: Pagination):
    return ApiResponse[Page[ContactRead]](
        data=await list_submissions(session, WebsiteContact, ContactRead, pagination)
    )
