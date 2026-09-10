"""Read rows from a Google Sheet using a service account (no OAuth flow, no
manual token refresh — google-auth handles minting a short-lived access
token from the service account's private key)."""
import json

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_}"


def get_access_token(service_account_json):
    info = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    credentials.refresh(Request())
    return credentials.token


def fetch_rows(sheet_id, service_account_json, range_="A:Z"):
    """Returns a list of rows (each a list of cell strings), first row is the header."""
    token = get_access_token(service_account_json)
    resp = requests.get(
        SHEETS_API.format(sheet_id=sheet_id, range_=range_),
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("values", [])
