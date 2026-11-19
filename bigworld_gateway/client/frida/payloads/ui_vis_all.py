OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    for name, ui in all_ui.items():
        f.write('%s: isVisible=%r\n' % (name, getattr(ui, 'isVisible', lambda: 'N/A')()))
        p = getattr(ui, 'panel', None)
        if p:
            f.write('  panel.isVisible: %r\n' % getattr(p, 'isVisible', lambda: 'N/A')())
            f.write('  panel.getPosition: %r\n' % getattr(p, 'getPosition', lambda: 'N/A')())
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
