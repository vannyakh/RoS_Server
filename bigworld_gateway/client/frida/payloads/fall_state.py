# READ-ONLY: own player's fall-related attributes right now (after the jump).
import BigWorld
out = open(OUT, 'w')
p = BigWorld.player()
for k in ('position', 'planeID', 'fallPhase', 'clientFallPhase', 'battleState', 'jumpFactor', 'reduceJumpHeight', 'jumpBuffHeight',
          'glidePhase', 'hasLanded', 'speedFactor', 'moveSpeedFactor', 'gravity', 'isSkydiving', 'parachuteSpeed'):
    out.write('%s = %r\n' % (k, getattr(p, k, 'MISSING')))
for k in sorted(dir(p)):
    if any(s in k.lower() for s in ('factor', 'gravity', 'fallspeed', 'skydiv')) and not callable(getattr(p, k, None)):
        out.write('  %s = %r\n' % (k, getattr(p, k, None)))
out.close()
