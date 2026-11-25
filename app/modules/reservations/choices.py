from app.core.document_types import LabeledTextChoice


class ReservationStatus(LabeledTextChoice):
    CONFIRMED = "CONFIRMADO", "Confirmado"
    BOOKED = "RESERVADO", "Reservado"
    CANCELED = "CANCELADO", "Cancelado"
    EXPIRED = "CADUCADO", "Caducado"
    WITHOUT_PAYMENT = "RESERVA SIN PAGOS", "Reserva Sin Pagos"
    PARTIALLY_PAID = "RESERVA CON PAGOS PARCIALES", "Reserva Con Pagos Parciales"
