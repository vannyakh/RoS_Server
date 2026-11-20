# READ-ONLY: what the client's jump/pose code reads and the player's pose-related values.
import BigWorld
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
def co(f):
    f = getattr(f, 'im_func', f)
    return getattr(f, 'func_code', None)
p = BigWorld.player()
for cls in type(p).__mro__:
    for n in ('set_pose', 'set_jumpState', 'set_isJumping', 'changePose', 'onChangePose', 'tryChangePose', 'set_dtsPose', 'jumpStart', 'onJumpStart', 'onJumpEnd', 'canJump', 'setJumpEnabled'):
        f = cls.__dict__.get(n)
        k = co(f) if f else None
        if k:
            w('== %s.%s args=%r' % (cls.__name__, n, list(k.co_varnames[:k.co_argcount])))
            w('names=%r' % list(k.co_names)[:60])
for n in ('pose', 'forbidJump', 'jumpFactor', 'isJumping', 'jumpState', 'battleState', 'fallPhase'):
    w('%s=%r' % (n, getattr(p, n, '<none>')))
out.close()
