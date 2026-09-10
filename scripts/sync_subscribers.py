"""Sync the Google Form responses sheet into the SUBSCRIBERS_JSON secret.

Runs on its own schedule (not the hourly wind check) since subscribers don't
change often. The sheet is the source of truth: every run rebuilds the whole
SUBSCRIBERS_JSON secret from the current rows, matching rows to the same
person+site by email/telegram_chat_id and merging their layers together (so
someone can fill the form more than once for the same site to add layers).

Column headers are matched by keyword, not exact text, so small wording
edits in the Google Form don't break this (see find_col below).
"""
import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from github_secret import set_secret
from sheets import fetch_rows

ROOT = Path(__file__).resolve().parent.parent
SITES_PATH = ROOT / "config" / "sites.yaml"


def normalize(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def find_col(headers_norm, *keywords):
    for i, header in enumerate(headers_norm):
        if all(keyword in header for keyword in keywords):
            return i
    return None


def cell(row, index):
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def parse_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_point(value):
    v = normalize(value)
    if "aterrizaje" in v:
        return "landing"
    return "launch"


def match_site_id(raw_value, valid_site_ids):
    """The form's dropdown shows friendly labels like 'cerro_otto (Bariloche)' —
    match as long as a known site id appears anywhere in the answer."""
    normalized = normalize(raw_value)
    for site_id in valid_site_ids:
        if normalize(site_id) in normalized:
            return site_id
    return None


def parse_kind(value):
    v = normalize(value)
    if v.startswith("agl"):
        return "agl"
    if v.startswith("msl"):
        return "msl"
    return "surface"


def build_layer(row, cols, index):
    kind = parse_kind(cell(row, cols["kind"]))
    point = parse_point(cell(row, cols["point"]))
    layer = {"id": f"{kind}_{point}_{index}", "point": point, "kind": kind}

    if kind != "surface":
        meters = parse_float(cell(row, cols["meters"]))
        if meters is None:
            return None, f"capa {kind} sin 'metros', se descarta"
        layer["meters"] = meters

    min_speed = parse_float(cell(row, cols["min_speed"]))
    max_speed = parse_float(cell(row, cols["max_speed"]))
    if min_speed is not None:
        layer["min_speed_kmh"] = min_speed
    if max_speed is not None:
        layer["max_speed_kmh"] = max_speed

    gust = parse_float(cell(row, cols["gust"]))
    if gust is not None and kind == "surface":
        layer["max_gust_kmh"] = gust

    dir_min = parse_float(cell(row, cols["dir_min"]))
    dir_max = parse_float(cell(row, cols["dir_max"]))
    if dir_min is not None and dir_max is not None:
        layer["directions"] = [{"min_deg": dir_min, "max_deg": dir_max}]

    return layer, None


def sync(dry_run=False):
    sheet_id = os.environ["SHEET_ID"]
    service_account_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

    valid_site_ids = {s["id"] for s in yaml.safe_load(SITES_PATH.read_text(encoding="utf-8"))["sites"]}

    rows = fetch_rows(sheet_id, service_account_json)
    if not rows:
        print("No rows in sheet, nothing to sync")
        return

    headers_norm = [normalize(h) for h in rows[0]]
    cols = {
        "name": find_col(headers_norm, "nombre"),
        "email": find_col(headers_norm, "email"),
        "telegram": find_col(headers_norm, "telegram"),
        "site": find_col(headers_norm, "sitio"),
        "point": find_col(headers_norm, "referencia"),
        "kind": find_col(headers_norm, "capa"),
        "meters": find_col(headers_norm, "metros"),
        "min_speed": find_col(headers_norm, "velocidad", "minima"),
        "max_speed": find_col(headers_norm, "velocidad", "maxima"),
        "gust": find_col(headers_norm, "rafaga"),
        "dir_min": find_col(headers_norm, "direccion", "minima"),
        "dir_max": find_col(headers_norm, "direccion", "maxima"),
    }
    missing = [k for k in ("name", "email", "site", "point", "kind") if cols[k] is None]
    if missing:
        print(f"ERROR: no encontré columnas para {missing} en el encabezado {rows[0]}", file=sys.stderr)
        sys.exit(1)

    subscribers_by_site = {}
    # key: (site_id, email or telegram) -> subscriber dict, so repeat submissions
    # from the same person for the same site merge their layers together.
    index = {}

    for row_num, row in enumerate(rows[1:], start=2):
        name = cell(row, cols["name"])
        email = cell(row, cols["email"]) or None
        telegram_raw = cell(row, cols["telegram"])
        telegram_chat_id = int(telegram_raw) if telegram_raw.isdigit() else None
        site_raw = cell(row, cols["site"])
        site_id = match_site_id(site_raw, valid_site_ids)

        if site_id is None:
            print(f"[fila {row_num}] sitio {site_raw!r} no matchea ningún id de sites.yaml, se descarta")
            continue
        if not email and not telegram_chat_id:
            print(f"[fila {row_num}] sin email ni telegram_chat_id, se descarta")
            continue

        layer, error = build_layer(row, cols, row_num)
        if error:
            print(f"[fila {row_num}] {error}")
            continue

        key = (site_id, email or f"tg:{telegram_chat_id}")
        if key not in index:
            subscriber = {"name": name}
            if email:
                subscriber["email"] = email
            if telegram_chat_id:
                subscriber["telegram_chat_id"] = telegram_chat_id
            subscriber["layers"] = []
            index[key] = subscriber
            subscribers_by_site.setdefault(site_id, []).append(subscriber)
        index[key]["layers"].append(layer)

    total = sum(len(v) for v in subscribers_by_site.values())
    print(f"Suscriptores encontrados: {total} en {len(subscribers_by_site)} sitio(s)")
    for site_id, subs in subscribers_by_site.items():
        print(f"  {site_id}: {[s.get('email') or s.get('telegram_chat_id') for s in subs]}")

    payload = json.dumps(subscribers_by_site, ensure_ascii=False)

    if dry_run:
        print("\n--dry-run: no se actualiza el secret. JSON que se hubiera escrito:\n")
        print(json.dumps(subscribers_by_site, ensure_ascii=False, indent=2))
        return

    token = os.environ["GH_PAT_FOR_SECRETS"]
    repo = os.environ["GITHUB_REPOSITORY"]
    set_secret(repo, "SUBSCRIBERS_JSON", payload, token)
    print(f"\nSecret SUBSCRIBERS_JSON actualizado en {repo}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sync(dry_run=args.dry_run)
