from sqlalchemy import insert

from app.modules.ubigee.catalog import catalog_rows
from app.modules.ubigee.models import Country, Department, District, Province


async def test_company_and_branch_routes(client, db, admin_headers):
    for model, rows in zip((Country, Department, Province, District), catalog_rows(), strict=True):
        await db.execute(insert(model.__table__), rows)
    await db.commit()

    path = "/api/v1/companies"
    assert (await client.get(path)).status_code == 401
    company_data = {
        "ruc": "20603239475",
        "legal_name": "KASUA AMAZON INVESTMENTS S.A.C.",
        "address": "JR. 20 DE ABRIL S/N",
        "district_code": "220101",
        "website": "https://kasualodge.com/",
        "reservations_email": "reservas@example.com",
    }
    response = await client.post(path, headers=admin_headers, json=company_data)
    assert response.status_code == 201, response.text
    company = response.json()["data"]
    assert company["district"]["province"]["code"] == "2201"
    assert company["district"]["province"]["department"]["code"] == "22"
    assert company["national_hotel_chain"] is False
    assert (await client.post(path, headers=admin_headers, json=company_data)).status_code == 409

    second = await client.post(
        path, headers=admin_headers, json={**company_data, "ruc": "20603239476"}
    )
    assert second.status_code == 201
    second_id = second.json()["data"]["id"]

    company_path = f"{path}/{company['id']}"
    branches_path = f"{company_path}/branches"
    branch_data = {
        "name": "Sucursal Moyobamba",
        "address": "JR. 20 DE ABRIL S/N",
        "district_code": "220101",
        "logo": "/media/logo/main.png",
        "logo_ticket": "/media/logo_ticket/main.png",
    }
    response = await client.post(branches_path, headers=admin_headers, json=branch_data)
    assert response.status_code == 201, response.text
    branch = response.json()["data"]
    assert branch["logo"] == branch_data["logo"]
    assert branch["logo_ticket"] == branch_data["logo_ticket"]
    assert branch["company_id"] == company["id"]
    response = await client.get(branches_path, headers=admin_headers)
    assert response.json()["data"]["items"] == [branch]

    branch_path = f"{branches_path}/{branch['id']}"
    response = await client.get(
        f"{path}/{second_id}/branches/{branch['id']}", headers=admin_headers
    )
    assert response.status_code == 404

    response = await client.patch(
        branch_path, headers=admin_headers, json={"district_code": "999999"}
    )
    assert response.status_code == 404
    response = await client.patch(
        branch_path, headers=admin_headers, json={"district_code": "010103"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["district"]["province"]["department"]["code"] == "01"
    assert (await client.delete(company_path, headers=admin_headers)).status_code == 409
    assert (await client.delete(branch_path, headers=admin_headers)).status_code == 204
    assert (await client.delete(company_path, headers=admin_headers)).status_code == 204
