# READ-ONLY: the player's pickup package, and what the client's door handlers touch.
import sys, types, BigWorld
import Globals
out = open(OUT, 'w')
def w(s): out.write(s + '\n')
p = BigWorld.player()
for n in ('dtsItemPackage', 'dtsPackage', 'dtsWeapon1', 'dtsWeapon2', 'dtsWeapon3', 'dtsCurWeapon'):
    v = getattr(p, n, '<none>')
    w('player.%s=%r' % (n, v))
se = Globals.spaceEntity
w('space.openedElements=%r' % (getattr(se, 'openedElements', '<none>'),))
def co(f):
    f = getattr(f, 'im_func', f)
    return getattr(f, 'func_code', None)
for cls_mod, cls in (('BattleGroundSpace', 'BattleGroundSpace'),):
    m = sys.modules.get(cls_mod)
    c = getattr(m, cls, None)
    for n in ('onElementOpen', 'onElementClose', 'set_openedElements', 'openedElementsUpdate'):
        f = getattr(c, n, None)
        k = co(f) if f else None
        w('%s: %s' % (n, ('names=%r consts=%r' % (list(k.co_names), [x for x in k.co_consts if not hasattr(x, 'co_code')])) if k else 'missing'))
out.close()
