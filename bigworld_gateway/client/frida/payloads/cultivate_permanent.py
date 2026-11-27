# READ-ONLY: why the Workshop says "Not enough materials" while Own shows 2. Lists names and consts of
# DtsAppearancePackageClient3.getPermanentItemCnt and the client consumption / unlock checks,
# and prints the stored item info of the Thunder Lv.1 copies.
import sys
out = open(OUT, 'w')


def disasm(f):
    """dis.dis fails on NeoX's remapped opcodes: names, constants and locals only."""
    c = getattr(f, 'func_code', f)
    return 'names=%r consts=%r vars=%r' % (c.co_names, c.co_consts, c.co_varnames)


import BigWorld
p = BigWorld.player()
pk = p.dtsAppearancePackage
for k in type(pk).__mro__:
    for n in ('getPermanentItemCnt', 'getItemCnt', '_getItemById'):
        if n in vars(k):
            out.write('==== %s.%s\n%s\n' % (k.__name__, n, disasm(vars(k)[n])))
cu = sys.modules['dts_appearance_cultivate_utils']
for n in ('checkIfMeetAppearanceCultivateRuleConsumptions', 'checkAllConditionAppearancePassed'):
    out.write('==== %s\n%s\n' % (n, disasm(getattr(cu, n))))
for n in ('UnlockConditionAppearance',):
    c = getattr(cu, n)
    for mk, mv in vars(c).items():
        if hasattr(mv, 'func_code'):
            out.write('==== %s.%s\n%s\n' % (n, mk, disasm(mv)))
for i in (142091, 142092):
    out.write('cnt %d item=%r permanent=%r\n' % (i, pk.getItemCnt(i), pk.getPermanentItemCnt(i)))
    try:
        out.write('  items=%r\n' % (pk._getItemById(i),))
    except Exception as e:
        out.write('  _getItemById err %r\n' % (e,))
out.close()
