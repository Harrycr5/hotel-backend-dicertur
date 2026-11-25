from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DbSession
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.payment_methods.models import PaymentMethod
from app.modules.reservations.choices import ReservationStatus
from app.modules.reservations.models import Reservation, ReservationPayment
from app.modules.reservations.router import find_reservation
from app.modules.reservations.service import (
    EXPIRATION_CHANNEL,
    has_processing_charge,
    hold_has_expired,
    paid_status,
)

from . import client
from .models import DECLINED, PROCESSING, REQUIRES_3DS, SUCCEEDED, CulqiCharge
from .schemas import AuthenticateCharge, ChargeCreate


def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def validate_token(token: str, key: str) -> None:
    mode = key.split("_")[1]
    prefix, separator, suffix = token.partition(f"_{mode}_")
    if (
        not separator
        or prefix not in {"tkn", "ype"}
        or not suffix.isascii()
        or not suffix.isalnum()
        or len(token) > 150
    ):
        raise ConflictError("Usa un token de Checkout válido para el entorno de Culqi.")


async def get_charge(session: DbSession, charge_id: UUID) -> CulqiCharge:
    charge = await session.get(CulqiCharge, charge_id, populate_existing=True)
    if charge is None:
        raise NotFoundError("Cargo no encontrado.")
    return charge


def verify_balance(reservation: Reservation, amount) -> None:
    if reservation.status not in (ReservationStatus.BOOKED, ReservationStatus.PARTIALLY_PAID):
        raise ConflictError("La reserva no admite cargos.")
    if reservation.status == ReservationStatus.BOOKED and hold_has_expired(
        reservation.created_at, datetime.now(timezone.utc)
    ):
        raise ConflictError("La reserva ya caducó.")
    if reservation.detail is None or amount > reservation.detail.amount_remaining:
        raise ConflictError("El monto supera el saldo pendiente o la reserva carece de un total.")


def check_replay(charge: CulqiCharge, key: str, data: ChargeCreate, digest: str) -> CulqiCharge:
    if (
        charge.idempotency_key != key
        or charge.reservation_id != data.reservation_id
        or charge.amount != data.amount
        or charge.token_hash != digest
        or charge.device_id != data.device_id
    ):
        raise ConflictError("La clave de idempotencia o el token ya se usó para otro cargo.")
    return charge


async def create_charge(session: DbSession, key: str, data: ChargeCreate) -> CulqiCharge:
    token = data.token.get_secret_value()
    digest = token_digest(token)
    lookup = (
        select(CulqiCharge)
        .where(or_(CulqiCharge.idempotency_key == key, CulqiCharge.token_hash == digest))
        .order_by((CulqiCharge.idempotency_key == key).desc())
    )
    existing = await session.scalar(lookup)
    if existing is not None:
        return check_replay(existing, key, data, digest)
    secret = client.api_key()
    validate_token(token, secret)
    reservation = await find_reservation(session, data.reservation_id, lock=True)
    existing = await session.scalar(lookup)
    if existing is not None:
        return check_replay(existing, key, data, digest)
    verify_balance(reservation, data.amount)
    if await has_processing_charge(session, reservation.id):
        raise ConflictError("La reserva ya tiene un cargo pendiente de conciliación.")
    method_id = await session.scalar(
        select(PaymentMethod.id).where(PaymentMethod.code == "CULQI", PaymentMethod.is_active)
    )
    if method_id is None:
        raise ConflictError("El método de pago Culqi no está activo.")
    charge = CulqiCharge(
        reservation_id=reservation.id,
        payment_method_id=method_id,
        idempotency_key=key,
        token_hash=digest,
        amount=data.amount,
        status=PROCESSING,
        device_id=data.device_id,
    )
    session.add(charge)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(lookup)
        if existing is None:
            raise
        return check_replay(existing, key, data, digest)
    return await submit(session, charge, reservation.email, token, secret)


async def authenticate_charge(
    session: DbSession, charge_id: UUID, data: AuthenticateCharge
) -> CulqiCharge:
    charge = await get_charge(session, charge_id)
    reservation = await find_reservation(session, charge.reservation_id, lock=True)
    charge = await get_charge(session, charge_id)
    token = data.token.get_secret_value()
    if token_digest(token) != charge.token_hash:
        raise ConflictError("El token debe ser el mismo que se usó al iniciar el cargo.")
    if charge.status != REQUIRES_3DS:
        return charge
    secret = client.api_key()
    validate_token(token, secret)
    verify_balance(reservation, charge.amount)
    if await has_processing_charge(session, reservation.id):
        raise ConflictError("La reserva ya tiene un cargo pendiente de conciliación.")
    charge.status = PROCESSING
    await session.commit()
    return await submit(
        session,
        charge,
        reservation.email,
        token,
        secret,
        data.authentication.model_dump(mode="json"),
    )


