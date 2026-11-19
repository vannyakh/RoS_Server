OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals, opcode
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    fn = w.onCloseTouch
    co = fn.func_code
    code = co.co_code
    i = 0
    while i < len(code):
        op = ord(code[i])
        opname = opcode.opname[op]
        i += 1
        arg = None
        if op >= opcode.HAVE_ARGUMENT:
            arg = ord(code[i]) + (ord(code[i+1]) << 8)
            i += 2
        f.write('%3d: %-20s %r\n' % (i, opname, arg))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
