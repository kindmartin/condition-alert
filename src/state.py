"""Load/save the ON/OFF alert-state log.

Each (site, subscriber+alert) pair has at most one entry, present only
while its condition is currently considered "on" (qualifying hours exist
somewhere in the rolling forecast window). There is no date in the key
anymore — an alert stays "on" across runs until the condition actually
stops qualifying, at which point its entry is removed and a "cleared"
notice is sent. This replaces the old once-per-calendar-day dedup.
"""
import json


def state_key(site_id, label):
    return f"{site_id}|{label}"


def load_state(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def prune_stale(state, valid_keys):
    """Drop entries for (site, subscriber+alert) pairs that no longer exist
    in SUBSCRIBERS_JSON — e.g. someone unsubscribed while their alert was on."""
    return {key: value for key, value in state.items() if key in valid_keys}
