from unicodedata import normalize


def report_key(value: str) -> str:
    text = "".join(
        char for char in normalize("NFD", value.upper()) if not 0x300 <= ord(char) <= 0x36F
    )
    return " ".join(text.split())


ROOM_ROWS = {
    "INDIVIDUALES O SIMPLES": 24,
    "DOBLES Y MATRIMONIALES": 25,
    "SUITES (INCLUYE SALA)": 27,
    "TRIPLES": 28,
    "BUNGALOS (CASAS PEQUENAS)": 29,
}
COUNTRY_ROWS = {
    code: row
    for row, code in enumerate(
        "AR DE BO BR CA CO KR CR CL CN EC US ES FR NL IN IL IT JP MX PA GB RU CH TR UY VE".split(),
        46,
    )
}
REGION_ROWS = {
    name: row
    for row, name in enumerate(
        (
            "LIMA",
            "AMAZONAS",
            "ANCASH",
            "APURIMAC",
            "AREQUIPA",
            "AYACUCHO",
            "CAJAMARCA",
            "CUSCO",
            "HUANCAVELICA",
            "HUANUCO",
            "ICA",
            "JUNIN",
            "LA LIBERTAD",
            "LAMBAYEQUE",
            "LORETO",
            "MADRE DE DIOS",
            "MOQUEGUA",
            "PASCO",
            "PIURA",
            "PUNO",
            "SAN MARTIN",
            "TACNA",
            "TUMBES",
            "UCAYALI",
        ),
        46,
    )
}
REGION_ROWS["LIMA METROPOLITANA"] = 46

AFRICA = set(
    "AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG EH ER ET GA GH GM GN GQ GW KE KM LR LS LY "
    "MA MG ML MR MU MW MZ NA NE NG RE RW SC SD SH SL SN SO SS ST SZ TD TG TN TZ UG YT ZA ZM ZW".split()
)
OCEANIA = set(
    "AS AU CK FJ FM GU KI MH MP NC NF NR NU NZ PF PG PN PW SB TK TO TV UM VU WF WS".split()
)
ASIA = set(
    "AE AF AM AZ BD BH BN BT CY GE HK ID IQ IR JO KG KH KP KW KZ LA LB LK MM MN MO MV MY NP OM "
    "PH PK PS QA SA SG SY TH TJ TL TM TW UZ VN YE".split()
)
EUROPE = set(
    "AD AL AT AX BA BE BG BY CZ DK EE FI FO GG GI GR HR HU IE IM IS JE LI LT LU LV MC MD ME MK MT "
    "NO PL PT RO RS SE SI SJ SK SM UA VA XK".split()
)


def foreign_row(country_code: str) -> int:
    if country_code in COUNTRY_ROWS:
        return COUNTRY_ROWS[country_code]
    for codes, row in ((AFRICA, 73), (OCEANIA, 74), (ASIA, 76), (EUROPE, 77)):
        if country_code in codes:
            return row
    return 75


REASON_COLUMNS = {
    "D": ("VACACION", "RECRE", "OCIO", "EVENTO", "TURISMO"),
    "F": ("FAMILI", "AMIGO"),
    "H": ("EDUC", "FORMACION", "ESTUDIO"),
    "J": ("SALUD", "MEDIC"),
    "L": ("RELIG", "PEREGRIN"),
    "N": ("TRABAJO", "REMUNER"),
    "P": ("COMPRA",),
    "R": ("NEGOCIO", "PROFESIONAL"),
}


def reason_column(reason: str) -> str:
    key = report_key(reason)
    for column, words in REASON_COLUMNS.items():
        if any(word in key for word in words):
            return column
    return "T"
