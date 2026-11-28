# READ-ONLY: which built-in portrait sprite frames the client has (SpriteFrameCache lookups only).
import sys

out = open(OUT, 'w')
import cc
cache = cc.SpriteFrameCache.getInstance()
found = []
for c in list(range(1, 40)) + list(range(10001, 10010)) + list(range(20001, 20010)) + list(range(30001, 30010)):
    for fmt in ('ui/images/avatar/portrait/%d_on.png', 'avatar/portrait/%d_on.png', '%d_on.png'):
        name = fmt % c
        try:
            if cache.getSpriteFrame(name) is not None:
                found.append(name)
        except Exception as e:
            out.write('%s: %r\n' % (name, e))
            break
out.write('frames: %r\n' % (found,))
for n in ('getSpriteFrames', 'getSpriteFrameNames', 'getAllSpriteFrameNames'):
    out.write('cache has %s: %r\n' % (n, hasattr(cache, n)))
ru = sys.modules.get('role_utils') or sys.modules.get('hero_utils')
out.write('role module: %r\n' % (ru,))
out.close()
