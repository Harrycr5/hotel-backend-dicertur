from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from pathlib import Path
from uuid import UUID

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.companies.models import Branch, Company
from app.modules.person.choices import PersonArea, PersonCategory, PersonGender
from app.modules.person.models import Person
from app.modules.reservations.choices import ReservationStatus
from app.modules.reservations.models import Reservation
from app.modules.reservations.schemas import PERU_TIME
from app.modules.rooms.choices import RoomStatus
from app.modules.rooms.models import Room
from app.modules.ubigee.models import Department, District, Province

from .classification import REGION_ROWS, ROOM_ROWS, foreign_row, reason_column, report_key
from .schemas import ReportPeriod

TEMPLATE = Path(__file__).with_name("templates") / "dircetur.xlsx"
STAY_STATUSES = (
    ReservationStatus.CONFIRMED,
    ReservationStatus.PARTIALLY_PAID,
    ReservationStatus.WITHOUT_PAYMENT,
)
CAPACITY_COLUMNS = ("D", "F", "H", "J", "L", "N", "P", "R")
STAFF_COLUMNS = ("G", "I", "K", "M", "O", "Q", "S")


@dataclass
class Counts:
    arrivals: int = 0
    guest_nights: int = 0


@dataclass
class RoomCounts(Counts):
    with_bath: int = 0
    without_bath: int = 0
    bed_places: int = 0
    occupied_nights: set[tuple[UUID, date]] = field(default_factory=set)
    rates_with_bath: list[Decimal] = field(default_factory=list)
    rates_without_bath: list[Decimal] = field(default_factory=list)


def peru_time(value: datetime) -> datetime:
    # PostgreSQL returns aware datetimes. SQLite test fixtures store UTC without offset.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(PERU_TIME)


def month_bounds(period: ReportPeriod) -> tuple[date, date]:
    month = int(period.month)
    return date(period.year, month, 1), date(period.year + (month == 12), month % 12 + 1, 1)


def reportable_stays(start: date, end: date, now: datetime):
    return select(Reservation).where(
        Reservation.status.in_(STAY_STATUSES),
        Reservation.is_active,
        Reservation.check_in < datetime.combine(end, time.min, PERU_TIME),
        Reservation.check_in <= now,
        Reservation.check_out > datetime.combine(start, time.min, PERU_TIME),
    )


def nights_in_period(
    check_in: datetime, check_out: datetime, start: date, end: date, now: datetime
) -> tuple[date, int]:
    local_start = max(start, peru_time(check_in).date())
    local_end = min(peru_time(check_out).date(), end, peru_time(now).date())
    return local_start, max(0, (local_end - local_start).days)


def write_cell(sheet: Worksheet, address: str, value) -> None:
    cell = sheet[address]
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"


def fill_company(sheet: Worksheet, company: Company, department: str, province: str, district: str):
    fields = {
        "C5": company.legal_name,
        "J5": company.ruc,
        "P5": company.lodging_class,
        "T5": company.category,
        "C6": company.trade_name,
        "T6": company.certificate_number,
        "C7": company.address,
        "C8": department,
        "H8": province,
        "L8": district,
        "C9": company.phone,
        "Q9": company.coordinate_system,
        "C10": company.website,
        "Q10": company.reservations_email,
        "C12": company.contact_name,
        "L12": company.contact_phone,
        "P12": company.contact_email,
        "C14": "SÍ" if company.national_hotel_chain else "NO",
        "L14": "SÍ" if company.international_hotel_chain else "NO",
    }
    for address, value in fields.items():
        write_cell(sheet, address, value if value is not None else "—")


def add_capacity(rows: dict[int, RoomCounts], rooms: list[Room]) -> None:
    for room in rooms:
        if room.status == RoomStatus.MAINTENANCE:
            continue
        room_type = room.room_type
        if room_type.has_bathroom is None or room_type.bed_places is None:
            raise ConflictError(
                f"Completa baño y plazas-cama del tipo «{room_type.name}» antes de generar el reporte."
            )
        counts = rows[ROOM_ROWS.get(report_key(room_type.name), 30)]
        counts.bed_places += room_type.bed_places
        prices = [rate.price for rate in room.rates if rate.is_active]
        if room_type.has_bathroom:
            counts.with_bath += 1
            if prices:
                counts.rates_with_bath.append(sum(prices) / len(prices))
        else:
            counts.without_bath += 1
            if prices:
                counts.rates_without_bath.append(sum(prices) / len(prices))


