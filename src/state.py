"""Load/save/prune the sent-state log used to dedup emails to one per site per local day."""
import json
from datetime import date, timedelta


def site_date_key(site_id, date_str):
    return f"{site_id}|{date_str}"


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


def prune_old(state, keep_days=14):
    cutoff = date.today() - timedelta(days=keep_days)
    pruned = {}
    for key, value in state.items():
        try:
            _, date_str = key.rsplit("|", 1)
            key_date = date.fromisoformat(date_str)
        except ValueError:
            pruned[key] = value  # malformed/legacy key, keep rather than silently drop data
            continue
        if key_date >= cutoff:
            pruned[key] = value
    return pruned
