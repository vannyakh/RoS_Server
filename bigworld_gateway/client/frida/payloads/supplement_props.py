# READ-ONLY: for every on-sale supply box, the prop ids it can award (client's own pure
# helpers over local data tables). Writes JSON to OUT. No server call, no state change.
import sys
import json
su = sys.modules['supplement_utils']
res = {}
errs = {}
for sid in sorted(su.getAvailableSupplementDictByTime().keys()):
    for fn in ('getAllPossiblePropID', 'getSortedSupplementPropIDs'):
        try:
            v = getattr(su, fn)(sid)
            res.setdefault(str(sid), {})[fn] = list(v) if v is not None else None
        except Exception as e:
            errs['%s:%s' % (sid, fn)] = repr(e)[:120]
out = open(OUT, 'w')
out.write(json.dumps({'props': res, 'errors': errs}))
out.close()
