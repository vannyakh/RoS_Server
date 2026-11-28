# READ-ONLY: attributes read by UILimitWelfareController.on_enter (and the panel methods it uses) that
# PlayerAthlete lacks, with candidate setter methods (on*/sync*/update*). Only getattr/hasattr.
import sys, __builtin__
import BigWorld
out = open(OUT, 'w')
p = BigWorld.player()
cls = type(p)


def code_of(f):
    return getattr(f, 'func_code', None) or getattr(getattr(f, '__func__', None), 'func_code', None)


def names_of(co, acc):
    acc.update(co.co_names)
    for c in co.co_consts:
        if hasattr(c, 'co_code'):
            names_of(c, acc)
    return acc

meth = {}
for k in dir(cls):
    try:
        c = code_of(getattr(cls, k))
    except Exception:
        c = None
    if c is not None:
        meth[k] = names_of(c, set())
mod = sys.modules.get('ui.UILimitWelfareController')
ctl = getattr(mod, 'UILimitWelfareController', None)
out.write('controller methods: %r\n' % sorted(vars(ctl)))
wanted = set()
for n, f in vars(ctl).items():
    c = code_of(f)
    if c is not None:
        names_of(c, wanted)
glob = set(vars(mod)) | set(dir(__builtin__)) | set(sys.modules)
for n in sorted(wanted):
    if n in glob or n.startswith('_') or hasattr(p, n):
        continue
    setters = sorted(m for m, ns in meth.items() if n in ns and m.startswith(('on', 'sync', 'update', 'set', 'init')))
    if setters:
        out.write('MISSING %s <- %s\n' % (n, setters[:6]))
out.close()
