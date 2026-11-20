# READ-ONLY: find the hall (lobby) prop data accessor and sample one weapon skin and one cloth.
import sys
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
mod = sys.modules.get('shared.lib.gametoolslib.properties')
names = [n for n in dir(mod) if n.startswith('get') and ('Hall' in n or 'Appearance' in n or 'Supplement' in n or 'Mall' in n or 'Suit' in n or 'Theme' in n)]
w('fns=%r' % names[:80])
for fn in ('getHallPropData', 'getDtsHallPropData', 'getHallPropsData'):
    f = getattr(mod, fn, None)
    if f is None:
        continue
    for pid in (120920, 110985, 270000, 105987):
        try:
            d = f(pid)
            ks = list(d.keys()) if hasattr(d, 'keys') else []
            w('%s(%d) keys=%r' % (fn, pid, ks[:40]))
            for k in ('NAME', 'ICON_PATH', 'BIG_ICON_PATH', 'QUALITY', 'PROP_TYPE', 'DESC', 'BRIEF_DES'):
                try: w('   %s=%r' % (k, d[k] if not hasattr(d[k], '__class__') or isinstance(d[k], (str, unicode, int, long, float)) else type(d[k]).__name__))
                except Exception as e: w('   %s err %r' % (k, e))
        except Exception as e:
            w('%s(%d) failed %r' % (fn, pid, e))
out.close()
