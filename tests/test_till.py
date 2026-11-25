from app.modules.payment_methods.models import PaymentMethod
from app.modules.till.models import TillConcept


async def test_till_transfers_replays_void_and_cash_closing(client, db, admin_headers):
    cash = PaymentMethod(code="EFECTIVO", name="Efectivo")
    card = PaymentMethod(code="TARJETA", name="Tarjeta")
    concept = TillConcept(code="PAGO_RESERVA", name="Pago de reserva")
    transfer_concept = TillConcept(code="TRANSFERENCIA_ENTRE_CAJAS", name="Transferencia")
    db.add_all([cash, card, concept, transfer_concept])
    await db.commit()
    root = "/api/v1/tills"

    async def write(method, path, key, data, expected):
        response = await client.request(
            method, root + path, headers={**admin_headers, "Idempotency-Key": key}, json=data
        )
        assert response.status_code == expected, response.text
        return response.json().get("data")

    source = await write("POST", "", "till-1", {"name": "Recepción"}, 201)
    destination = await write("POST", "", "till-2", {"name": "Restaurante"}, 201)
    opened = {"opening_amount": "100"}
    shifts_path = f"/{source['id']}/shifts"
    source_shift = await write("POST", shifts_path, "open-1", opened, 201)
    assert await write("POST", shifts_path, "open-1", opened, 201) == source_shift
    await write("POST", shifts_path, "another-open", opened, 409)
    destination_shift = await write(
        "POST", f"/{destination['id']}/shifts", "open-2", {"opening_amount": "0"}, 201
    )
    shift_id = source_shift["id"]

    for method, amount in ((cash, "30.00"), (card, "500.00")):
        await write(
            "POST",
            f"/shifts/{shift_id}/movements",
            str(method.id),
            {
                "concept_id": str(concept.id),
                "payment_method_id": str(method.id),
                "direction": "INGRESO",
                "amount": amount,
            },
            201,
        )
    transfer = {
        "source_shift_id": shift_id,
        "destination_shift_id": destination_shift["id"],
        "amount": "40.00",
    }
    await write("POST", "/transfers", "too-much", {**transfer, "amount": "131"}, 409)
    sent = await write("POST", "/transfers", "transfer-1", transfer, 201)
    assert (
        await write("POST", "/transfers", "transfer-1", {**transfer, "amount": "40"}, 201) == sent
    )
    await write("POST", "/transfers", "transfer-1", {**transfer, "amount": "41"}, 409)
    assert sent["expense"]["direction"] == "EGRESO"
    assert sent["income"]["direction"] == "INGRESO"
    assert sent["expense"]["transfer_id"] == sent["income"]["transfer_id"] == sent["id"]

    canceled = await write(
        "PATCH", f"/movements/{sent['income']['id']}/void", "void-1", {"reason": "Error"}, 200
    )
    assert len(canceled["movements"]) == 2
    assert all(entry["voided_at"] and entry["voided_by_id"] for entry in canceled["movements"])
    await write("POST", "/transfers", "transfer-2", transfer, 201)
    close_path = f"/shifts/{shift_id}/close"
    closed = await write("PATCH", close_path, "close-1", {"counted_cash": "89.50"}, 200)
    assert closed["expected_cash"] == "90.00"
    assert closed["difference"] == "-0.50"
    assert await write("PATCH", close_path, "close-1", {"counted_cash": "89.50"}, 200) == closed
    await write("POST", "/transfers", "after-close", transfer, 409)

    response = await client.get(f"{root}/shifts/{shift_id}/movements", headers=admin_headers)
    assert response.json()["data"]["total"] == 4