def rounded_rate(rates: list[Decimal]) -> int | None:
    if not rates:
        return None
    return int((sum(rates) / len(rates)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def write_capacity(sheet: Worksheet, rows: dict[int, RoomCounts], days: int) -> None:
    total = RoomCounts()
    for row, data in rows.items():
        values = (
            data.with_bath,
            data.without_bath,
            data.bed_places,
            data.arrivals,
            len(data.occupied_nights),
            data.guest_nights,
            rounded_rate(data.rates_with_bath),
            rounded_rate(data.rates_without_bath),
        )
        for column, value in zip(CAPACITY_COLUMNS, values, strict=True):
            sheet[f"{column}{row}"] = value
        total.with_bath += data.with_bath
        total.without_bath += data.without_bath
        total.bed_places += data.bed_places
        total.arrivals += data.arrivals
        total.guest_nights += data.guest_nights
        total.occupied_nights.update(data.occupied_nights)

    totals = (
        total.with_bath,
        total.without_bath,
        total.bed_places,
        total.arrivals,
        len(total.occupied_nights),
        total.guest_nights,
        rounded_rate([rate for data in rows.values() for rate in data.rates_with_bath]),
        rounded_rate([rate for data in rows.values() for rate in data.rates_without_bath]),
    )
    for column, value in zip(CAPACITY_COLUMNS, totals, strict=True):
        sheet[f"{column}31"] = value
    room_days = (total.with_bath + total.without_bath) * days
    bed_days = total.bed_places * days
    sheet["U29"] = len(total.occupied_nights) / room_days if room_days else None
    sheet["U30"] = total.guest_nights / bed_days if bed_days else None
    sheet["U31"] = total.guest_nights / total.arrivals if total.arrivals else None
    sheet["U29"].number_format = sheet["U30"].number_format = "0.00%"
    sheet["U31"].number_format = "0.00"


def write_daily_arrivals(sheet: Worksheet, arrivals: Counter[int], days: int) -> None:
    for day in range(1, 32):
        row = (36, 37, 39, 40)[(day - 1) // 8]
        col = 3 + 2 * ((day - 1) % 8)
        sheet.cell(row=row, column=col).value = arrivals[day] if day <= days else None
    sheet["Q40"] = sum(arrivals.values())


def write_origins(
    sheet: Worksheet, domestic: dict[int | None, Counts], foreign: dict[int, Counts]
) -> None:
    for groups, first, last, total_row, arrivals_col, nights_col in (
        (domestic, 46, 69, 70, "N", "P"),
        (foreign, 46, 77, 78, "E", "G"),
    ):
        for row in range(first, last + 1):
            counts = groups[row]
            sheet[f"{arrivals_col}{row}"] = counts.arrivals
            sheet[f"{nights_col}{row}"] = counts.guest_nights
        sheet[f"{arrivals_col}{total_row}"] = sum(counts.arrivals for counts in groups.values())
        sheet[f"{nights_col}{total_row}"] = sum(counts.guest_nights for counts in groups.values())
    sheet["N73"] = sheet["N70"].value + sheet["E78"].value
    sheet["P73"] = sheet["P70"].value + sheet["G78"].value


def write_reasons(sheet: Worksheet, reasons: dict[int, Counter[str]]) -> None:
    for column in ("D", "F", "H", "J", "L", "N", "P", "R", "T"):
        sheet[f"{column}86"] = reasons[86][column]
        sheet[f"{column}87"] = reasons[87][column]
        sheet[f"{column}88"] = reasons[86][column] + reasons[87][column]
    for row in (86, 87):
        sheet[f"B{row}"] = sum(reasons[row].values())
    sheet["B88"] = sheet["B86"].value + sheet["B87"].value


def write_staff(sheet: Worksheet, workers: list[Person]) -> None:
    counts = Counter()
    for worker in workers:
        if worker.category == PersonCategory.OWNER_OR_PARTNER:
            row = 99
        elif worker.category == PersonCategory.UNPAID:
            row = 100
        else:
            row = 95 if worker.gender == PersonGender.MASCULINE else 97
            row += int(not worker.is_permanent_employee)
        counts[row, worker.area] += 1
    for area, column in zip(PersonArea, STAFF_COLUMNS, strict=True):
        for row in range(95, 101):
            sheet[f"{column}{row}"] = counts[row, area]
        sheet[f"{column}101"] = sum(counts[row, area] for row in range(95, 101))
    for row in range(95, 102):
        sheet[f"E{row}"] = sum(sheet[f"{column}{row}"].value for column in STAFF_COLUMNS)


async def generate_report(
    session: AsyncSession, period: ReportPeriod, *, now: datetime | None = None
) -> bytes:
    start, end = month_bounds(period)
    now = now or datetime.now(PERU_TIME)
    next_instant = datetime.combine(end, time.min, PERU_TIME)
    companies = (
        await session.execute(
            select(Company, Department.name, Province.name, District.name)
            .join(District, District.code == Company.district_code)
            .join(Province, Province.code == District.province_code)
            .join(Department, Department.code == Province.department_code)
            .limit(2)
        )
    ).all()
    if not companies:
        raise NotFoundError("Registra un establecimiento antes de generar el reporte.")
    if len(companies) > 1 or len((await session.scalars(select(Branch.id).limit(2))).all()) > 1:
        raise ConflictError(
            "El inventario y el personal deben vincularse a su establecimiento para generar el reporte."
        )

    rooms = list(
        (
            await session.scalars(
                select(Room).options(joinedload(Room.room_type), selectinload(Room.rates))
            )
        ).all()
    )
    stays = (
        await session.scalars(
            reportable_stays(start, end, now).options(selectinload(Reservation.companions))
        )
    ).all()
    workers = list(
        (await session.scalars(select(Person).where(Person.created_at < next_instant))).all()
    )

    book = load_workbook(TEMPLATE)
    sheet = book.active
    month_name = period.month.label.upper()
    sheet["A1"] = f"REPORTE DE RESERVACIONES - MES {month_name} DE AÑO {period.year}"
    sheet["A34"] = f"CAPÍTULO III: NÚMERO DE ARRIBOS DE HUÉSPEDES POR DÍA DEL MES {month_name}"
    fill_company(sheet, *companies[0])

    room_rows = {row: RoomCounts() for row in (24, 25, 27, 28, 29, 30)}
    add_capacity(room_rows, rooms)
    room_lookup = {room.id: room for room in rooms}
    daily = Counter()
    domestic: dict[int | None, Counts] = defaultdict(Counts)
    foreign: dict[int, Counts] = defaultdict(Counts)
    reasons = {86: Counter(), 87: Counter()}
    for stay in stays:
        arrived = peru_time(stay.check_in).date()
        local_start, nights = nights_in_period(stay.check_in, stay.check_out, start, end, now)
        guests = 1 + len(stay.companions)
        arrivals = guests if start <= arrived < end else 0
        room_type = room_lookup[stay.room_id].room_type
        counts = room_rows[ROOM_ROWS.get(report_key(room_type.name), 30)]
        counts.arrivals += arrivals
        counts.guest_nights += nights * guests
        counts.occupied_nights.update(
            (stay.room_id, local_start + timedelta(days=n)) for n in range(nights)
        )
        if stay.country_code == "PE":
            origin = domestic[REGION_ROWS.get(report_key(stay.region))]
            reason_row = 87
        else:
            origin = foreign[foreign_row(stay.country_code)]
            reason_row = 86
        origin.arrivals += arrivals
        origin.guest_nights += nights * guests
        if arrivals:
            daily[arrived.day] += arrivals
            reasons[reason_row][reason_column(stay.travel_reason)] += arrivals

    days = (end - start).days
    write_capacity(sheet, room_rows, days)
    write_daily_arrivals(sheet, daily, days)
    write_origins(sheet, domestic, foreign)
    write_reasons(sheet, reasons)
    write_staff(sheet, workers)
    observations = [
        "La ocupación se estima con reservas elegibles cuya fecha de entrada ya pasó.",
        "Los acompañantes se clasifican con la residencia y el motivo del titular.",
        "La capacidad y las tarifas corresponden al inventario vigente. Las tarifas se promedian "
        "por habitación y se redondean al sol.",
        "El personal corresponde al registro del establecimiento, sin historial de bajas.",
    ]
    unmatched = domestic.get(None)
    if unmatched and (unmatched.arrivals or unmatched.guest_nights):
        observations.append(
            f"El subtotal de residentes incluye {unmatched.arrivals} arribos y "
            f"{unmatched.guest_nights} pernoctaciones sin una fila de región en la plantilla."
        )
    sheet["A105"] = "\n".join(observations)
    sheet.row_dimensions[105].height = 18 * len(observations)
    with BytesIO() as output:
        book.save(output)
        return output.getvalue()
