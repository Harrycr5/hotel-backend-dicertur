from typing import Annotated

from pydantic import BaseModel, Field

DistrictCode = Annotated[str, Field(pattern=r"^[0-9]{6}$")]
UbigeoSearch = Annotated[str, Field(pattern=r"^(PE|[0-9]{2}([0-9]{2}){0,2})$")]


class DistrictRead(BaseModel):
    code: str
    name: str


class ProvinceRead(BaseModel):
    code: str
    name: str
    districts: list[DistrictRead]


class DepartmentRead(BaseModel):
    code: str
    name: str
    provinces: list[ProvinceRead]


class CountrySummary(BaseModel):
    code: str
    name: str


class CountryRead(CountrySummary):
    departments: list[DepartmentRead]
