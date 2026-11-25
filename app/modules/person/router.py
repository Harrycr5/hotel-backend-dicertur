from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.api.dependencies import DbSession
from app.core.document_types import DocumentType
from app.core.exceptions import NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions

from .choices import PersonArea, PersonCategory, PersonGender
from .models import Customer, Person
from .schemas import (
    ChoiceRead,
    CustomerRead,
    PersonChoicesRead,
    PersonCreate,
    PersonRead,
    PersonUpdate,
)

router = APIRouter()
persons_router = APIRouter(
    prefix="/persons",
    tags=["Persons"],
)
customers_router = APIRouter(prefix="/customers", tags=["Customers"])


@customers_router.get(
    "",
    summary="Listar clientes",
    response_model=ApiResponse[Page[CustomerRead]],
    dependencies=[Depends(require_permissions("customers.read"))],
)
async def list_customers(session: DbSession, pagination: Pagination):
    total = await session.scalar(select(func.count()).select_from(Customer))
    customers = await session.scalars(
        select(Customer)
        .order_by(Customer.last_name, Customer.name, Customer.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[CustomerRead]](
        message="Clientes obtenidos correctamente.",
        data=Page[CustomerRead].build(
            [CustomerRead.model_validate(customer) for customer in customers],
            total or 0,
            pagination,
        ),
    )


async def get_person_or_404(person_id: UUID, session: DbSession) -> Person:
    person = await session.get(Person, person_id)
    if person is None:
        raise NotFoundError("Persona no encontrada.")
    return person


@persons_router.get(
    "/choices",
    summary="Consultar opciones para el registro de personas",
    response_model=ApiResponse[PersonChoicesRead],
    dependencies=[Depends(require_permissions("persons.read"))],
)
async def get_choices():
    return ApiResponse[PersonChoicesRead](
        message="Opciones obtenidas correctamente.",
        data=PersonChoicesRead(
            document_types=[ChoiceRead(**choice) for choice in DocumentType.choices()],
            areas=[ChoiceRead(value=area.value, label=area.value) for area in PersonArea],
            genders=[ChoiceRead(**choice) for choice in PersonGender.choices()],
            categories=[
                ChoiceRead(value=category.value, label=category.value)
                for category in PersonCategory
            ],
        ),
    )


@persons_router.get(
    "",
    summary="Listar personas",
    response_model=ApiResponse[Page[PersonRead]],
    dependencies=[Depends(require_permissions("persons.read"))],
)
async def list_persons(session: DbSession, pagination: Pagination):
    total = await session.scalar(select(func.count()).select_from(Person))
    persons = await session.scalars(
        select(Person)
        .order_by(Person.last_name, Person.name, Person.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[PersonRead]](
        message="Personas obtenidas correctamente.",
        data=Page[PersonRead].build(
            [PersonRead.model_validate(person) for person in persons], total or 0, pagination
        ),
    )


@persons_router.post(
    "",
    summary="Crear persona",
    response_model=ApiResponse[PersonRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("persons.create"))],
)
async def create_person(data: PersonCreate, session: DbSession):
    person = Person(**data.model_dump())
    session.add(person)
    await session.commit()
    await session.refresh(person)
    return ApiResponse[PersonRead](
        message="Persona creada correctamente.", data=PersonRead.model_validate(person)
    )


@persons_router.get(
    "/{person_id}",
    summary="Consultar persona",
    response_model=ApiResponse[PersonRead],
    dependencies=[Depends(require_permissions("persons.read"))],
)
async def get_person(person_id: UUID, session: DbSession):
    person = await get_person_or_404(person_id, session)
    return ApiResponse[PersonRead](
        message="Persona obtenida correctamente.", data=PersonRead.model_validate(person)
    )


@persons_router.patch(
    "/{person_id}",
    summary="Actualizar persona",
    response_model=ApiResponse[PersonRead],
    dependencies=[Depends(require_permissions("persons.update"))],
)
async def update_person(person_id: UUID, data: PersonUpdate, session: DbSession):
    person = await get_person_or_404(person_id, session)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(person, field, value)
    await session.commit()
    await session.refresh(person)
    return ApiResponse[PersonRead](
        message="Persona actualizada correctamente.", data=PersonRead.model_validate(person)
    )


@persons_router.delete(
    "/{person_id}",
    summary="Eliminar persona",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("persons.delete"))],
)
async def delete_person(person_id: UUID, session: DbSession) -> None:
    person = await get_person_or_404(person_id, session)
    await session.delete(person)
    await session.commit()


router.include_router(persons_router)
router.include_router(customers_router)
