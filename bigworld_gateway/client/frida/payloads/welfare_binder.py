OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals, dis, StringIO, sys
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    fn = getattr(w, '_add_btn_binder', None)
    if fn:
        buf = StringIO.StringIO()
        old = sys.stdout; sys.stdout = buf
        dis.dis(fn)
        sys.stdout = old
        f.write(buf.getvalue()[:2000])
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
