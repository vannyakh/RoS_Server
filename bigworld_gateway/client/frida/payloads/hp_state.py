# READ-ONLY: own player's health values and battle state.
import BigWorld
out = open(OUT, 'w')
p = BigWorld.player()
out.write('type %s\n' % type(p).__name__)
for k in ('hp', 'maxHp', 'tmpHP', 'actualHP', 'shieldHp', 'isInPoisonArea', 'battleState', 'position'):
    out.write('%s = %r\n' % (k, getattr(p, k, 'MISSING')))
out.close()
