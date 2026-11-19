OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Athlete, Globals
    go = Athlete.GameObject
    scene = go.Find('Scene')
    ss = scene.GetComponent('SceneSystem') if scene else None
    if ss:
        for k in dir(ss):
            if not k.startswith('__'):
                try:
                    v = getattr(ss, k)
                    if not callable(v):
                        f.write('ss.%s: %r\n' % (k, v))
                except: pass
    import BigWorld
    p = BigWorld.player()
    f.write('player: %r\n' % p)
    if p:
        f.write('p.dtsInGameActionAppearanceIDs: %r\n' % (getattr(p, 'dtsInGameActionAppearanceIDs', 'MISSING')[:5] if hasattr(p, 'dtsInGameActionAppearanceIDs') else 'MISSING'))
        f.write('p.dtsEmojiList count: %r\n' % (len(getattr(p, 'dtsEmojiList', []))))
        f.write('p.dtsInGameActionSuitAppearanceIDs count: %r\n' % (len(getattr(p, 'dtsInGameActionSuitAppearanceIDs', [])) if hasattr(p, 'dtsInGameActionSuitAppearanceIDs') else 'MISSING'))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
