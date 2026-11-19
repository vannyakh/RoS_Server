# READ-ONLY: a few switch values.
import sys
out = open(OUT, 'w')
sw = sys.modules.get('shared.switches')
for k in ('SysEnableMonthSupply', 'SysEnableHuiliuRecallSystem', 'EnableRecallPlayer', 'EnableNewRecallPlayer', 'URGENT_SWITCH_ENABLE_FORCE_UPGRADE'):
    out.write('%s = %r\n' % (k, getattr(sw, k, '<missing>')))
out.write('isAB = %r\n' % ([getattr(sw, 'isABSwitch')(k) for k in ('SysEnableMonthSupply',)] if hasattr(sw, 'isABSwitch') else None,))
out.close()
