"""Sync the Google Form responses sheet into the SUBSCRIBERS_JSON secret.

Runs on its own schedule (not the hourly wind check) since subscribers don't
change often. The sheet is the source of truth: every run rebuilds the whole
SUBSCRIBERS_JSON secret from the current rows, in the order they were
submitted (Google Forms appends chronologically). Rows are processed with
"last submission wins" semantics per (site, person, named alert):

- A person can have several independent alerts on the same site (the
  "Nombre de la Alerta" question — e.g. "Alerta 1", "Alerta 2"). Each named
  alert is evaluated on its own: main.py sends a notification whenever ANY
  one of them qualifies, not only when all of a person's conditions hold
  at once (that AND behavior still applies *within* one named alert, for
  people who stack several layers — surface + altitude — into one alert).
- Resubmitting the same kind of layer (same kind+point+meters) under the
  same alert name REPLACES the earlier one — that's how you edit it.
- Choosing "Baja"/"Remover" clears that specific named alert only, leaving
  any other alerts the person has on that site untouched. A later "Alta"
  submission with the same name re-creates it.
- Submissions without an alert name (or before this feature existed) fall
  into a single unnamed alert per person+site, same behavior as before.

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


def loose(text):
    """Collapse spaces/underscores/hyphens so 'vicente_lopez' matches 'Vicente Lopez'."""
    normalized = normalize(text)
    for sep in ("_", "-", " "):
        normalized = normalized.replace(sep, "")
    return normalized


def match_site_id(raw_value, valid_site_ids):
    """The form's dropdown shows friendly labels like 'cerro_otto (Bariloche)' or
    'Vicente Lopez' — match loosely, ignoring case/accents/separators."""
    loose_value = loose(raw_value)
    for site_id in valid_site_ids:
        if loose(site_id) in loose_value:
            return site_id
    return None


def parse_kind(value):
    v = normalize(value)
    if v.startswith("agl"):
        return "agl"
    if v.startswith("msl"):
        return "msl"
    return "surface"


REMOVE_KEYWORDS = ("baja", "remover", "eliminar", "quitar", "borrar")
ORIGINAL_ALERT_KEYWORDS = ("sinnombre", "original", "yatenia", "notenia")


def parse_accion(value):
    v = normalize(value)
    return any(keyword in v for keyword in REMOVE_KEYWORDS)


def parse_alert_name(value):
    """The dropdown may offer an option meaning "my original, unnamed alert"
    (for people who subscribed before this question existed) — map that back
    to the empty string so it matches those legacy rows."""
    if any(keyword in loose(value) for keyword in ORIGINAL_ALERT_KEYWORDS):
        return ""
    return value


def build_layer(row, cols):
    kind = parse_kind(cell(row, cols["kind"]))
    point = parse_point(cell(row, cols["point"]))
    layer = {"point": point, "kind": kind}

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
    csv_url = os.environ["SHEET_CSV_URL"]

    valid_site_ids = {s["id"] for s in yaml.safe_load(SITES_PATH.read_text(encoding="utf-8"))["sites"]}

    rows = fetch_rows(csv_url)
    if not rows:
        print("No rows in sheet, nothing to sync")
        return

    headers_norm = [normalize(h) for h in rows[0]]
    cols = {
        "name": find_col(headers_norm, "nombre"),
        "email": find_col(headers_norm, "email"),
        "telegram": find_col(headers_norm, "telegram"),
        "accion": find_col(headers_norm, "accion") or find_col(headers_norm, "baja"),
        "alert_name": find_col(headers_norm, "alerta"),
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
    if cols["accion"] is None:
        print("AVISO: no hay columna 'Acción' en el formulario todavía — todas las filas se tratan como alta/edición, nadie se puede dar de baja por el formulario.")

    # key: (site_id, email-or-telegram, alert_name) -> {name, email,
    # telegram_chat_id, alert_name, layers: {signature: layer}}. Rows are
    # processed in sheet order (= chronological), so the last submission for
    # a given signature wins, and a "Baja" row wipes just that named alert.
    index = {}

    for row_num, row in enumerate(rows[1:], start=2):
        name = cell(row, cols["name"])
        email = cell(row, cols["email"]) or None
        telegram_raw = cell(row, cols["telegram"])
        telegram_chat_id = int(telegram_raw) if telegram_raw.isdigit() else None
        site_raw = cell(row, cols["site"])
        site_id = match_site_id(site_raw, valid_site_ids)
        is_baja = cols["accion"] is not None and parse_accion(cell(row, cols["accion"]))
        alert_name_raw = cell(row, cols["alert_name"]) if cols["alert_name"] is not None else ""
        alert_name = parse_alert_name(alert_name_raw)

        if site_id is None:
            print(f"[fila {row_num}] sitio {site_raw!r} no matchea ningún id de sites.yaml, se descarta")
            continue
        if not email and not telegram_chat_id:
            print(f"[fila {row_num}] sin email ni telegram_chat_id, se descarta")
            continue

        identity = email or f"tg:{telegram_chat_id}"
        key = (site_id, identity, alert_name)
        state = index.setdefault(
            key,
            {"name": name, "email": email, "telegram_chat_id": telegram_chat_id, "alert_name": alert_name, "layers": {}},
        )
        state["name"] = name  # keep the latest name too

        if is_baja:
            state["layers"].clear()
            print(f"[fila {row_num}] baja de {identity} en {site_id}" + (f" (alerta {alert_name!r})" if alert_name else ""))
            continue

        layer, error = build_layer(row, cols)
        if error:
            print(f"[fila {row_num}] {error}")
            continue

        signature = (layer["kind"], layer["point"], layer.get("meters"))
        state["layers"][signature] = layer

    subscribers_by_site = {}
    for (site_id, _identity, _alert_name), state in index.items():
        if not state["layers"]:
            continue
        subscriber = {"name": state["name"]}
        if state["email"]:
            subscriber["email"] = state["email"]
        if state["telegram_chat_id"]:
            subscriber["telegram_chat_id"] = state["telegram_chat_id"]
        if state["alert_name"]:
            subscriber["alert_name"] = state["alert_name"]
        subscriber["layers"] = [
            {**layer, "id": f"{layer['kind']}_{layer['point']}_{i}"}
            for i, layer in enumerate(state["layers"].values())
        ]
        subscribers_by_site.setdefault(site_id, []).append(subscriber)

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
