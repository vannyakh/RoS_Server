# READ-ONLY: BigWorld.serverTime (the clock the pre-start countdown subtracts from gameStageStartTime),
# sampled twice a few seconds apart, next to the wall clock and the space entity's stage start.
import time, BigWorld

out = open(OUT, 'w')
def w(s): out.write(s + '\n')

def sample(tag):
    parts = ['wall=%.3f' % time.time()]
    for name in ('serverTime', 'time', 'timeAtStart', 'gameTime', 'tickTime', 'tick'):
        try:
            v = getattr(BigWorld, name, None)
            if callable(v):
                v = v()
            parts.append('%s=%r' % (name, v))
        except Exception as e:
            parts.append('%s=ERR(%r)' % (name, e))
    try:
        import Globals
        se = getattr(Globals, 'spaceEntity', None)
        if se is not None:
            parts.append('stage=%r gameStartTime=%r startTime=%r status=%r' % (
                getattr(se, 'gameStageStartTime', None), getattr(se, 'gameStartTime', None),
                getattr(se, 'startTime', None), getattr(se, 'gameStatus', None)))
    except Exception as e:
        parts.append('Globals ERR %r' % (e,))
    w('%s %s' % (tag, ' | '.join(parts)))

sample('T0')
time.sleep(4)
sample('T4')
out.close()
