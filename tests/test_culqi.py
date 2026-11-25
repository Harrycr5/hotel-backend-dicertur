from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.modules.culqi import client as provider
from app.modules.payment_methods.models import PaymentMethod
from app.modules.reservations.models import Reservation, ReservationDetail
from app.modules.rooms.models import Floor, Rate, Room, RoomType
from app.modules.ubigee.models import Country


async def test_culqi_retries_and_reconciliation(client, db, admin_headers, monkeypatch):
    floor = Floor(description="Primer piso")
    room_type = RoomType(name="Suite")
    rate = Rate(name="Estándar", price=100)
    db.add_all(
        [
            floor,
            room_type,
            rate,
            Country(code="PE", name="Perú"),
            PaymentMethod(code="CULQI", name="Culqi"),
        ]
    )
    await db.flush()
    room = Room(name="Suite", code="001", room_type_id=room_type.id, floor_id=floor.id)
    db.add(room)
    await db.flush()
    now = datetime.now(timezone.utc)
    reservation = Reservation(
        room_id=room.id,
        rate_id=rate.id,
        check_in=now,
        check_out=now + timedelta(days=1),
        created_at=now,
        document_type="SIN DOCUMENTO",
        full_name="Huésped de prueba",
        birth_date=date(1995, 1, 1),
        phone="+51900000000",
        email="demo@example.com",
        country_code="PE",
        city="Lima",
        region="Lima",
        district="Lima",
        address="Prueba",
        travel_reason="Turismo",
        dietary_restrictions="Ninguna",
        gender="FEMENINO",
        detail=ReservationDetail(
            amount_paid=Decimal("0"),
            amount_remaining=Decimal("100"),
            base_price=Decimal("100"),
            promotion_discount=Decimal("0"),
            final_total=Decimal("100"),
            stay_days=1,
            unit_rate=Decimal("100"),
        ),
    )
    db.add(reservation)
    await db.commit()
    sent = []

    async def request(method, path, key, payload=None):
        if method == "POST":
            sent.append(payload)
            assert payload["amount"] == 10000
            assert payload["metadata"]["reservation_id"] == str(reservation.id)
            return 0, {}
        return 200, {
            "id": path.rsplit("/", 1)[-1],
            "object": "charge",
            "amount": 10000,
            "amount_refunded": 0,
            "currency": "PEN",
            "response_code": "venta_exitosa",
            "metadata": sent[0]["metadata"],
        }

    monkeypatch.setattr(provider, "api_key", lambda: "sk_test_demo")
    monkeypatch.setattr(provider, "request", request)
    path = "/api/v1/culqi/charges"
    headers = {**admin_headers, "Idempotency-Key": "booking-payment-1"}
    data = {"reservation_id": str(reservation.id), "amount": "100.00", "token": "tkn_test_demo"}
    response = await client.post(path, headers=headers, json=data)
    assert response.status_code == 201, response.text
    pending = response.json()["data"]
    assert pending["status"] == "PROCESSING"
    replay = await client.post(path, headers=headers, json=data)
    assert replay.json()["data"] == pending
    assert len(sent) == 1
    another = await client.post(
        path, headers={**headers, "Idempotency-Key": "new"}, json={**data, "token": "tkn_test_new"}
    )
    assert another.status_code == 409
    reservation_path = f"/api/v1/reservations/{reservation.id}"
    canceled = await client.patch(f"{reservation_path}/cancel", headers=admin_headers)
    assert canceled.status_code == 409

    for _ in range(2):
        settled = await client.post(
            f"{path}/{pending['id']}/reconcile",
            headers=admin_headers,
            json={"provider_charge_id": "chr_test_demo"},
        )
        assert settled.status_code == 200, settled.text
        assert settled.json()["data"]["status"] == "SUCCEEDED"
    detail = (await client.get(reservation_path, headers=admin_headers)).json()["data"]
    assert detail["status"] == "CONFIRMADO"
    assert detail["detail"]["amount_paid"] == "100.00"
    assert detail["transaction_number"] == "chr_test_demo"
    payments = await client.get(f"{reservation_path}/payments", headers=admin_headers)
    summary = payments.json()["data"]
    assert summary["payment_method_count"] == 1
    assert summary["methods"][0]["code"] == "CULQI"
    assert summary["methods"][0]["payment_count"] == 1
    assert summary["methods"][0]["amount_paid"] == "100.00"
    assert len(sent) == 1
