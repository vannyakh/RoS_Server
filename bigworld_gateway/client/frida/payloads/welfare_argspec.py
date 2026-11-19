OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals, inspect
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    fn = getattr(w, 'onCloseTouch', None)
    f.write('args: %s\n' % str(inspect.getargspec(fn)))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
