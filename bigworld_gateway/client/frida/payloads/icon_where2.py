# READ-ONLY: resolve an appearance icon through cocos FileUtils / sprite frame cache.
import sys
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
cc = sys.modules.get('cc')
P = 'ui/images/dts_appearance/gunfull/img_wanjuqiang.png'
fu = cc.FileUtils.getInstance()
for p in (P, 'img_wanjuqiang.png', 'dts_appearance/gunfull/img_wanjuqiang.png'):
    try:
        full = fu.fullPathForFilename(p)
        w('full(%s)=%r exists=%r' % (p, full, fu.isFileExist(p)))
    except Exception as e:
        w('full(%s) err %r' % (p, e))
for meth in ('getDataFromFile', 'getStringFromFile'):
    try:
        r = getattr(fu, meth)(P)
        w('%s -> %s len %s head %r' % (meth, type(r).__name__, len(r) if r else 0, r[:8] if r else r))
    except Exception as e:
        w('%s err %r' % (meth, e))
sfc = cc.SpriteFrameCache.getInstance()
for p in (P, 'img_wanjuqiang.png'):
    try:
        w('frame(%s)=%r' % (p, sfc.getSpriteFrame(p)))
    except Exception as e:
        w('frame err %r' % e)
try:
    w('searchPaths=%r' % (fu.getSearchPaths(),))
except Exception as e:
    w('searchPaths err %r' % e)
out.close()
