import BigWorld, sys
try:
    p = BigWorld.player()
    print('PLAYER:', p, type(p))
    if p:
        print('dtsInGameActionAppearanceIDs:', hasattr(p, 'dtsInGameActionAppearanceIDs'), len(getattr(p, 'dtsInGameActionAppearanceIDs', [])))
        print('dtsEmojiList:', hasattr(p, 'dtsEmojiList'), len(getattr(p, 'dtsEmojiList', [])))
        print('dtsInGameActionSuitAppearanceIDs:', hasattr(p, 'dtsInGameActionSuitAppearanceIDs'), len(getattr(p, 'dtsInGameActionSuitAppearanceIDs', [])))
    import logic
    print('logic state:', getattr(logic, 'g_game_state', None))
except Exception as e:
    import traceback
    traceback.print_exc()
