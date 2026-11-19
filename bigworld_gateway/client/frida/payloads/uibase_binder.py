OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import ui.UIBase as UIBase
    fn = getattr(UIBase.UIBase, '_add_btn_binder', None)
    f.write('fn: %r\n' % fn)
    if fn:
        co = fn.func_code
        f.write('names: %r\n' % list(co.co_names))
        f.write('consts: %r\n' % [c for c in co.co_consts if not isinstance(c, type(co))])
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
