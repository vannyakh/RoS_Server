OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    uiMgr = Globals.uiMgr
    all_ui = getattr(uiMgr, '____all_ui__', getattr(uiMgr, '_UIMgr____all_ui__', {}))
    for k, v in all_ui.items():
        vis = getattr(v, 'is_visible', None)
        if callable(vis): vis = vis()
        act = getattr(v, 'is_active', None)
        if callable(act): act = act()
        f.write('%s: vis=%r act=%r\n' % (k, vis, act))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
