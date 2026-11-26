from datetime import date, datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app.modules.companies.models import Company
from app.modules.person.models import Person, PersonAssignment
from app.modules.reservations.models import Companion, Reservation
from app.modules.reservations.schemas import PERU_TIME
from app.modules.rooms.models import Floor, Rate, Room, RoomType
from app.modules.ubigee.models import Country, Department, District, Province


async def test_dircetur_download_validates_period_and_counts_across_months(
    client, db, admin_headers
):
    def instant(month, day, hour):
        return datetime(2024, month, day, hour, tzinfo=PERU_TIME)

    db.add_all([Country(code="PE", name="Perú"), Country(code="US", name="Estados Unidos")])
    await db.flush()
    db.add(Department(code="22", name="San Martín", country_code="PE"))
    await db.flush()
    db.add(Province(code="2201", name="Moyobamba", department_code="22"))
    await db.flush()
    db.add(District(code="220101", name="Moyobamba", province_code="2201"))
    await db.flush()
    floor = Floor(description="Primer piso")
    rate = Rate(name="Estándar", price=100)
    simple = RoomType(name="Individuales o simples", has_bathroom=True, bed_places=1)
    double = RoomType(name="Dobles y matrimoniales", has_bathroom=False, bed_places=2)
    db.add_all(
        [
            Company(
                ruc="20000000001",
                legal_name="Hotel de prueba",
                address="Prueba",
                district_code="220101",
            ),
            floor,
            rate,
            simple,
            double,
            Person(
                name="Personal",
                last_name="Prueba",
                document_type="SIN DOCUMENTO",
                mobile_phone="+51987654321",
                area="BAR",
                gender="FEMENINO",
                category="EMPLEADO",
                is_permanent_employee=False,
                employment_start_date=date(2024, 1, 1),
                assignments=[
                    PersonAssignment(
                        effective_from=date(2024, 1, 1),
                        area="RECEPCIÓN",
                        category="EMPLEADO",
                        is_permanent_employee=True,
                    ),
                    PersonAssignment(
                        effective_from=date(2024, 3, 1),
                        area="BAR",
                        category="EMPLEADO",
                        is_permanent_employee=False,
                    ),
                ],
                created_at=instant(1, 1, 0),
            ),
        ]
    )
    await db.flush()
    room = Room(name="Doble", code="101", floor_id=floor.id, room_type_id=double.id, rates=[rate])
    db.add_all(
        [
            room,
            Room(
                name="Simple", code="102", floor_id=floor.id, room_type_id=simple.id, rates=[rate]
            ),
        ]
    )
    await db.flush()
    guest = dict(
        room_id=room.id,
        rate_id=rate.id,
        document_type="SIN DOCUMENTO",
        full_name="Huésped",
        birth_date=date(1990, 1, 1),
        phone="+51987654321",
        email="guest@example.com",
        city="Moyobamba",
        region="San Martín",
        district="Moyobamba",
        address="Prueba",
        travel_reason="Visita familiar",
        dietary_restrictions="Ninguna",
        gender="FEMENINO",
    )
    db.add_all(
        [
            Reservation(
                **guest,
                country_code="PE",
                status="RESERVA SIN PAGOS",
                check_in=instant(1, 31, 15),
                check_out=instant(2, 2, 12),
            ),
            Reservation(
                **guest,
                country_code="US",
                status="RESERVA SIN PAGOS",
                check_in=instant(2, 29, 15),
                check_out=instant(3, 2, 12),
                companions=[
                    Companion(
                        document_type="DNI",
                        document_number="00000000",
                        full_name="Acompañante",
                        gender="MASCULINO",
                    )
                ],
            ),
            Reservation(
                **guest,
                country_code="PE",
                status="CANCELADO",
                check_in=instant(2, 5, 15),
                check_out=instant(2, 6, 12),
            ),
        ]
    )
    await db.commit()

    path = "/api/v1/reports/dircetur"
    assert (await client.get(path, headers=admin_headers, params={"month": "2"})).status_code == 422
    assert (await client.get(path, headers=admin_headers, params={"year": 2024})).status_code == 422
    months = await client.get("/api/v1/reports/months", headers=admin_headers)
    assert len(months.json()["data"]) == 12
    response = await client.get(path, headers=admin_headers, params={"month": "2", "year": 2024})
    assert response.status_code == 200, response.text
    assert "reporte-dircetur-2024-02.xlsx" in response.headers["content-disposition"]
    sheet = load_workbook(BytesIO(response.content), data_only=True).active
    expected = {
        "D31": 1,
        "F31": 1,
        "H31": 3,
        "J31": 2,
        "L31": 2,
        "N31": 3,
        "K40": 2,
        "M40": None,
        "Q40": 2,
        "E57": 2,
        "G57": 2,
        "P66": 1,
        "B88": 2,
        "F86": 2,
        "I97": 1,
        "E101": 1,
    }
    for address, value in expected.items():
        assert sheet[address].value == value, address
    assert sheet["U29"].value == pytest.approx(2 / (2 * 29))
    assert sheet["U30"].value == pytest.approx(3 / (3 * 29))
    assert sheet["U31"].value == 1.5
    assert sheet["L70"].value == "TOTAL DE PERUANOS Y RESIDENTES"
    assert "L70:M71" in sheet.merged_cells
    assert sheet["L72"].value is None
    assert sheet["A91"].border.bottom.style is None
    assert sheet["U91"].border.right.style is None
    assert sheet["A105"].alignment.wrap_text is True
    assert "\n" in sheet["A105"].value

    register_path = "/api/v1/reports/guest-register"
    assert (await client.get(register_path, headers=admin_headers)).status_code == 422
    response = await client.get(
        register_path, headers=admin_headers, params={"month": "2", "year": 2024}
    )
    assert response.status_code == 200, response.text
    assert "registro-huespedes-2024-02.xlsx" in response.headers["content-disposition"]
    register = load_workbook(BytesIO(response.content), data_only=True).active
    assert register.freeze_panes == "A5"
    assert register.sheet_view.pane.xSplit is None
    assert register["A5"].value == 1
    assert register["S5"].value == 0
    assert register["B7"].value == "Acompañante"
    assert register["C7"].value == 1
    assert register["G7"].value == "Visita familiar"
    assert register["U7"].value == 1
    assert register["T7"].value is None
    for row in register.iter_rows(min_row=5, max_row=7, min_col=1, max_col=22):
        for cell in row:
            for edge in (cell.border.left, cell.border.right, cell.border.top, cell.border.bottom):
                assert edge.style == "thin"
                assert edge.color.rgb == "FF404040"
    assert [register[f"{column}8"].value for column in ("S", "T", "U")] == [2, 2, 3]
