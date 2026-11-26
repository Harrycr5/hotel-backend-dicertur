from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.api.dependencies import DbSession
from app.core.exceptions import ConflictError, NotFoundError
from app.core.pagination import Page, Pagination
from app.core.responses import ApiResponse
from app.modules.auth.dependencies import require_permissions
from app.modules.ubigee.models import District, Province

from .models import Branch, Company
from .schemas import (
    BranchCreate,
    BranchRead,
    BranchUpdate,
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
)

router = APIRouter(prefix="/companies", tags=["Companies"])

company_query = (
    select(Company)
    .options(
        joinedload(Company.district).joinedload(District.province).joinedload(Province.department)
    )
    .execution_options(populate_existing=True)
)
branch_query = (
    select(Branch)
    .options(
        joinedload(Branch.district).joinedload(District.province).joinedload(Province.department)
    )
    .execution_options(populate_existing=True)
)


async def get_company_or_404(session: DbSession, company_id: UUID) -> Company:
    company = await session.scalar(company_query.where(Company.id == company_id))
    if company is None:
        raise NotFoundError("Empresa no encontrada.")
    return company


async def get_branch_or_404(session: DbSession, company_id: UUID, branch_id: UUID) -> Branch:
    branch = await session.scalar(
        branch_query.where(Branch.company_id == company_id, Branch.id == branch_id)
    )
    if branch is None:
        raise NotFoundError("Sucursal no encontrada en esta empresa.")
    return branch


async def validate_district(session: DbSession, district_code: str) -> None:
    if await session.get(District, district_code) is None:
        raise NotFoundError("Distrito no encontrado.")


async def save_company(session: DbSession, company: Company) -> Company:
    ruc = company.ruc
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        if await session.scalar(select(Company.id).where(Company.ruc == ruc)) is not None:
            raise ConflictError("Ya existe una empresa con ese RUC.") from exc
        raise
    company = await get_company_or_404(session, company.id)
    await session.commit()
    return company


@router.get(
    "",
    summary="Listar empresas",
    response_model=ApiResponse[Page[CompanyRead]],
    dependencies=[Depends(require_permissions("companies.read"))],
)
async def list_companies(session: DbSession, pagination: Pagination):
    total = await session.scalar(select(func.count()).select_from(Company))
    companies = await session.scalars(
        company_query.order_by(Company.legal_name, Company.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[CompanyRead]](
        message="Empresas obtenidas correctamente.",
        data=Page[CompanyRead].build(
            [CompanyRead.model_validate(company) for company in companies], total or 0, pagination
        ),
    )


@router.post(
    "",
    summary="Crear empresa",
    response_model=ApiResponse[CompanyRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("companies.create"))],
)
async def create_company(data: CompanyCreate, session: DbSession):
    await validate_district(session, data.district_code)
    company = Company(**data.model_dump())
    session.add(company)
    company = await save_company(session, company)
    return ApiResponse[CompanyRead](
        message="Empresa creada correctamente.", data=CompanyRead.model_validate(company)
    )


@router.get(
    "/{company_id}",
    summary="Consultar empresa",
    response_model=ApiResponse[CompanyRead],
    dependencies=[Depends(require_permissions("companies.read"))],
)
async def get_company(company_id: UUID, session: DbSession):
    company = await get_company_or_404(session, company_id)
    return ApiResponse[CompanyRead](
        message="Empresa obtenida correctamente.", data=CompanyRead.model_validate(company)
    )


@router.patch(
    "/{company_id}",
    summary="Actualizar empresa",
    response_model=ApiResponse[CompanyRead],
    dependencies=[Depends(require_permissions("companies.update"))],
)
async def update_company(company_id: UUID, data: CompanyUpdate, session: DbSession):
    company = await get_company_or_404(session, company_id)
    if data.district_code is not None:
        await validate_district(session, data.district_code)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    company = await save_company(session, company)
    return ApiResponse[CompanyRead](
        message="Empresa actualizada correctamente.", data=CompanyRead.model_validate(company)
    )


@router.delete(
    "/{company_id}",
    summary="Eliminar empresa",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("companies.delete"))],
)
async def delete_company(company_id: UUID, session: DbSession) -> None:
    company = await get_company_or_404(session, company_id)
    await session.delete(company)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if await session.scalar(select(Branch.id).where(Branch.company_id == company_id).limit(1)):
            raise ConflictError("La empresa todavía tiene sucursales.") from exc
        raise


@router.get(
    "/{company_id}/branches",
    summary="Listar sucursales",
    response_model=ApiResponse[Page[BranchRead]],
    dependencies=[Depends(require_permissions("company_branches.read"))],
)
async def list_branches(company_id: UUID, session: DbSession, pagination: Pagination):
    await get_company_or_404(session, company_id)
    total = await session.scalar(
        select(func.count()).select_from(Branch).where(Branch.company_id == company_id)
    )
    branches = await session.scalars(
        branch_query.where(Branch.company_id == company_id)
        .order_by(Branch.name, Branch.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    return ApiResponse[Page[BranchRead]](
        message="Sucursales obtenidas correctamente.",
        data=Page[BranchRead].build(
            [BranchRead.model_validate(branch) for branch in branches], total or 0, pagination
        ),
    )


@router.post(
    "/{company_id}/branches",
    summary="Crear sucursal",
    response_model=ApiResponse[BranchRead],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permissions("company_branches.create"))],
)
async def create_branch(company_id: UUID, data: BranchCreate, session: DbSession):
    await get_company_or_404(session, company_id)
    await validate_district(session, data.district_code)
    branch = Branch(company_id=company_id, **data.model_dump())
    session.add(branch)
    await session.flush()
    branch = await get_branch_or_404(session, company_id, branch.id)
    await session.commit()
    return ApiResponse[BranchRead](
        message="Sucursal creada correctamente.", data=BranchRead.model_validate(branch)
    )


@router.get(
    "/{company_id}/branches/{branch_id}",
    summary="Consultar sucursal",
    response_model=ApiResponse[BranchRead],
    dependencies=[Depends(require_permissions("company_branches.read"))],
)
async def get_branch(company_id: UUID, branch_id: UUID, session: DbSession):
    branch = await get_branch_or_404(session, company_id, branch_id)
    return ApiResponse[BranchRead](
        message="Sucursal obtenida correctamente.", data=BranchRead.model_validate(branch)
    )


@router.patch(
    "/{company_id}/branches/{branch_id}",
    summary="Actualizar sucursal",
    response_model=ApiResponse[BranchRead],
    dependencies=[Depends(require_permissions("company_branches.update"))],
)
async def update_branch(company_id: UUID, branch_id: UUID, data: BranchUpdate, session: DbSession):
    branch = await get_branch_or_404(session, company_id, branch_id)
    if data.district_code is not None:
        await validate_district(session, data.district_code)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(branch, field, value)
    await session.flush()
    branch = await get_branch_or_404(session, company_id, branch_id)
    await session.commit()
    return ApiResponse[BranchRead](
        message="Sucursal actualizada correctamente.", data=BranchRead.model_validate(branch)
    )


@router.delete(
    "/{company_id}/branches/{branch_id}",
    summary="Eliminar sucursal",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permissions("company_branches.delete"))],
)
async def delete_branch(company_id: UUID, branch_id: UUID, session: DbSession) -> None:
    branch = await get_branch_or_404(session, company_id, branch_id)
    await session.delete(branch)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("La sucursal tiene registros de personal asociados.") from exc
