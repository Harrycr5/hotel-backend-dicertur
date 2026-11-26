from app.core.document_types import LabeledTextChoice


class WebsiteCategory(LabeledTextChoice):
    HOME = "INICIO", "Inicio"
    HOTEL = "HOTEL", "Hotel"
    ROOMS = "HABITACIONES", "Habitaciones"
    RESTAURANT = "RESTAURANTE", "Restaurante"
    BAR = "BAR", "Bar"
    SERVICES = "SERVICIOS", "Servicios"


class ComplaintType(LabeledTextChoice):
    COMPLAINT = "QUEJA", "Queja"
    CLAIM = "RECLAMO", "Reclamo"


class MediaType(LabeledTextChoice):
    VIDEO = "VIDEO", "Video"
    PDF = "PDF", "PDF"
