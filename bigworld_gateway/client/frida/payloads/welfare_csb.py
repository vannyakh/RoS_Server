OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    f.write('CSB: %r\n' % getattr(w, 'CSB_PATH', getattr(w, '_csb_path', None)))
    f.write('w.__class__: %r\n' % (w.__class__,))
    f.write('w.__class__.__module__: %r\n' % (w.__class__.__module__,))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
