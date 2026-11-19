OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    uiMgr = Globals.uiMgr
    all_ui = getattr(uiMgr, '____all_ui__', getattr(uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    if w:
        f.write('w: %r\n' % w)
        for k in dir(w):
            if not k.startswith('__') and any(x in k.lower() for x in ['close', 'back', 'exit', 'leave', 'click', 'btn']):
                f.write('  %s\n' % k)
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
