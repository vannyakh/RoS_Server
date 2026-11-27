# READ-ONLY: dump client item-convert table helpers and one sample entry shape for gateway replies.
# Run while the Convert UI is open; compare with bigworld_gateway/server/athlete_requests.convert_entry.
import json
import sys

out = open(OUT, "w")


def dump(name, obj):
    out.write(f"{name} type={type(obj).__name__}\n")
    if isinstance(obj, dict):
        for k in sorted(obj.keys())[:5]:
            v = obj[k]
            out.write(f"  key {k!r} -> {type(v).__name__}\n")
            if isinstance(v, dict):
                out.write(f"    subkeys={sorted(v.keys())[:20]!r}\n")


for mod_name in (
    "item_convert_utils",
    "dts_item_convert_utils",
    "dts_appearance_convert_utils",
):
    mod = sys.modules.get(mod_name)
    if mod is None:
        continue
    for attr in dir(mod):
        if "Convert" in attr or "convert" in attr:
            try:
                val = getattr(mod, attr)
            except Exception:
                continue
            if callable(val):
                out.write(f"{mod_name}.{attr} callable\n")
            else:
                dump(f"{mod_name}.{attr}", val)

out.write(json.dumps({"done": True}) + "\n")
out.close()