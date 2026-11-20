# READ-ONLY: const.PlayerPose and related enums.
import sys
out = open(OUT, 'w')
const = sys.modules.get('const')
for n in ('PlayerPose', 'PlayerState', 'FallPhase'):
    c = getattr(const, n, None)
    out.write('%s=%r\n' % (n, dict((k, v) for k, v in vars(c).items() if not k.startswith('__')) if c else None))
out.close()
