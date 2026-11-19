# READ-ONLY: raw (opcode, oparg) stream of the code objects that read availSupplementDict,
# with each oparg resolved against names/consts/varnames, to follow the data flow even
# though opcodes are scrambled. Calls nothing.
import sys
import types
out = open(OUT, 'w')
isup = sys.modules['iSupplement'].iSupplement


def stream(label, code):
    out.write('== %s\n' % label)
    b = code.co_code
    i = 0
    rows = []
    while i < len(b):
        op = ord(b[i])
        if i + 2 < len(b) and op >= 90:
            arg = ord(b[i + 1]) | (ord(b[i + 2]) << 8)
            def at(seq):
                return repr(seq[arg])[:40] if arg < len(seq) else '-'
            rows.append('%4d op%3d arg%3d  n=%s c=%s v=%s' % (i, op, arg, at(code.co_names), at(code.co_consts), at(code.co_varnames)))
            i += 3
        else:
            rows.append('%4d op%3d' % (i, op))
            i += 1
    out.write('\n'.join(rows[:260]) + '\n')


def find(code, name):
    for c in code.co_consts:
        if isinstance(c, types.CodeType) and c.co_name == name:
            return c


f = vars(isup)['openSupplyBox']
stream('openSupplyBox', f.func_code)
stream('openSupplyBox.checkIfCanUseCashCoupon', find(f.func_code, 'checkIfCanUseCashCoupon'))
stream('refreshRedHintState', vars(isup)['refreshRedHintState'].func_code)
out.close()
