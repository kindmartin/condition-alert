"""Update a GitHub Actions repository secret via the REST API.

GitHub requires the secret value to be encrypted client-side with the repo's
own public key (libsodium sealed box) before it's sent over the API — a
plain PUT with the raw value is rejected.
"""
import base64

import requests
from nacl import encoding, public

API_ROOT = "https://api.github.com"


def _encrypt(public_key_b64, secret_value):
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def set_secret(repo, secret_name, secret_value, token):
    """repo is 'owner/name'; token needs the repo's 'Secrets: Read and write' permission."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    key_resp = requests.get(f"{API_ROOT}/repos/{repo}/actions/secrets/public-key", headers=headers, timeout=30)
    key_resp.raise_for_status()
    key_data = key_resp.json()

    encrypted_value = _encrypt(key_data["key"], secret_value)

    put_resp = requests.put(
        f"{API_ROOT}/repos/{repo}/actions/secrets/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": key_data["key_id"]},
        timeout=30,
    )
    put_resp.raise_for_status()