async def submit(
    session: DbSession, charge: CulqiCharge, email: str, token: str, key: str, authentication=None
):
    payload = {
        "amount": int(charge.amount * 100),
        "currency_code": "PEN",
        "email": email,
        "source_id": token,
        "capture": True,
        "metadata": {
            "gateway_attempt_id": str(charge.id),
            "reservation_id": str(charge.reservation_id),
        },
    }
    if charge.device_id is not None:
        payload["antifraud_details"] = {"device_finger_print_id": str(charge.device_id)}
    if authentication is not None:
        payload["authentication_3DS"] = authentication
    status, body = await client.request("POST", "/charges", key, payload)
    return await settle(session, charge, status, body, key, allow_challenge=authentication is None)


async def settle(
    session: DbSession,
    charge: CulqiCharge,
    status: int,
    body: dict,
    key: str,
    *,
    allow_challenge: bool = False,
    reconcile_id: str | None = None,
) -> CulqiCharge:
    reservation = await find_reservation(session, charge.reservation_id, lock=True)
    charge = await get_charge(session, charge.id)
    if charge.status != PROCESSING:
        if reconcile_id is not None and charge.provider_charge_id != reconcile_id:
            raise ConflictError("El cargo ya tiene otro resultado registrado.")
        return charge

    provider_id = body.get("id")
    metadata = body.get("metadata")
    verified = (
        status in (200, 201)
        and body.get("object") == "charge"
        and isinstance(provider_id, str)
        and provider_id.startswith(f"chr_{key.split('_')[1]}_")
        and len(provider_id) <= 100
        and body.get("response_code") == "venta_exitosa"
        and body.get("capture") is not False
        and body.get("amount") == int(charge.amount * 100)
        and body.get("amount_refunded") == 0
        and body.get("currency") == "PEN"
        and isinstance(metadata, dict)
        and metadata.get("gateway_attempt_id") == str(charge.id)
        and (reconcile_id is None or reconcile_id == provider_id)
    )
    if verified:
        detail = reservation.detail
        if detail is None or detail.amount_remaining < charge.amount:
            raise ConflictError("El cargo fue recibido y su saldo requiere conciliación.")
        detail.amount_paid += charge.amount
        detail.amount_remaining -= charge.amount
        reservation.paid_at = datetime.now(timezone.utc)
        reservation.payment_method_id = charge.payment_method_id
        reservation.payment_amount = charge.amount
        reservation.transaction_number = provider_id
        reservation.status = paid_status(detail.amount_paid, detail.final_total)
        charge.provider_charge_id = provider_id
        charge.status = SUCCEEDED
        session.add(
            ReservationPayment(
                reservation_id=reservation.id,
                payment_method_id=charge.payment_method_id,
                culqi_charge_id=charge.id,
                amount=charge.amount,
            )
        )
    elif reconcile_id is not None:
        raise ConflictError("Culqi no confirmó un cargo capturado que coincida con este intento.")
    elif (
        allow_challenge and status == 200 and body and body.get("object") not in ("charge", "error")
    ):
        charge.status = REQUIRES_3DS
    elif (
        status in (400, 401, 402, 403, 422)
        and body.get("object") == "error"
        and (
            body.get("decline_code")
            or body.get("type") in ("authentication_error", "parameter_error")
        )
    ):
        charge.status = DECLINED
    if charge.status != PROCESSING and session.get_bind().dialect.name == "postgresql":
        await session.execute(select(func.pg_notify(EXPIRATION_CHANNEL, "")))
    await session.commit()
    return charge


async def reconcile_charge(session: DbSession, charge_id: UUID, provider_id: str) -> CulqiCharge:
    charge = await get_charge(session, charge_id)
    if charge.status == SUCCEEDED and charge.provider_charge_id == provider_id:
        return charge
    if charge.status != PROCESSING:
        raise ConflictError("El cargo no está pendiente de conciliación.")
    secret = client.api_key()
    if not provider_id.startswith(f"chr_{secret.split('_')[1]}_"):
        raise ConflictError("El cargo pertenece a otro entorno de Culqi.")
    await session.rollback()
    charge = await get_charge(session, charge_id)
    status, body = await client.request("GET", f"/charges/{provider_id}", secret)
    return await settle(session, charge, status, body, secret, reconcile_id=provider_id)
