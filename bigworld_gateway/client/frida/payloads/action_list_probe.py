OUT = '/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log'
f = open(OUT, 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    a = all_ui.get('UIMainActionAndEmoji')
    f.write('btnOpen.isVisible: %r\n' % a.btnOpen.isVisible())
    f.write('btnClose.isVisible: %r\n' % a.btnClose.isVisible())
    f.write('itempanel.isVisible: %r\n' % a.itempanel.isVisible())
    items = a.listview.getItems()
    f.write('listview items count: %r\n' % len(items))
    f.write('btnOpen pos: %r\n' % (getattr(a.btnOpen, 'getPosition', lambda: None)()))
    f.write('btnOpen wp: %r\n' % (getattr(a.btnOpen, 'getWorldPosition', lambda: None)()))
    f.write('btnClose pos: %r\n' % (getattr(a.btnClose, 'getPosition', lambda: None)()))
    f.write('btnClose wp: %r\n' % (getattr(a.btnClose, 'getWorldPosition', lambda: None)()))
except Exception:
    import traceback
    f.write(traceback.format_exc())
f.close()
