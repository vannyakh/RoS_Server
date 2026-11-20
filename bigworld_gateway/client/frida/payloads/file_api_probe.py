# READ-ONLY: find the client's file-loading API and try to read one UI icon by path.
import sys
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
for mn in ('C_file', 'C_ui', 'render', 'world'):
    m = sys.modules.get(mn)
    if m is not None:
        w('%s: %r' % (mn, [n for n in dir(m) if not n.startswith('__')][:80]))
PATH = 'ui/images/dts_item/package/icn_dts_guns_10.png'
cf = sys.modules.get('C_file')
for fn in ('get_file', 'read_file', 'open_file', 'find_file', 'file_exists', 'get_file_size'):
    f = getattr(cf, fn, None) if cf else None
    if f is None:
        continue
    for arg in (PATH, PATH.replace('/', '\\'), 'res/' + PATH):
        try:
            r = f(arg)
            w('%s(%r) -> %s %r' % (fn, arg, type(r).__name__, (r[:16] if isinstance(r, str) else r)))
        except Exception as e:
            w('%s(%r) failed %r' % (fn, arg, e))
out.close()
