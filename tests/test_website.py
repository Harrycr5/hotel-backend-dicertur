from base64 import b64encode
from io import BytesIO

from PIL import Image


async def test_website_content_and_public_forms(client, admin_headers):
    root = "/api/v1/website"
    response = await client.get(f"{root}/choices")
    assert response.status_code == 200
    assert {item["value"] for item in response.json()["data"]["request_types"]} == {
        "QUEJA",
        "RECLAMO",
    }

    gallery_data = {"category": "HOTEL", "description": "Servicios e instalaciones"}
    assert (await client.post(f"{root}/galleries", json=gallery_data)).status_code == 401
    gallery = await client.post(f"{root}/galleries", headers=admin_headers, json=gallery_data)
    assert gallery.status_code == 201, gallery.text
    gallery_url = f"{root}/galleries/{gallery.json()['data']['id']}"
    with Image.new("RGB", (8, 8)) as photo, BytesIO() as buffer:
        photo.save(buffer, format="PNG")
        image = await client.post(
            f"{gallery_url}/images",
            headers=admin_headers,
            files={"file": ("hotel.png", buffer.getvalue(), "image/png")},
        )
    assert image.status_code == 201, image.text
    image_url = image.json()["data"]["image"]
    public_image = await client.get(image_url)
    assert public_image.headers["content-type"] == "image/webp"
    response = await client.put(
        gallery_url, headers=admin_headers, json={**gallery_data, "is_active": False}
    )
    assert response.status_code == 200
    assert (await client.get(image_url)).status_code == 404
    assert (await client.get(f"{root}/galleries")).json()["data"] == []

    for description in ("Bienvenidos", "Bienvenidos al hotel"):
        response = await client.put(
            f"{root}/descriptions/INICIO", headers=admin_headers, json={"description": description}
        )
        assert response.status_code == 200, response.text
    response = await client.get(f"{root}/descriptions?category=INICIO")
    assert response.json()["data"] == [
        {"category": "INICIO", "description": "Bienvenidos al hotel"}
    ]

    pdf = b"%PDF-1.7\n%%EOF"
    response = await client.post(
        f"{root}/pdfs",
        headers=admin_headers,
        json={"title": "Carta", "pdf": "data:application/pdf;base64," + b64encode(pdf).decode()},
    )
    assert response.status_code == 201, response.text
    public_pdf = await client.get(response.json()["data"]["url"])
    assert public_pdf.content == pdf
    assert public_pdf.headers["content-disposition"].startswith("attachment;")
    response = await client.post(
        f"{root}/videos",
        headers=admin_headers,
        json={"title": "Video", "video": b64encode(pdf).decode()},
    )
    assert response.status_code == 415
    mp4_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    response = await client.post(
        f"{root}/videos",
        headers=admin_headers,
        json={"title": "Video", "video": b64encode(mp4_header).decode()},
    )
    assert response.status_code == 201, response.text
    video = await client.get(response.json()["data"]["url"])
    assert video.headers["content-type"] == "video/mp4"
    assert video.content == mp4_header

    complaint = {
        "full_name": "Cliente de prueba",
        "email": "demo@example.com",
        "document_type": "DNI",
        "document_number": "01234567",
        "request_type": "RECLAMO",
        "amount": "20.00",
        "detail": "Revisar el cobro",
        "expected_solution": "Confirmar el importe",
    }
    assert (await client.post(f"{root}/complaints", json=complaint)).status_code == 422
    complaint["mobile_phone"] = "(01) 234-5678"
    assert (await client.post(f"{root}/complaints", json=complaint)).status_code == 422
    complaint["mobile_phone"] = "987 654 321"
    assert (await client.post(f"{root}/complaints", json=complaint)).status_code == 201
    assert (await client.get(f"{root}/complaints")).status_code == 401
    response = await client.get(f"{root}/complaints", headers=admin_headers)
    assert response.json()["data"]["items"][0]["document_number"] == "01234567"
    assert response.json()["data"]["items"][0]["mobile_phone"] == "+51987654321"

    contact = {
        "name": "Cliente",
        "email": "demo@example.com",
        "subject": "Consulta",
        "message": "Hola",
    }
    assert (await client.post(f"{root}/contacts", json=contact)).status_code == 201
    assert (await client.get(f"{root}/contacts")).status_code == 401
    response = await client.get(f"{root}/contacts", headers=admin_headers)
    assert response.json()["data"]["items"][0]["message"] == "Hola"
