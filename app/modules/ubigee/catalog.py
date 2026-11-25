import json
from pathlib import Path

DATA_PATH = Path(__file__).with_name("data")
CATALOG_PATH = DATA_PATH / "ubigeos-peru-inei-2026.json"
COUNTRIES_PATH = DATA_PATH / "countries.json"


def catalog_rows():
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    countries = json.loads(COUNTRIES_PATH.read_text(encoding="utf-8-sig"))
    country_code = catalog["metadata"]["pais"]
    return (
        countries,
        [
            {"code": row["codigo"], "name": row["nombre"], "country_code": country_code}
            for row in catalog["departamentos"]
        ],
        [
            {
                "code": row["codigo"],
                "name": row["nombre"],
                "department_code": row["departamento_codigo"],
            }
            for row in catalog["provincias"]
        ],
        [
            {
                "code": row["codigo"],
                "name": row["nombre"],
                "province_code": row["provincia_codigo"],
            }
            for row in catalog["distritos"]
        ],
    )
