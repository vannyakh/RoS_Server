"""Reference copy of ros_server.load_accounts / save_account (as of RO-119),
with the module-level ACCOUNTS_FILE turned into a parameter. Used by the parity
tests and the benchmark. Do not import ros_server here: it has side effects."""

import json
import os


def load_accounts(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ACC] load_accounts error: {e}")
            return {}
    return {}


def save_account(path, key, data):
    accs = load_accounts(path)
    accs[str(key)] = data
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(accs, f, indent=2)
    except Exception as e:
        print(f"[ACC] save_account error: {e}")
