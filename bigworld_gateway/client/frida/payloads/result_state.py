# READ-ONLY: client state while the result screen should be up (2026-11-28 run 3: onBattleGroundResult
# ran with no error, but the battle HUD stayed and the screen did not change for 60 s). Reads the open
# UIs, the win-process flag, the result-delay timer and the player's result attributes. Calls nothing.
import sys
f = open(OUT, 'w')
def w(s): f.write(s + '\n')
import BigWorld, Globals
p = BigWorld.player()
w('player=%s hp=%r' % (p.__class__.__name__ if p else None, getattr(p, 'hp', '<missing>')))
for k in ('isWinProcess', 'MAP_ID', 'isInGame', 'inLoading'):
    w('Globals.%s=%r' % (k, getattr(Globals, k, '<missing>')))
for k in ('showResultDelayTimerID', 'everyDayGP', 'observeType', 'battleState', 'fallPhase', 'gid'):
    w('player.%s=%r' % (k, getattr(p, k, '<missing>')))
try:
    import const
    w('ShowResultDelayTime=%r' % (getattr(const, 'ShowResultDelayTime', '<not in const>'),))
except Exception as e:
    w('const: %r' % (e,))
for modname, mod in list(sys.modules.items()):
    if mod is not None and 'ShowResultDelayTime' in getattr(mod, '__dict__', {}):
        w('%s.ShowResultDelayTime=%r' % (modname, mod.__dict__['ShowResultDelayTime']))
um = getattr(Globals, 'uiMgr', None)
for attr in ('_UIMgr____all_ui__vis', '_UIMgr____all_ui_enter_times'):
    v = getattr(um, attr, None)
    if isinstance(v, dict):
        w('uiMgr.%s=%r' % (attr, dict((k, x) for k, x in v.items() if x)))
for name in ('UIBattlegroundsResult', 'UIBattlegroundsResultGold', 'UIBattlegroundsInGame', 'UIDialog'):
    try:
        ui = um.get_ui(name) if hasattr(um, 'get_ui') else None
    except Exception as e:
        ui = '<err %r>' % (e,)
    w('ui %s=%r' % (name, ui))
f.close()
