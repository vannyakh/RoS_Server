OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    a = all_ui.get('UIMainActionAndEmoji')
    f.write('UIMainActionAndEmoji: %r\n' % a)
    for k in dir(a):
        if not k.startswith('__') and not callable(getattr(a, k)):
            try:
                f.write('  %s: %r\n' % (k, getattr(a, k)))
            except: pass
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
