from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.dependencies import DbSession
from app.core.document_types import DocumentType
from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions
from app.modules.companies.models import Branch
from app.modules.reservations.schemas import PERU_TIME

from .choices import PersonArea, PersonCategory, PersonGender
from .models import Customer, Person, PersonAssignment
from .schemas import (
    ChoiceRead,
    CustomerRead,
    PersonAssignmentRead,
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
ASSIGNMENT_FIELDS = ("branch_id", "area", "category", "is_permanent_employee")


async def validate_branch(session: DbSession, branch_id: UUID | None) -> None:
    if branch_id is not None and await session.get(Branch, branch_id) is None:
        raise NotFoundError("Sucursal no encontrada.")


def validate_employment_dates(start: date, end: date | None) -> None:
    if end is not None and end < start:
        raise AppError("La fecha de baja debe ser igual o posterior a la fecha de ingreso.")


def assignment_values(person: Person) -> dict:
    return {name: getattr(person, name) for name in ASSIGNMENT_FIELDS}


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
    start = data.employment_start_date or datetime.now(PERU_TIME).date()
    validate_employment_dates(start, data.employment_end_date)
    await validate_branch(session, data.branch_id)
    values = data.model_dump(exclude={"employment_start_date"})
    person = Person(**values, employment_start_date=start)
    person.assignments = [PersonAssignment(effective_from=start, **assignment_values(person))]
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
    person = await session.scalar(
        select(Person)
        .where(Person.id == person_id)
        .options(selectinload(Person.assignments))
        .with_for_update()
    )
    if person is None:
        raise NotFoundError("Persona no encontrada.")
    changes = data.model_dump(exclude_unset=True, exclude={"assignment_effective_from"})
    start = changes.get("employment_start_date", person.labor_start)
    end = changes.get("employment_end_date", person.employment_end_date)
    validate_employment_dates(start, end)
    if "branch_id" in changes:
        await validate_branch(session, changes["branch_id"])

    if not person.assignments:
        person.assignments.append(
            PersonAssignment(effective_from=start, **assignment_values(person))
        )
    first, *later = person.assignments
    if "employment_start_date" in changes:
        if later and start >= later[0].effective_from:
            raise ConflictError(
                "La fecha de ingreso debe ser anterior al primer cambio de asignación."
            )
        first.effective_from = start
    latest = person.assignments[-1]
    today = datetime.now(PERU_TIME).date()
    assignment_changed = any(
        name in changes and changes[name] != getattr(person, name) for name in ASSIGNMENT_FIELDS
    )
    if data.assignment_effective_from is not None and not assignment_changed:
        raise AppError(
            "Indica un cambio de sucursal, área o condición para usar la fecha de asignación."
        )
    effective = data.assignment_effective_from or max(today, start)
    if assignment_changed and (
        effective < latest.effective_from or (effective > today and effective != start)
    ):
        raise ConflictError(
            "La fecha del cambio debe seguir al historial y no puede programarse a futuro."
        )
    last_effective = effective if assignment_changed else latest.effective_from
    if end is not None and end < last_effective:
        raise ConflictError("La fecha de baja no puede ser anterior a la última asignación.")

    for field, value in changes.items():
        setattr(person, field, value)
    if assignment_changed:
        if effective == latest.effective_from:
            for field, value in assignment_values(person).items():
                setattr(latest, field, value)
        else:
            person.assignments.append(
                PersonAssignment(effective_from=effective, **assignment_values(person))
            )
    await session.commit()
    await session.refresh(person)
    return ApiResponse[PersonRead](
        message="Persona actualizada correctamente.", data=PersonRead.model_validate(person)
    )


@persons_router.get(
    "/{person_id}/assignments",
    summary="Consultar historial de asignaciones del personal",
    response_model=ApiResponse[list[PersonAssignmentRead]],
    dependencies=[Depends(require_permissions("persons.read"))],
)
async def list_person_assignments(person_id: UUID, session: DbSession):
    await get_person_or_404(person_id, session)
    assignments = await session.scalars(
        select(PersonAssignment)
        .where(PersonAssignment.person_id == person_id)
        .order_by(PersonAssignment.effective_from)
    )
    return ApiResponse[list[PersonAssignmentRead]](
        data=[PersonAssignmentRead.model_validate(assignment) for assignment in assignments]
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
