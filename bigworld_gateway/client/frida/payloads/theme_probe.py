# READ-ONLY: the player's hall-theme attributes.
out = open(OUT, 'w')
try:
    import BigWorld
    p = BigWorld.player()
    for a in sorted(dir(p)):
        if 'theme' in a.lower() and not a.startswith('__'):
            try:
                v = getattr(p, a)
            except Exception:
                continue
            if not callable(v):
                out.write('%s = %r\n' % (a, v))
except Exception:
    import traceback
    out.write(traceback.format_exc())
out.close()
