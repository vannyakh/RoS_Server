OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    uiMgr = Globals.uiMgr
    all_ui = getattr(uiMgr, '____all_ui__', getattr(uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    if w:
        f.write('w.panel: %r\n' % getattr(w, 'panel', None))
        for k in ['btn_close', 'close_btn', 'bg', 'mask', 'root', 'panel']:
            f.write('%s: %r\n' % (k, getattr(w, k, None)))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
