# READ-ONLY: raw bytes of an appearance icon texture (PKM/ETC1) and its alpha companion.
import sys
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
cc = sys.modules.get('cc'); cf = sys.modules.get('C_file')
fu = cc.FileUtils.getInstance()
w('fu attrs=%r' % [n for n in dir(fu) if 'ile' in n or 'ata' in n][:40])
base = 'ui/images/dts_appearance/gunfull/img_wanjuqiang'
for p in (base + '.pkm', base + '.png.pkm', base + '_alpha.pkm', base + '.png@alpha', base + '_a.png', base + '.png_alpha'):
    try:
        r = cf.get_res_file(p, '')
        w('C_file %s -> %d %r' % (p, len(r), r[:16]))
    except Exception as e:
        w('C_file %s -> %r' % (p, e))
    try:
        w('exists %s=%r' % (p, fu.isFileExist(p)))
    except Exception as e:
        pass
out.close()
