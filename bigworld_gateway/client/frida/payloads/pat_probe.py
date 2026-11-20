# READ-ONLY: dump props of test entity 23001 (BattleGroundSpace sent with a byte pattern).
import BigWorld
out = open(OUT, 'w')
e = BigWorld.entities.get(23001)
out.write('entity=%r\n' % (e,))
if e is not None:
    for n in ('mapID', 'socketHint', 'gameStartTime', 'gameStatus', 'clientStatus', 'gameEnterType', 'weatherID',
              'redPackets', 'redPacketCnt', 'commanderNumber', 'startTime', 'startTimeStamp', 'circleStage',
              'blueCircleRadius', 'whiteCircleRadius', 'teamSize', 'aliveNum'):
        v = getattr(e, n, '<none>')
        out.write('%s=%r\n' % (n, v if not isinstance(v, (str, unicode)) else v.encode('hex')))
out.close()
