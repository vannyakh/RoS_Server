# READ-ONLY: path hash and two-argument file reads for one UI icon.
import sys
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
cf = sys.modules.get('C_file')
P = 'ui/images/dts_item/package/icn_dts_guns_10.png'
for arg in (P, P.replace('/', chr(92)), 'res/' + P):
    try:
        w('string_id(%r) = %r' % (arg, cf.string_id(arg)))
    except Exception as e:
        w('string_id(%r) failed %r' % (arg, e))
for fn, args in (('get_res_file', (P,)), ('get_res_file', (P, '')), ('get_file', (P, '')), ('get_file', ('', P)), ('find_file', (P, '')), ('get_file_info', (P,)), ('get_file_info', (P, ''))):
    try:
        r = getattr(cf, fn)(*args)
        w('%s%r -> %s len=%s head=%r' % (fn, args, type(r).__name__, len(r) if hasattr(r, '__len__') else '-', r[:12] if isinstance(r, str) else r))
    except Exception as e:
        w('%s%r failed %r' % (fn, args, e))
out.close()
