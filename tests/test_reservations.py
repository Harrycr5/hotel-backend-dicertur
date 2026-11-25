from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import update

from app.modules.payment_methods.models import PaymentMethod
from app.modules.reservations.models import Reservation
from app.modules.reservations.service import expire_unpaid_reservations
from app.modules.rooms.models import Floor, Rate, Room, RoomType
from app.modules.ubigee.models import Country


async def test_reservation_payments_companions_and_expiration(client, admin_headers, db):
    floor = Floor(description="Primer piso")
    room_type = RoomType(name="Suites (incluye sala)")
    method = PaymentMethod(code="EFECTIVO", name="Efectivo")
    second_method = PaymentMethod(code="TARJETA", name="Tarjeta")
    rate = Rate(name="Estándar", price=55)
    db.add_all([floor, room_type, method, second_method, rate, Country(code="PE", name="Perú")])
    await db.flush()
    room = Room(name="Suite panorámica", code="HN001", floor_id=floor.id, room_type_id=room_type.id)
    db.add(room)
    await db.commit()

    prefix = "/api/v1/reservations"
    assert (await client.get(prefix)).status_code == 401
    methods = await client.get("/api/v1/payment-methods", headers=admin_headers)
    assert methods.json()["data"][0]["code"] == "EFECTIVO"
    statuses = await client.get(f"{prefix}/statuses", headers=admin_headers)
    assert len(statuses.json()["data"]) == 6

    payload = {
        "room_id": str(room.id),
        "rate_id": str(rate.id),
        "check_in": "11-06-2025 19:00",
        "check_out": "15-06-2025 19:00",
        "document_type": "PASAPORTE",
        "document_number": "01234567",
        "full_name": "Huésped de prueba",
        "birth_date": "1994-03-14",
        "phone": "+51900000000",
        "email": "huesped@example.com",
        "country_code": "PE",
        "city": "Moyobamba",
        "region": "San Martín",
        "district": "Moyobamba",
        "address": "Dirección de prueba",
        "travel_reason": "Turismo",
        "dietary_restrictions": "Ninguna",
        "gender": "FEMENINO",
        "companions": [
            {"document_type": "DNI", "document_number": "01234567", "full_name": "Acompañante"}
        ],
        "detail": {
            "amount_remaining": "220.00",
            "base_price": "220.00",
            "final_total": "220.00",
            "stay_days": 4,
            "unit_rate": "55.00",
        },
    }

    invalid = {**payload, "rate_id": None, "dietary_restrictions": " "}
    invalid.pop("birth_date")
    response = await client.post(prefix, headers=admin_headers, json=invalid)
    assert response.status_code == 422

    async def create(**overrides):
        response = await client.post(prefix, headers=admin_headers, json={**payload, **overrides})
        assert response.status_code == 201, response.text
        return response.json()["data"]

    paid = await create()
    unpaid = await create()
    complimentary = await create(status="RESERVA SIN PAGOS")
    assert paid["status"] == "RESERVADO"
    assert paid["rate_name"] == rate.name
    assert paid["room_type_name"] == room_type.name
    assert paid["companions"][0]["document_number"] == "01234567"
    assert paid["companions"][0]["birth_date"] is None
    assert paid["detail"]["amount_remaining"] == "220.00"

    payment_path = f"{prefix}/{paid['id']}/payment"
    response = await client.patch(
        payment_path,
        headers=admin_headers,
        json={"amount_paid": "80.00", "method_id": str(method.id)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "RESERVA CON PAGOS PARCIALES"
    assert response.json()["data"]["detail"]["amount_remaining"] == "140.00"

    now = datetime.now(timezone.utc)
    await db.execute(update(Reservation).values(created_at=now - timedelta(hours=24)))
    await expire_unpaid_reservations(db, now)
    await db.commit()

    for item, expected in (
        (paid, "RESERVA CON PAGOS PARCIALES"),
        (unpaid, "CADUCADO"),
        (complimentary, "RESERVA SIN PAGOS"),
    ):
        response = await client.get(f"{prefix}/{item['id']}", headers=admin_headers)
        assert response.json()["data"]["status"] == expected

    response = await client.patch(
        f"{prefix}/{unpaid['id']}/payment", headers=admin_headers, json={"amount_paid": "220.00"}
    )
    assert response.status_code == 409
    response = await client.patch(
        payment_path, headers=admin_headers, json={"amount_paid": "100.00"}
    )
    assert response.status_code == 200
    final_payment = {"amount_paid": "220.00", "method_id": str(second_method.id)}
    response = await client.patch(payment_path, headers=admin_headers, json=final_payment)
    assert response.status_code == 200, response.text
    confirmed = response.json()["data"]
    assert confirmed["status"] == "CONFIRMADO"
    assert confirmed["detail"]["amount_remaining"] == "0.00"
    assert (
        await client.patch(payment_path, headers=admin_headers, json=final_payment)
    ).status_code == 200
    response = await client.get(f"{prefix}/{paid['id']}/payments", headers=admin_headers)
    summary = response.json()["data"]
    assert summary["payment_method_count"] == 2
    assert summary["unattributed_amount"] == "20.00"
    assert [
        (row["code"], row["payment_count"], row["amount_paid"]) for row in summary["methods"]
    ] == [
        ("EFECTIVO", 1, "80.00"),
        ("TARJETA", 1, "120.00"),
    ]
    assert UUID(confirmed["detail"]["reservation_id"]) == UUID(paid["id"])

    response = await client.patch(f"{prefix}/{paid['id']}/cancel", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "CANCELADO"
