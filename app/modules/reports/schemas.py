from typing import Annotated

from pydantic import BaseModel, Field

from .choices import ReportMonth


class ReportPeriod(BaseModel):
    month: ReportMonth
    year: Annotated[int, Field(ge=1900, le=9998)]


class ReportMonthRead(BaseModel):
    value: ReportMonth
    label: str
