from io import BytesIO
from uuid import uuid4

from PIL import Image

from app.modules.rooms.models import RoomCategory


async def test_rooms_with_floors_rates_and_optional_images(client, db, admin_headers):
    prefix = "/api/v1/rooms"
    db.add(RoomCategory(name="Premium"))
    await db.commit()
    response = await client.get(f"{prefix}/categories", headers=admin_headers)
    assert response.status_code == 200
    [category] = response.json()["data"]
    assert category["name"] == "Premium"
    response = await client.get(f"{prefix}/statuses", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["data"] == [
        {"value": "DISPONIBLE", "label": "Disponible"},
        {"value": "OCUPADO", "label": "Ocupado"},
        {"value": "MANTENIMIENTO", "label": "Mantenimiento"},
        {"value": "RESERVADO", "label": "Reservado"},
    ]

    async def create(path, data):
        response = await client.post(prefix + path, headers=admin_headers, json=data)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    floor = await create("/floors", {"description": "Primer piso"})
    room_type = await create("/types", {"name": "Suite"})
    rate = await create("/rates", {"name": "Estándar", "price": "280.00"})
    other_rate = await create("/rates", {"name": "Temporada alta", "price": "350.00"})
    room = await create(
        "",
        {
            "name": "Suite panorámica premium",
            "code": "HN001",
            "floor_id": floor["id"],
            "room_type_id": room_type["id"],
            "category_id": category["id"],
            "rate_ids": [rate["id"], other_rate["id"]],
            "details": [{"detail": "Wi-Fi"}],
        },
    )
    assert room["images"] == []
    assert room["category_id"] == category["id"]
    assert set(room["rate_ids"]) == {rate["id"], other_rate["id"]}
    assert room["status"] == "DISPONIBLE"
    response = await client.delete(f"{prefix}/rates/{rate['id']}", headers=admin_headers)
    assert response.status_code == 409

    room_path = f"{prefix}/{room['id']}"
    response = await client.patch(
        room_path, headers=admin_headers, json={"category_id": str(uuid4())}
    )
    assert response.status_code == 404
    response = await client.patch(room_path, headers=admin_headers, json={"status": "CERRADO"})
    assert response.status_code == 422
    response = await client.patch(room_path, headers=admin_headers, json={"status": "RESERVADO"})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "RESERVADO"
    images = []
    for format, mode in (("PNG", "RGBA"), ("JPEG", "RGB")):
        with Image.new(mode, (2400, 1200)) as source, BytesIO() as buffer:
            source.save(buffer, format=format)
            original = buffer.getvalue()
        response = await client.post(
            f"{room_path}/images",
            headers=admin_headers,
            files={"file": (f"room.{format.lower()}", original, f"image/{format.lower()}")},
        )
        assert response.status_code == 201, response.text
        image = response.json()["data"]
        images.append(image)
        public = await client.get(image["image"])
        assert public.headers["content-type"] == "image/webp"
        with Image.open(BytesIO(public.content)) as converted:
            assert converted.format == "WEBP"
            assert converted.size == (1920, 960)
            assert converted.mode == mode
    response = await client.post(
        f"{room_path}/images",
        headers=admin_headers,
        files={"file": ("fake.jpg", b"\xff\xd8\xff", "image/jpeg")},
    )
    assert response.status_code == 415
    listing = await client.get(prefix, headers=admin_headers)
    listed_images = listing.json()["data"]["items"][0]["images"]
    assert {item["id"]: item["image"] for item in listed_images} == {
        item["id"]: item["image"] for item in images
    }

    response = await client.patch(
        room_path,
        headers=admin_headers,
        json={"visible": False, "rate_ids": [], "category_id": None},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["rate_ids"] == []
    assert response.json()["data"]["category_id"] is None
    assert (await client.get(image["image"])).status_code == 404
    assert (await client.delete(room_path, headers=admin_headers)).status_code == 204
    assert (await client.get(room_path, headers=admin_headers)).status_code == 404


async def test_room_type_and_rate_routes(client, admin_headers):
    types_path = "/api/v1/rooms/types"
    rates_path = "/api/v1/rooms/rates"
    assert (await client.get(types_path)).status_code == 401

    room_data = {"name": "Dobles y matrimoniales"}
    response = await client.post(types_path, headers=admin_headers, json=room_data)
    assert response.status_code == 201
    room = response.json()["data"]
    assert room["has_bathroom"] is None
    assert room["bed_places"] is None
    assert (await client.post(types_path, headers=admin_headers, json=room_data)).status_code == 409

    type_path = f"{types_path}/{room['id']}"
    response = await client.patch(
        type_path, headers=admin_headers, json={"has_bathroom": False, "bed_places": 2}
    )
    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["name"] == room_data["name"]
    assert updated["has_bathroom"] is False
    assert updated["bed_places"] == 2
    assert (await client.get(types_path, headers=admin_headers)).json()["data"]["items"] == [
        updated
    ]

    rate_data = {"name": "Tarifa estándar", "rate_condition": "---", "price": "280.00"}
    response = await client.post(rates_path, headers=admin_headers, json=rate_data)
    assert response.status_code == 201
    rate = response.json()["data"]
    assert rate["price"] == "280.00"
    assert rate["is_active"] is True

    rate_path = f"{rates_path}/{rate['id']}"
    response = await client.patch(rate_path, headers=admin_headers, json={"price": "280.123"})
    assert response.status_code == 422
    response = await client.patch(rate_path, headers=admin_headers, json={"is_active": False})
    assert response.status_code == 200
    assert (await client.get(rate_path, headers=admin_headers)).json()["data"]["is_active"] is False
    assert (await client.delete(rate_path, headers=admin_headers)).status_code == 204
    assert (await client.delete(type_path, headers=admin_headers)).status_code == 204
