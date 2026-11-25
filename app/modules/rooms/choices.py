from app.core.document_types import LabeledTextChoice


class RoomStatus(LabeledTextChoice):
    AVAILABLE = "DISPONIBLE", "Disponible"
    OCCUPIED = "OCUPADO", "Ocupado"
    MAINTENANCE = "MANTENIMIENTO", "Mantenimiento"
    RESERVED = "RESERVADO", "Reservado"
