OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    p = w.panel
    for m in dir(p):
        if 'path' in m.lower() or 'child' in m.lower() or 'find' in m.lower():
            f.write('%s\n' % m)
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
