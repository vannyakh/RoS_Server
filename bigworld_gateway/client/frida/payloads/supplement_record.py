# READ-ONLY: field values of a few local supply-box records, to match the shape the
# server reply must use (e.g. CURRENCY_ID). No server call, no state change.
import sys
out = open(OUT, 'w')
su = sys.modules['supplement_utils']
d = su.getAvailableSupplementDictByTime()
for sid in (1, 2, 5, 9728):
    o = d[sid]
    fields = {}
    for k in dir(o):
        if k.startswith('_') or not k.isupper():
            continue
        try:
            v = getattr(o, k)
        except Exception as e:
            v = 'ERR %r' % e
        if not callable(v):
            fields[k] = v
    out.write('%d %s %r\n' % (sid, type(o).__name__, fields))
    try:
        out.write('   currency type=%r\n' % (su.getSupplementCurrencyType(sid),))
    except Exception as e:
        out.write('   currency err %r\n' % e)
out.close()
