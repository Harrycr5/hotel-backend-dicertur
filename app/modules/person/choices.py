from enum import StrEnum

from app.core.document_types import LabeledTextChoice


class PersonGender(LabeledTextChoice):
    MASCULINE = "MASCULINO", "Hombre"
    FEMININE = "FEMENINO", "Mujer"


class PersonArea(StrEnum):
    EXECUTIVES_AND_ADMINISTRATIVE = "EJECUTIVOS Y ADMINISTRATIVOS"
    RECEPTION = "RECEPCIÓN"
    CONCIERGE = "CONSERJERÍA"
    HOUSEKEEPING = "LIMPIEZA"
    DINING_AND_CAFETERIA = "COMEDOR Y CAFETERÍA"
    BAR = "BAR"
    OTHER_POSITIONS = "DEMÁS PUESTOS"


class PersonCategory(StrEnum):
    EMPLOYEE = "EMPLEADO"
    OWNER_OR_PARTNER = "PROPIETARIO O SOCIO"
    UNPAID = "NO REMUNERADO"
