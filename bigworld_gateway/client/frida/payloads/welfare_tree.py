OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    w = all_ui.get('UILimitWelfareController')
    p = w.panel
    def dump_children(node, indent=0):
        if not node: return
        f.write(' '*indent + '%s: name=%r tag=%r pos=%r\n' % (type(node).__name__, getattr(node, 'getName', lambda: '')(), getattr(node, 'getTag', lambda: 0)(), getattr(node, 'getPosition', lambda: None)()))
        try:
            for c in node.getChildren():
                dump_children(c, indent+2)
        except: pass
    dump_children(p)
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
