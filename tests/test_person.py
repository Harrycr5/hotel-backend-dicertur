from app.modules.person.models import Customer
from app.modules.ubigee.models import Country


async def test_customers_are_listed_with_reservation_count(client, db, admin_headers):
    db.add(Country(code="PE", name="Perú"))
    await db.flush()
    db.add(
        Customer(
            identity_key="EMAIL:demo@example.com",
            document_type="SIN DOCUMENTO",
            name="Cliente de prueba",
            phone="+51900000000",
            email="demo@example.com",
            country_code="PE",
            reservation_count=2,
            city="Moyobamba",
            address="Dirección de prueba",
        )
    )
    await db.commit()

    path = "/api/v1/customers"
    assert (await client.get(path)).status_code == 401
    response = await client.get(path, headers=admin_headers, params={"page_size": 1})
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    [customer] = response.json()["data"]["items"]
    assert customer["reservation_count"] == 2
    assert "identity_key" not in customer


async def test_person_routes(client, admin_headers):
    path = "/api/v1/persons"
    assert (await client.get(path)).status_code == 401

    response = await client.get(f"{path}/choices", headers=admin_headers)
    assert response.status_code == 200
    choices = response.json()["data"]
    assert choices["genders"] == [
        {"value": "MASCULINO", "label": "Hombre"},
        {"value": "FEMENINO", "label": "Mujer"},
    ]
    assert len(choices["document_types"]) == 5
    assert len(choices["areas"]) == 7
    assert len(choices["categories"]) == 3

    response = await client.post(
        path,
        headers=admin_headers,
        json={
            "name": "Ana",
            "last_name": "Pérez",
            "document_type": "DNI",
            "document_number": "01234567",
            "mobile_phone": "987654321",
            "area": "RECEPCIÓN",
            "gender": "FEMENINO",
            "category": "EMPLEADO",
        },
    )
    assert response.status_code == 201
    person = response.json()["data"]
    assert person["mobile_phone"] == "+51987654321"
    assert person["document_number"] == "01234567"
    assert person["is_permanent_employee"] is False

    response = await client.get(path, headers=admin_headers)
    assert response.json()["data"]["items"] == [person]

    detail_path = f"{path}/{person['id']}"
    response = await client.patch(detail_path, headers=admin_headers, json={"gender": "Mujer"})
    assert response.status_code == 422
    response = await client.patch(
        detail_path, headers=admin_headers, json={"is_permanent_employee": True}
    )
    assert response.status_code == 200
    response = await client.get(detail_path, headers=admin_headers)
    assert response.json()["data"]["is_permanent_employee"] is True
    assert (await client.delete(detail_path, headers=admin_headers)).status_code == 204
    assert (await client.get(detail_path, headers=admin_headers)).status_code == 404
