# READ-ONLY: list string constants / names used by the mail and rank-list UI classes (dict keys the
# server data must carry). Calls no game method.
import sys
out = open(OUT, 'w')


def code_of(f):
    return getattr(f, 'func_code', None) or getattr(getattr(f, '__func__', None), 'func_code', None)


def walk(co, label):
    out.write('-- %s line %s\n   consts=%r\n   names=%r\n' % (label, co.co_firstlineno,
              [c for c in co.co_consts if isinstance(c, (str, int, long)) and c not in (None,)],
              list(co.co_names)))
    for c in co.co_consts:
        if hasattr(c, 'co_code'):
            walk(c, label + '.' + c.co_name)


for modname, mod in sorted(sys.modules.items()):
    if mod is None:
        continue
    low = modname.lower()
    if not ('systemmail' in low or 'mail_utils' in low or 'uiranklist' in low or 'rank_list_utils' in low):
        continue
    out.write('==== MODULE %s\n' % modname)
    try:
        items = list(vars(mod).items())
    except Exception:
        continue
    for k, v in items:
        if isinstance(v, type) or type(v).__name__ == 'classobj':
            for mk, mv in vars(v).items():
                c = code_of(mv)
                if c is not None:
                    walk(c, '%s.%s' % (k, mk))
        else:
            c = code_of(v)
            if c is not None:
                walk(c, k)
out.close()
