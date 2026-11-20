# READ-ONLY: report weapon-related properties.
import BigWorld
out = open(OUT, 'w')
p = BigWorld.player()
out.write('dtsCurWeapon=%r dtsWeapon3=%r dtsWeapon4=%r dtsWeapon5=%r w1id=%r\n' % (
    p.dtsCurWeapon, p.dtsWeapon3, p.dtsWeapon4, p.dtsWeapon5, p.dtsWeapon1['weaponID']))
out.close()
