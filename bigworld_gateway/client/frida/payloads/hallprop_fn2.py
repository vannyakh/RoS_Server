# READ-ONLY: attributes of a lobby Prop object.
import sys
out = open(OUT, 'w')
mod = sys.modules.get('shared.lib.gametoolslib.properties')
d = mod.getDtsHallPropData(120920)
for n in dir(d):
    if n.startswith('__'): continue
    try: v = getattr(d, n)
    except Exception as e: v = 'err %r' % e
    if callable(v) and not isinstance(v, (str, unicode)): v = '<fn>'
    out.write('%s=%r\n' % (n, v if not hasattr(v, '__dict__') else type(v).__name__))
out.close()
