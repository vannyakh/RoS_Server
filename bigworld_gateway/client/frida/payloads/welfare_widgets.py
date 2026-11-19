OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    fn = getattr(w, '_add_btn_binder', None)
    # Check widgets bound
    for k in dir(w):
        val = getattr(w, k)
        if hasattr(val, 'get_position') or hasattr(val, 'getPosition') or hasattr(val, 'getContentSize'):
            f.write('%s: %r pos=%r\n' % (k, val, getattr(val, 'getPosition', lambda: None)()))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
