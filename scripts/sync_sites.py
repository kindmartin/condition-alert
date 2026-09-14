"""Sync the "Sitios propuestos" sheet into docs/sites.json.

The sheet is the single source of truth for sites now — nothing is
hardcoded in code or in a committed YAML file anymore. Every row with
Estado="Aprobado" becomes one site; rows are processed in sheet order so a
later approved row for the same Site ID replaces an earlier one (e.g. if
the admin corrects a coordinate and re-approves). To edit an already-
approved site, the admin just edits that same row in place — there's no
separate "site list" to keep in sync, this sheet IS the list.

Site ID and Timezone are optional in the sheet: if left blank, Site ID is
slugified from the site name and Timezone is looked up from the despegue
coordinates (via timezonefinder, fully offline). Filling them in by hand
still works, as a manual override.

The 9 sites that existed before this sheet became the source of truth were
one-time seeded into the sheet via the seedExistingSites() function in
docs/apps_script.gs — see MANUAL.md.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).parent))

from sheet_columns import cell, find_col, normalize, parse_float
from sheets import fetch_rows
from timezonefinder import TimezoneFinder

ROOT = Path(__file__).resolve().parent.parent
SITES_PATH = ROOT / "docs" / "sites.json"

APPROVED_KEYWORDS = ("aprobado", "approved")


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "sitio"


def valid_latlon(lat, lon):
    return -90 <= lat <= 90 and -180 <= lon <= 180


def sync(dry_run=False):
    csv_url = os.environ["SITES_SHEET_CSV_URL"]

    rows = fetch_rows(csv_url)
    if not rows:
        print("No rows in sheet, nothing to sync")
        return

    headers_norm = [normalize(h) for h in rows[0]]
    cols = {
        "estado": find_col(headers_norm, "estado"),
        "site_id": find_col(headers_norm, "site", "id"),
        "timezone": find_col(headers_norm, "timezone"),
        "name": find_col(headers_norm, "nombre", "sitio"),
        "despegue_lat": find_col(headers_norm, "despegue", "lat"),
        "despegue_lon": find_col(headers_norm, "despegue", "lon"),
        "despegue_elev": find_col(headers_norm, "despegue", "elev"),
        "tiene_aterrizaje": find_col(headers_norm, "tiene", "aterrizaje"),
        "aterrizaje_lat": find_col(headers_norm, "aterrizaje", "lat"),
        "aterrizaje_lon": find_col(headers_norm, "aterrizaje", "lon"),
        "aterrizaje_elev": find_col(headers_norm, "aterrizaje", "elev"),
    }
    missing = [k for k in cols if cols[k] is None]
    if missing:
        print(f"ERROR: no encontré columnas para {missing} en el encabezado {rows[0]}", file=sys.stderr)
        sys.exit(1)

    tf = TimezoneFinder()
    sites_by_id = {}  # last approved row per site_id wins (sheet order)
    used_slugs = {}  # auto-generated slug -> site name that claimed it (collision detection)

    for row_num, row in enumerate(rows[1:], start=2):
        estado = normalize(cell(row, cols["estado"]))
        if not any(keyword in estado for keyword in APPROVED_KEYWORDS):
            continue

        name = cell(row, cols["name"])

        despegue_lat = parse_float(cell(row, cols["despegue_lat"]))
        despegue_lon = parse_float(cell(row, cols["despegue_lon"]))
        despegue_elev = parse_float(cell(row, cols["despegue_elev"]))
        if None in (despegue_lat, despegue_lon, despegue_elev):
            print(f"[fila {row_num}] faltan datos de despegue para {name!r}, se descarta")
            continue
        if not valid_latlon(despegue_lat, despegue_lon):
            print(f"[fila {row_num}] coordenadas de despegue fuera de rango ({despegue_lat}, {despegue_lon}) para {name!r}, se descarta")
            continue

        site_id = cell(row, cols["site_id"])
        if not site_id:
            base_slug = slugify(name or f"sitio_fila_{row_num}")
            site_id = base_slug
            suffix = 2
            while site_id in used_slugs and used_slugs[site_id] != name:
                site_id = f"{base_slug}_{suffix}"
                suffix += 1
            used_slugs[site_id] = name

        timezone_override = cell(row, cols["timezone"])
        timezone = None
        if timezone_override:
            try:
                ZoneInfo(timezone_override)
                timezone = timezone_override
            except (ZoneInfoNotFoundError, ValueError):
                print(f"[fila {row_num}] timezone {timezone_override!r} inválido para site_id {site_id!r}, se calcula desde coordenadas")
        if timezone is None:
            timezone = tf.timezone_at(lat=despegue_lat, lng=despegue_lon)
        if timezone is None:
            print(f"[fila {row_num}] no se pudo determinar timezone para site_id {site_id!r}, se descarta")
            continue

        points = {"launch": {"lat": despegue_lat, "lon": despegue_lon, "elevation_m": despegue_elev}}

        tiene_aterrizaje = normalize(cell(row, cols["tiene_aterrizaje"])) in ("si", "sí", "yes", "true")
        if tiene_aterrizaje:
            landing_lat = parse_float(cell(row, cols["aterrizaje_lat"]))
            landing_lon = parse_float(cell(row, cols["aterrizaje_lon"]))
            landing_elev = parse_float(cell(row, cols["aterrizaje_elev"]))
            if None in (landing_lat, landing_lon, landing_elev):
                print(f"[fila {row_num}] 'Tiene aterrizaje' pero faltan sus coordenadas, se omite el punto landing")
            elif not valid_latlon(landing_lat, landing_lon):
                print(f"[fila {row_num}] coordenadas de aterrizaje fuera de rango ({landing_lat}, {landing_lon}) para site_id {site_id!r}, se omite el punto landing")
            else:
                points["landing"] = {"lat": landing_lat, "lon": landing_lon, "elevation_m": landing_elev}

        sites_by_id[site_id] = {
            "id": site_id,
            "name": name or site_id,
            "timezone": timezone,
            "points": points,
        }

    sites = [sites_by_id[k] for k in sorted(sites_by_id)]
    print(f"Sitios aprobados encontrados: {len(sites)} -> {[s['id'] for s in sites]}")

    payload = json.dumps(sites, ensure_ascii=False, indent=2) + "\n"

    if dry_run:
        print("\n--dry-run: no se escribe docs/sites.json. Contenido que se hubiera escrito:\n")
        print(payload)
        return

    if not sites:
        print("ERROR: 0 sitios aprobados — no piso docs/sites.json con una lista vacía por las dudas.", file=sys.stderr)
        sys.exit(1)

    SITES_PATH.write_text(payload, encoding="utf-8")
    print(f"\n{SITES_PATH} actualizado")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sync(dry_run=args.dry_run)
