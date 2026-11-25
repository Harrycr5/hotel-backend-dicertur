from collections import Counter
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.modules.reservations.models import Reservation
from app.modules.reservations.schemas import PERU_TIME
from app.modules.rooms.models import Room
from app.modules.ubigee.models import Country

from .classification import report_key
from .schemas import ReportPeriod
from .service import month_bounds, nights_in_period, peru_time, reportable_stays, write_cell

TEMPLATE = Path(__file__).with_name("templates") / "guest_register.xlsx"
GUEST_GRID_SIDE = Side(style="thin", color="FF404040")
GRID = Border(
    left=GUEST_GRID_SIDE, right=GUEST_GRID_SIDE, top=GUEST_GRID_SIDE, bottom=GUEST_GRID_SIDE
)


async def generate_guest_register(
    session: AsyncSession, period: ReportPeriod, *, now: datetime | None = None
) -> bytes:
    start, end = month_bounds(period)
    now = now or datetime.now(PERU_TIME)
    stays = (
        await session.scalars(
            reportable_stays(start, end, now)
            .options(
                joinedload(Reservation.room).joinedload(Room.room_type),
                joinedload(Reservation.rate),
                joinedload(Reservation.detail),
                selectinload(Reservation.companions),
            )
            .order_by(Reservation.check_in, Reservation.id)
        )
    ).all()
    countries = dict((await session.execute(select(Country.code, Country.name))).all())
    book = load_workbook(TEMPLATE)
    sheet = book.active
    sheet["A1"] = f"REGISTRO MENSUAL DE HUÉSPEDES - {period.month.label.upper()} {period.year}"
    sheet.freeze_panes = "A5"
    totals = Counter()
    counted_room_nights = set()
    row = 5
    for stay in stays:
        arrival = peru_time(stay.check_in).date()
        departure = peru_time(stay.check_out).date()
        first_night, nights = nights_in_period(stay.check_in, stay.check_out, start, end, now)
        arrivals = int(start <= arrival < end)
        if not (arrivals or nights):
            continue
        room_nights = {
            (stay.room_id, first_night + timedelta(days=offset)) for offset in range(nights)
        }
        occupied = len(room_nights - counted_room_nights)
        counted_room_nights.update(room_nights)
        price = stay.detail.unit_rate if stay.detail else stay.rate.price
        for index, guest in enumerate((stay, *stay.companions)):
            gender = report_key(stay.gender) if index == 0 else ""
            male = int(gender in {"M", "MASCULINO", "HOMBRE"})
            female = int(gender in {"F", "FEMENINO", "MUJER"})
            notes = []
            if index:
                notes.append("Acompañante. Residencia y motivo según el titular.")
            elif stay.notes:
                notes.append(stay.notes)
            if not (male or female):
                notes.append("Sexo sin dato.")
            if not arrivals:
                notes.append("Ingreso en un mes anterior.")
            values = (
                row - 4,
                guest.full_name,
                male or None,
                female or None,
                countries.get(stay.country_code, stay.country_code),
                stay.region,
                stay.travel_reason,
                guest.document_type.value,
                guest.document_number,
                arrival.day,
                arrival.month,
                arrival.year,
                departure.day,
                departure.month,
                departure.year,
                stay.room.code,
                stay.room.room_type.name,
                price if index == 0 else None,
                arrivals,
                occupied if index == 0 else None,
                nights,
                " ".join(notes) or None,
            )
            if row == 5:
                sheet.unmerge_cells("A5:B5")
                footer = [cell._style for cell in sheet[5]]
                for cell in sheet[5]:
                    cell._style = None
            for column, value in enumerate(values, 1):
                write_cell(sheet, f"{get_column_letter(column)}{row}", value)
                cell = sheet.cell(row, column)
                cell.border = GRID
                cell.alignment = Alignment(
                    horizontal="left" if column in {2, 5, 6, 7, 8, 9, 16, 17, 22} else "center",
                    vertical="center",
                    wrap_text=True,
                )
                if column in {10, 11, 13, 14}:
                    cell.number_format = "00"
                elif column == 18:
                    cell.number_format = "0.00"
            sheet.row_dimensions[row].height = (
                30 if not notes else max(30, 15 * ((len(values[-1]) + 32) // 33))
            )
            totals.update(
                {3: male, 4: female, 19: arrivals, 20: occupied if index == 0 else 0, 21: nights}
            )
            row += 1
    if row > 5:
        for column, style in enumerate(footer, 1):
            sheet.cell(row, column)._style = style
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        sheet.cell(row, 1, "SUMATORIA TOTAL")
    for column in (3, 4, 19, 20, 21):
        sheet.cell(row, column).value = totals[column]
    sheet.print_area = f"A1:V{row}"
    sheet.print_title_rows = "1:4"
    sheet.page_setup.orientation = "landscape"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    with BytesIO() as output:
        book.save(output)
        return output.getvalue()
