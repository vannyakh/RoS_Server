# READ-ONLY: map 700 safe-zone stages (maps_utils.getBattleGroundParamData(700).CIRCLE_PARAM) and the
# updateCircleRestTime / showCircleNotify argument types. Data getters only.
import sys
out = open(OUT, 'w')
import maps_utils
bp = maps_utils.getBattleGroundParamData(700)
for i, c in enumerate(bp.CIRCLE_PARAM):
    out.write('stage %d %r\n' % (i + 1, dict((a, getattr(c, a)) for a in dir(c) if a.isupper())))
out.close()
