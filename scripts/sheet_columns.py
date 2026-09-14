"""Shared helpers for matching Google Sheet columns by keyword instead of
exact header text or position — used by both sync_subscribers.py and
sync_sites.py so a wording tweak in a form question doesn't break parsing."""
import unicodedata


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
