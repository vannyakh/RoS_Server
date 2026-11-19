OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    b = getattr(w, 'binder', None)
    f.write('binder: %r\n' % b)
    if b:
        for k in dir(b):
            if not k.startswith('__'):
                f.write('  %s: %r\n' % (k, getattr(b, k)))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
