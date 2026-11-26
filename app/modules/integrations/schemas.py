from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)


class SendEmail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    asunto: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\r\n]+$"
        ),
    ]
    mensaje: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)
    ]
    archivo: str | None = None


class ReniecLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dni: Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")]


class ReniecRecord(BaseModel):
    nuDni: Annotated[str, StringConstraints(pattern=r"^[0-9]{8}$")] = Field(
        validation_alias=AliasChoices("nuDni", "D_NUDNI")
    )
    digitoVerificacion: str | None = Field(
        None, validation_alias=AliasChoices("digitoVerificacion", "D_DIGITOVERIFICACION")
    )
    preNombres: str | None = Field(
        None, validation_alias=AliasChoices("preNombres", "D_PRENOMBRES")
    )
    apePaterno: str | None = Field(
        None, validation_alias=AliasChoices("apePaterno", "D_APEPATERNO")
    )
    apeMaterno: str | None = Field(
        None, validation_alias=AliasChoices("apeMaterno", "D_APEMATERNO")
    )
    feNacimiento: str | None = Field(
        None, validation_alias=AliasChoices("feNacimiento", "D_FENACIMIENTO")
    )

    @field_validator("nuDni", mode="before")
    @classmethod
    def normalize_dni(cls, value: object) -> object:
        if type(value) is int and 0 <= value <= 99_999_999:
            return f"{value:08d}"
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("digitoVerificacion", mode="before")
    @classmethod
    def normalize_verification_digit(cls, value: object) -> object:
        if type(value) is int and 0 <= value <= 9:
            return str(value)
        return value


class ReniecResponse(BaseModel):
    success: Literal[True] = True
    data: ReniecRecord
