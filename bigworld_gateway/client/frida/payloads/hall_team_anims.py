# READ-ONLY: which hall props are team dances/actions, with the animation name and loop flag that
# iHallTeam.syncHallTeamAnimation(gid, animName, loop) expects (UIMainAction.onClickActItem reads
# legacyProperties.getDtsHallPropData(id).PROP_TYPE.HALL_TEAM_ANIMATION[_LOOP]). Getters only.
import json
import sys
out = open(OUT, 'w')
lp = None
for m in list(sys.modules.values()):
    if m is not None and hasattr(m, '__dict__') and 'legacyProperties' in m.__dict__:
        lp = m.__dict__['legacyProperties']
        break
found = {}
ids = []
for lo, hi in ((900000, 912000),):
    ids.extend(range(lo, hi))
for i in ids:
    try:
        data = lp.getDtsHallPropData(i)
        kind = data.PROP_TYPE
        name = getattr(kind, 'HALL_TEAM_ANIMATION', None)
        if name:
            found[i] = [name, int(bool(getattr(kind, 'HALL_TEAM_ANIMATION_LOOP', False)))]
    except Exception:
        pass
out.write(json.dumps(found, sort_keys=True))
out.close()
