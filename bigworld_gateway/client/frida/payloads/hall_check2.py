OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Athlete, Globals
    go = Athlete.GameObject
    scene = go.Find('Scene')
    ss = scene.GetComponent('SceneSystem') if scene else None
    f.write('ss: %r\n' % ss)
    if ss:
        f.write('scene: %r\n' % getattr(ss, '_scene', None))
        for c in ['DoLoadNeoxScene', 'loadHallScene']:
            f.write('%s: %r\n' % (c, ss.isCoroutineRunning(c)))
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    f.write('all_ui: %r\n' % list(all_ui.keys()))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
