import traceback, sys
f = open(OUT, 'w')
def w(s): f.write(str(s) + '\n')
try:
    import BigWorld, Globals
    p = BigWorld.player()
    w("player: %r" % p)
    w("has dtsInGameActionAppearanceIDs: %r" % hasattr(p, 'dtsInGameActionAppearanceIDs'))
    if hasattr(p, 'dtsInGameActionAppearanceIDs'):
        w("dtsInGameActionAppearanceIDs: %r" % (p.dtsInGameActionAppearanceIDs,))
    w("has dtsInGameActionSuitAppearanceIDs: %r" % hasattr(p, 'dtsInGameActionSuitAppearanceIDs'))
    if hasattr(p, 'dtsInGameActionSuitAppearanceIDs'):
        w("dtsInGameActionSuitAppearanceIDs: %r" % (p.dtsInGameActionSuitAppearanceIDs,))
    w("has dtsEmojiList: %r" % hasattr(p, 'dtsEmojiList'))
    if hasattr(p, 'dtsEmojiList'):
        w("dtsEmojiList: %r" % (p.dtsEmojiList,))
    sw = sys.modules.get('shared.switches')
    if sw:
        w("SysEnableInGameAction: %r" % getattr(sw, 'SysEnableInGameAction', None))
        w("SysEnableEmoji: %r" % getattr(sw, 'SysEnableEmoji', None))
    # Check UIs
    uiMgr = getattr(Globals, 'uiMgr', None)
    w("uiMgr: %r" % uiMgr)
    if uiMgr:
        all_ui = getattr(uiMgr, '____all_ui__', getattr(uiMgr, '_UIMgr____all_ui__', {}))
        w("all_ui: %r" % list(all_ui.keys()))
except Exception:
    w(traceback.format_exc())
f.close()
