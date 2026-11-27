# READ-ONLY: the client's current safe-zone values on the space entity.
import BigWorld
out = open(OUT, 'w')
sp = BigWorld.entities.get(20001)
for k in ('gameStatus', 'circleStage', 'whiteCircleCenter', 'whiteCircleRadius', 'blueCircleCenter', 'blueCircleRadius',
          'blueCircleStartCenter', 'blueCircleStartRadius', 'blueCircleShowRadius', 'blueCircleShowCenter', 'circleRestTime'):
    out.write('%s = %r\n' % (k, getattr(sp, k, 'MISSING')))
out.write('player %r\n' % (BigWorld.player().position,))
out.close()
