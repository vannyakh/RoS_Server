# READ-ONLY (RO-074): snapshot space door state for correlating with gateway openElement logs.
# Run in match via tools/probe.sh after pressing OPEN on a building.
import sys
import BigWorld
import Globals

out = open(OUT, "w")


def w(line):
    out.write(line + "\n")


def code_names(fn):
    fn = getattr(fn, "im_func", fn)
    k = getattr(fn, "func_code", None)
    if not k:
        return None
    consts = [x for x in k.co_consts if not hasattr(x, "co_code")]
    return list(k.co_names), consts


p = BigWorld.player()
w("player.pos=%r" % (getattr(p, "position", None),))
w("player.mapID=%r" % (getattr(p, "mapID", None),))

se = getattr(Globals, "spaceEntity", None)
w("spaceEntity=%r" % (se,))
if se is None:
    out.close()
    raise SystemExit(0)

w("space.mapID=%r" % (getattr(se, "mapID", None),))
opened = getattr(se, "openedElements", "<none>")
w("space.openedElements=%r" % (opened,))
if opened not in ("<none>", None):
  try:
    w("openedElements.len=%d" % len(opened))
    for i, el in enumerate(opened):
      w("  [%d] elemID=%r state=%r" % (i, getattr(el, "elemID", el), getattr(el, "state", None)))
  except Exception as e:
    w("openedElements.iter failed: %r" % (e,))

for n in ("onElementOpen", "onElementClose", "set_openedElements", "openedElementsUpdate"):
    f = getattr(se.__class__, n, None) if se else None
    info = code_names(f) if f else None
    w("%s: %s" % (n, ("names=%r consts=%r" % info) if info else "missing"))

cell = getattr(se, "cell", None)
if cell:
    w("cell.openElement=%r" % getattr(cell, "openElement", None))
    w("cell.closeElement=%r" % getattr(cell, "closeElement", None))

out.close()