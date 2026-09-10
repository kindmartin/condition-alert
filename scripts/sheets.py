"""Read rows from a Google Sheet published to the web as CSV.

No Google Cloud project, service account, or auth needed — the sheet owner
publishes it (File -> Share -> Publish to web -> CSV) and this just does a
plain HTTP GET, same as the Open-Meteo fetch.
"""
import csv
import io

import requests


def fetch_rows(csv_url):
    """Returns a list of rows (each a list of cell strings), first row is the header."""
    resp = requests.get(csv_url, timeout=30)
    resp.raise_for_status()
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
