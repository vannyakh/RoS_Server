# READ-ONLY: which UIs are entered / visible right now.
out = open(OUT, 'w')
try:
    import Globals
    m = Globals.uiMgr
    for a in sorted(dir(m)):
        if any(t in a.lower() for t in ('stack', 'opened', 'entered', 'current', 'popup', 'queue', 'mask')) and not a.startswith('__'):
            try:
                v = getattr(m, a)
            except Exception:
                continue
            if not callable(v):
                out.write('uiMgr.%s = %r\n' % (a, v if not isinstance(v, dict) else list(v.keys())[:40]))
except Exception:
    import traceback; out.write(traceback.format_exc())
out.close()
