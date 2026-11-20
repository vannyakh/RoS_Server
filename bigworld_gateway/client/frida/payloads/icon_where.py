# READ-ONLY: how the client resolves one appearance icon (plist atlas? other package?).
import sys
out = open(OUT, 'w')
cf = sys.modules.get('C_file')
P = 'ui/images/dts_appearance/gunfull/img_wanjuqiang.png'
for p in (P, P.replace('.png', '.plist'), P.replace('.png', '.pvr.ccz'), P.replace('.png', '.ktx'), 'ui/images/dts_appearance/gunfull.plist', 'res/' + P):
    try:
        r = cf.get_res_file(p, '')
        out.write('%s -> %d bytes %r\n' % (p, len(r), r[:8]))
    except Exception as e:
        out.write('%s -> %r\n' % (p, e))
for p in (P,):
    for fn in ('find_res_file', 'find_file_ex', 'get_file_ex', 'validate_res_file'):
        try:
            out.write('%s(%s) -> %r\n' % (fn, p, getattr(cf, fn)(p, '')))
        except Exception as e:
            out.write('%s -> %r\n' % (fn, e))
out.close()
