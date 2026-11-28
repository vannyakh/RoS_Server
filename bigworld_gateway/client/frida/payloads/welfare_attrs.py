# READ-ONLY: list attributes the Activity panel (UILimitWelfareController + its sub-panels) reads that
# the current PlayerAthlete lacks, and the PlayerAthlete methods whose code names them (the setters
# the server is expected to call). Only getattr/hasattr; calls no game method.
import sys
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


# methods of every PlayerAthlete base class, name -> code names
meth_names = {}
for k in dir(cls):
    try:
        f = getattr(cls, k)
    except Exception:
        continue
    c = code_of(f)
    if c is not None:
        meth_names[k] = names_of(c, set())

wanted = set()
for modname, mod in sorted(sys.modules.items()):
    if mod is None or not modname.startswith('ui.'):
        continue
    low = modname.lower()
    if not ('limitwelfare' in low or 'welfare' in low or 'telkosme' in low or 'personalrecommend' in low):
        continue
    out.write('== module %s\n' % modname)
    for k, v in vars(mod).items():
        if isinstance(v, type) or type(v).__name__ == 'classobj':
            for n, f in vars(v).items():
                c = code_of(f)
                if c is not None:
                    names_of(c, wanted)
missing = sorted(n for n in wanted if not n.startswith('_') and not hasattr(p, n)
                 and any(n in ns for ns in meth_names.values()))
for n in missing:
    setters = sorted(m for m, ns in meth_names.items() if n in ns)[:8]
    out.write('MISSING %s  <- %s\n' % (n, setters))
out.close()
