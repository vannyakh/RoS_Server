import traceback, sys
f = open('/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log', 'w')
try:
    import Globals
    all_ui = getattr(Globals.uiMgr, '____all_ui__', getattr(Globals.uiMgr, '_UIMgr____all_ui__', {}))
    a = all_ui.get('UIMainActionAndEmoji')
    f.write('UIMainActionAndEmoji: %r\n' % a)
    for attr in dir(a):
        val = getattr(a, attr, None)
        if any(x in attr.lower() for x in ['tab', 'emoji', 'action', 'pose', 'btn', 'panel', 'view']):
            f.write('attr %s: %r\n' % (attr, val))
            if hasattr(val, 'getWorldPosition'):
                try:
                    f.write('  %s wp: %r, size: %r\n' % (attr, val.getWorldPosition(), val.getContentSize()))
                except Exception as e:
                    f.write('  %s err: %r\n' % (attr, e))
except Exception:
    f.write(traceback.format_exc())
f.close()
