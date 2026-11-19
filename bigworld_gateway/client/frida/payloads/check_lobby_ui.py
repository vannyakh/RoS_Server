import sys

with open('/storage/emulated/0/Android/data/com.netease.chiji/files/py_out.log', 'w') as out:
    try:
        import world
        import game3d
        p = world.player()
        out.write("player: %s\n" % str(p))
        scene = game3d.get_current_scene()
        out.write("scene: %s\n" % (scene.filename if scene else "None"))
        
        # Check UI manager
        import ui_mgr
        import ui_entry
        out.write("ui_entry.g_ui_manager: %s\n" % str(getattr(ui_entry, 'g_ui_manager', None)))
        
        # Check loaded controllers
        mgr = getattr(ui_entry, 'g_ui_manager', None)
        if mgr and hasattr(mgr, '_ui_controllers'):
            out.write("controllers:\n")
            for k, v in mgr._ui_controllers.items():
                out.write("  %s: visible=%s\n" % (k, getattr(v, 'isVisible', lambda: '?')()))
    except Exception as e:
        import traceback
        out.write("EXC:\n" + traceback.format_exc() + "\n")
