from collections import defaultdict

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.core.exceptions import NotFoundError
from app.core.responses import ApiResponse

from .models import Country, Department, District, Province
from .schemas import (
    CountryRead,
    CountrySummary,
    DepartmentRead,
    DistrictRead,
    ProvinceRead,
    UbigeoSearch,
)

router = APIRouter(prefix="/ubigeo", tags=["Ubigeo"])


@router.get(
    "/countries", summary="Listar y buscar países", response_model=ApiResponse[list[CountrySummary]]
)
async def get_countries(session: DbSession, search: str = Query("", max_length=100)):
    query = select(Country).order_by(Country.name, Country.code)
    term = search.strip()
    exact_country = await session.get(Country, term.upper()) if len(term) == 2 else None
    if term:
        query = query.where(Country.name.icontains(term, autoescape=True))

    countries = [exact_country] if exact_country else (await session.scalars(query)).all()
    return ApiResponse[list[CountrySummary]](
        message="Países obtenidos correctamente.",
        data=[CountrySummary(code=country.code, name=country.name) for country in countries],
    )


@router.get("", summary="Consultar ubigeos del Perú", response_model=ApiResponse[CountryRead])
async def get_ubigeo(session: DbSession, search: UbigeoSearch = "PE"):
    # Los pares 00 representan niveles agregados, p. ej. 2200 o 220100.
    code = "" if search == "PE" else search
    while code.endswith("00") and len(code) > 2:
        code = code[:-2]

    country = await session.get(Country, "PE")
    departments_query = select(Department).where(Department.country_code == "PE")
    provinces_query = select(Province)
    districts_query = select(District)
    if code:
        departments_query = departments_query.where(Department.code == code[:2])
        provinces_query = provinces_query.where(Province.code.startswith(code[:4]))
        districts_query = districts_query.where(District.code.startswith(code))
    departments = (await session.scalars(departments_query.order_by(Department.code))).all()
    provinces = (await session.scalars(provinces_query.order_by(Province.code))).all()
    districts = (await session.scalars(districts_query.order_by(District.code))).all()
    if country is None or not departments or (code and not districts):
        raise NotFoundError("Ubigeo no encontrado.")

    districts_by_province: dict[str, list[DistrictRead]] = defaultdict(list)
    for district in districts:
        districts_by_province[district.province_code].append(
            DistrictRead(code=district.code, name=district.name)
        )

    provinces_by_department: dict[str, list[ProvinceRead]] = defaultdict(list)
    for province in provinces:
        provinces_by_department[province.department_code].append(
            ProvinceRead(
                code=province.code,
                name=province.name,
                districts=districts_by_province[province.code],
            )
        )

    return ApiResponse[CountryRead](
        message="Ubigeo obtenido correctamente.",
        data=CountryRead(
            code=country.code,
            name=country.name,
            departments=[
                DepartmentRead(
                    code=department.code,
                    name=department.name,
                    provinces=provinces_by_department[department.code],
                )
                for department in departments
            ],
        ),
    )
