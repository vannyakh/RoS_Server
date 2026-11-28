# READ-ONLY: print SysMailTypeEnum and the mail type names table. Calls no game method.
import sys
out = open(OUT, 'w')
for modname, mod in sorted(sys.modules.items()):
    if mod is None:
        continue
    try:
        items = list(vars(mod).items())
    except Exception:
        continue
    for k, v in items:
        if k in ('SysMailTypeEnum', 'mailTypeName'):
            d = v if isinstance(v, dict) else dict((a, b) for a, b in vars(v).items() if not a.startswith('_'))
            out.write('%s.%s = %r\n' % (modname, k, d))
out.close()
