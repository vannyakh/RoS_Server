# READ-ONLY: did the lobby avatar ImageView get a texture? Renderer / content sizes only (getters).
import sys

out = open(OUT, 'w')
ui = sys.modules['Globals'].uiMgr.UIMain
w = ui.p_profile.getChildByName('avatar')
for g in ('getVirtualRendererSize', 'getContentSize'):
    try:
        s = getattr(w, g)()
        out.write('%s = (%s, %s)\n' % (g, s.width, s.height))
    except Exception as e:
        out.write('%s: %r\n' % (g, e))
try:
    r = w.getVirtualRenderer()
    out.write('renderer %r\n' % (type(r).__name__,))
    for g in ('getTexture', 'getSpriteFrame'):
        if hasattr(r, g):
            out.write('  %s -> %r\n' % (g, getattr(r, g)()))
    t = r.getTexture() if hasattr(r, 'getTexture') else None
    if t is not None:
        out.write('  texture %r x %r path=%r\n' % (t.getPixelsWide(), t.getPixelsHigh(),
                                                   t.getPath() if hasattr(t, 'getPath') else None))
except Exception as e:
    out.write('renderer: %r\n' % (e,))
lvl = ui.p_profile.getChildByName('level')
out.write('level text %r\n' % (lvl.getString(),))
out.close()
