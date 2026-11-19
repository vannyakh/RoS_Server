OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    a = all_ui.get('UIMainActionAndEmoji')
    ip = a.itempanel
    f.write('itempanel pos: %r\n' % (getattr(ip, 'getPosition', lambda: None)()))
    f.write('itempanel wp: %r\n' % (getattr(ip, 'getWorldPosition', lambda: None)()))
    f.write('itempanel size: %r\n' % (getattr(ip, 'getContentSize', lambda: None)()))
    f.write('itempanel isVisible: %r\n' % (getattr(ip, 'isVisible', lambda: None)()))
    f.write('node pos: %r\n' % getattr(a.panel, 'getPosition', lambda: None)())
    # Check parent
    p = ip.getParent()
    f.write('parent: %r pos=%r wp=%r\n' % (p, getattr(p, 'getPosition', lambda: None)(), getattr(p, 'getWorldPosition', lambda: None)()))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
