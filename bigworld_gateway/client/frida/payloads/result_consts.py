# READ-ONLY: constants the death/result screen needs (GameEnterType, DTS_TYPE_NAME, team size names,
# banner map) and the own avatar's gid. Reads attributes only, calls no game method.
import sys

out = open(OUT, 'w')
const = sys.modules.get('const')
for n in ('GameEnterType', 'BattleGroundBannerType', 'MallCurrencyType'):
    v = getattr(const, n, None)
    if v is not None:
        out.write('%s = %r\n' % (n, dict((k, x) for k, x in vars(v).items() if not k.startswith('_'))))
out.write('DTS_TYPE_NAME = %r\n' % (getattr(const, 'DTS_TYPE_NAME', None),))
ui = sys.modules.get('ui.UIBattlegroundsResult')
if ui is not None:
    cls = ui.UIBattlegroundsResult
    out.write('teamSizeToModeName = %r\n' % (getattr(cls, 'teamSizeToModeName', None) or getattr(ui, 'teamSizeToModeName', None),))
    out.write('BANNER_RES_MAP = %r\n' % (getattr(cls, 'BANNER_RES_MAP', None),))
ib = sys.modules.get('iBattleGround')
if ib is not None:
    out.write('ShowResultDelayTime = %r\n' % (getattr(ib, 'ShowResultDelayTime', None),))
try:
    import BigWorld
    p = BigWorld.player()
    out.write('player %r gid=%r\n' % (type(p).__name__, getattr(p, 'gid', None)))
except Exception as e:
    out.write('player: %r\n' % (e,))
out.close()
