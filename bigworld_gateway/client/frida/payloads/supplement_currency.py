# READ-ONLY: each on-sale box's CURRENCY_OPTION class and plain fields (int or list),
# written as JSON so the gateway reply copies the client's own shapes. No state change.
import sys
import json
su = sys.modules['supplement_utils']
res = {}
for sid, o in su.getAvailableSupplementDictByTime().items():
    co = o.CURRENCY_OPTION
    f = {'_type': type(co).__name__}
    for k in dir(co):
        if k.startswith('_') or not k.isupper():
            continue
        v = getattr(co, k)
        if isinstance(v, (int, long, float, basestring, bool)) or (isinstance(v, (list, tuple)) and all(isinstance(x, (int, long, float)) for x in v)):
            f[k] = list(v) if isinstance(v, tuple) else v
        else:
            f[k] = 'OBJ ' + type(v).__name__
    res[str(sid)] = f
out = open(OUT, 'w')
out.write(json.dumps(res))
out.close()
