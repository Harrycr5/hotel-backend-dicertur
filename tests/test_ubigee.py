from sqlalchemy import insert

from app.modules.ubigee.catalog import catalog_rows
from app.modules.ubigee.models import Country, Department, District, Province


async def test_country_search_and_peru_hierarchy(client, db):
    for model, rows in zip((Country, Department, Province, District), catalog_rows(), strict=True):
        await db.execute(insert(model.__table__), rows)
    await db.commit()

    path = "/api/v1/ubigeo/countries"
    for term, expected in (
        (" pe ", [{"code": "PE", "name": "Perú"}]),
        (
            "unidos",
            [
                {"code": "AE", "name": "Emiratos Árabes Unidos"},
                {"code": "US", "name": "Estados Unidos"},
            ],
        ),
        ("%", []),
    ):
        response = await client.get(path, params={"search": term})
        assert response.status_code == 200
        assert response.json()["data"] == expected

    response = await client.get("/api/v1/ubigeo", params={"search": "220100"})
    assert response.status_code == 200
    peru = response.json()["data"]
    assert peru["code"] == "PE"
    [department] = peru["departments"]
    assert department["code"] == "22"
    [province] = department["provinces"]
    assert province["code"] == "2201"
    assert province["districts"]
