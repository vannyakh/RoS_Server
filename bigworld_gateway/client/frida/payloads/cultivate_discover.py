# READ-ONLY: find the Workshop (appearance cultivate) modules, data tables and the code that
# computes "Own N" and the lock icons. Reads module dicts and code object names only.
import sys
import types
out = open(OUT, 'w')
mods = sorted(n for n, m in sys.modules.items() if m is not None and 'ultivat' in n.lower())
out.write('modules=%r\n' % mods)
ids = (140057, 140058, 140059, 140010)
for n in mods:
    m = sys.modules[n]
    for k, v in sorted(vars(m).items()):
        if k.startswith('__'):
            continue
        if isinstance(v, dict):
            hit = [(i, v[i]) for i in ids if i in v]
            out.write('%s.%s dict len=%d hits=%r sample=%r\n' % (n, k, len(v), hit, list(v.items())[:2]))
        elif isinstance(v, types.FunctionType):
            c = v.func_code
            out.write('%s.%s() args=%r names=%r\n' % (n, k, c.co_varnames[:c.co_argcount], c.co_names))
        elif isinstance(v, (type, types.ClassType)):
            for mk, mv in sorted(vars(v).items()):
                if isinstance(mv, types.FunctionType):
                    c = mv.func_code
                    out.write('%s.%s.%s() args=%r names=%r consts=%r\n' % (
                        n, k, mk, c.co_varnames[:c.co_argcount], c.co_names,
                        [x for x in c.co_consts if isinstance(x, (str, int))][:20]))
out.close()
