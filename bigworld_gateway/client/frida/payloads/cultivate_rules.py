# READ-ONLY: Workshop cultivate data for one vehicle chain (Thunder 140059 by default), the
# rule records (consumptions, unlock conditions), and how the client counts owned items.
import sys
import types
out = open(OUT, 'w')
CID = 140059
lp = sys.modules.get('legacyProperties') or vars(sys.modules['dts_appearance_cultivate_utils']).get('legacyProperties')
def rec(o, depth=0):
    """Plain view of a data record (namedtuple-like objects, dicts, lists)."""
    if depth > 3:
        return repr(o)[:200]
    if isinstance(o, (list, tuple)) and not hasattr(o, '_fields'):
        return [rec(x, depth + 1) for x in o]
    if isinstance(o, dict):
        return dict((k, rec(v, depth + 1)) for k, v in o.items())
    if hasattr(o, '_fields'):
        return (o.__class__.__name__, dict((f, rec(getattr(o, f), depth + 1)) for f in o._fields))
    if hasattr(o, '__dict__') and not isinstance(o, (types.ModuleType, types.FunctionType)):
        return (o.__class__.__name__, dict((k, rec(v, depth + 1)) for k, v in vars(o).items()))
    return o
try:
    d = lp.getDtsAppearanceCultivateData(CID)
    out.write('cultivate %d = %r\n' % (CID, rec(d)))
    for rid in (getattr(d, 'RULE_LIST', None) or (d.get('RULE_LIST') if isinstance(d, dict) else []) or []):
        out.write('rule %r = %r\n' % (rid, rec(lp.getDtsAppearanceCultivateRuleData(rid))))
except Exception as e:
    out.write('cultivate data err %r\n' % (e,))
cu = sys.modules.get('dts_appearance_cultivate_utils')
for n in ('getDtsAppearanceCultivateRuleConsumptions', 'isDtsAppearanceCultivateRuleCompleted',
          'isDtsAppearanceCultivateRuleCompletedServer'):
    f = getattr(cu, n, None) or getattr(lp, n, None)
    if f is not None and hasattr(f, 'func_code'):
        c = f.func_code
        out.write('%s args=%r names=%r consts=%r\n' % (n, c.co_varnames[:c.co_argcount], c.co_names,
                  [x for x in c.co_consts if isinstance(x, (str, int))]))
import BigWorld
p = BigWorld.player()
for n in ('getDtsAppearanceItemCnt', 'getPermanentDtsAppearanceItemCnt', 'hasDtsAppearance',
          'isDtsAppearanceCultivateRuleCompleted'):
    for k in type(p).__mro__:
        if n in vars(k):
            c = vars(k)[n].func_code
            out.write('player.%s (%s) args=%r names=%r consts=%r\n' % (n, k.__name__, c.co_varnames[:c.co_argcount],
                      c.co_names, [x for x in c.co_consts if isinstance(x, (str, int))]))
            break
for i in (140056, 140057, 140058, 140059):
    try:
        out.write('cnt %d = %r permanent=%r\n' % (i, p.getDtsAppearanceItemCnt(i),
                  getattr(p, 'getPermanentDtsAppearanceItemCnt', lambda x: None)(i)))
    except Exception as e:
        out.write('cnt %d err %r\n' % (i, e))
pkg = getattr(p, 'dtsAppearancePackage', None)
out.write('dtsAppearancePackage type=%r\n' % type(pkg))
try:
    items = pkg.items() if hasattr(pkg, 'items') else list(pkg)
    out.write('pkg sample=%r\n' % [rec(x) for x in list(items)[:3]])
    out.write('pkg thunder=%r\n' % [rec(x) for x in items if '1400' in repr(x)[:40]][:6])
except Exception as e:
    out.write('pkg err %r\n' % (e,))
for k in sorted(dir(p)):
    if 'ultivat' in k.lower():
        out.write('player attr %s=%r\n' % (k, rec(getattr(p, k)) if not callable(getattr(p, k)) else 'method'))
out.close()
out = open(OUT, 'a')
pk = p.dtsAppearancePackage
for n in ('getItemCnt', 'getPermanentItemCnt'):
    for k in type(pk).__mro__:
        if n in vars(k):
            c = vars(k)[n].func_code
            out.write('pkg.%s (%s) names=%r\n' % (n, k.__name__, c.co_names))
            break
out.write('pkg attrs=%r\n' % [a for a in dir(pk) if not a.startswith('__')][:60])
out.close()
