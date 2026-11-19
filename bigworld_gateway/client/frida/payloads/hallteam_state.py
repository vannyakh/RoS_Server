# READ-ONLY: current hall-team fields on the player and the map-group enum.
import sys
out = open(OUT, 'w')
try:
    import BigWorld
    p = BigWorld.player()
    for a in ('hallTeamType', 'hallTeamSize', 'hallTeamMapGroup', 'hallTeamLeaderGID', 'hallTeamData',
              'hallTeamReady', 'matchingState', 'matchingMapID', 'matchingSubMode', 'gid', 'occupation',
              'characterType', 'baseCharacterType', 'nickname', 'level'):
        out.write('%s = %r\n' % (a, getattr(p, a, '<missing>')))
    c = sys.modules.get('const')
    for n in ('DtsMapBaseType', 'BATTLE_GROUND_MAP_ID'):
        v = getattr(c, n, None)
        out.write('%s = %r\n' % (n, dict((k, x) for k, x in vars(v).items() if not k.startswith('__')) if hasattr(v, '__dict__') else v))
except Exception:
    import traceback
    out.write(traceback.format_exc())
out.close()
