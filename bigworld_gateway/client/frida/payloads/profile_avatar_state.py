# READ-ONLY: state of the lobby profile avatar widget (UIMain p_profile/avatar) and whether the built-in
# portrait files exist in the game's resources. Only getters and file-exists checks, no game method.
import sys

out = open(OUT, 'w')
try:
    import BigWorld
    p = BigWorld.player()
    out.write('portrait=%r char=%r headFrameTag=%r\n' % (p.portrait, p.baseCharacterType, p.headFrameTag))
except Exception as e:
    out.write('player: %r\n' % (e,))

G = sys.modules.get('Globals')
ui = None
try:
    mgr = G.uiMgr
    for name in ('UIMain',):
        ui = getattr(mgr, name, None)
        out.write('uiMgr.%s = %r\n' % (name, type(ui).__name__))
except Exception as e:
    out.write('uiMgr: %r\n' % (e,))
try:
    prof = ui.p_profile
    out.write('p_profile %r\n' % (type(prof).__name__,))
    for child in ('avatar', 'img_frame', 'mask', 'level'):
        w = prof.getChildByName(child)
        out.write('  child %s -> %r visible=%r\n' % (child, type(w).__name__, w.isVisible() if w else None))
        for getter in ('getRenderFile', 'getTextureFile', 'getFileName'):
            if w is not None and hasattr(w, getter):
                try:
                    out.write('    %s() = %r\n' % (getter, getattr(w, getter)()))
                except Exception as e:
                    out.write('    %s: %r\n' % (getter, e))
except Exception as e:
    out.write('widget: %r\n' % (e,))

cu = sys.modules.get('client_utils')
out.write('AVATAR_PORTRAIT_RES_PATH_PREFIX=%r portraitPlistLoaded=%r\n' % (
    getattr(cu, 'AVATAR_PORTRAIT_RES_PATH_PREFIX', None), getattr(cu, 'portraitPlistLoaded', None)))
paths = ['ui/images/avatar/portrait/%d_on.png' % c for c in (20001, 20002, 10001, 10002, 1, 2, 30001)]
checks = []
for modname in ('C_file', 'game3d', 'neox_file', 'cocosui'):
    m = sys.modules.get(modname)
    if m is not None:
        for fn in ('find_file', 'file_exists', 'isFileExist', 'exists'):
            if hasattr(m, fn):
                checks.append(('%s.%s' % (modname, fn), getattr(m, fn)))
try:
    import cc
    fu = cc.FileUtils.getInstance()
    checks.append(('cc.FileUtils.isFileExist', fu.isFileExist))
except Exception as e:
    out.write('cc.FileUtils: %r\n' % (e,))
for label, fn in checks:
    for pth in paths:
        try:
            out.write('%s(%s) = %r\n' % (label, pth, fn(pth)))
        except Exception as e:
            out.write('%s(%s): %r\n' % (label, pth, e))
out.close()
