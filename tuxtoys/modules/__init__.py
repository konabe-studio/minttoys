"""The tools, one package each, loaded by the daemon."""

# Every module TuxToys ships, as module id -> "package.module:Class". The daemon imports
# each one only when it gets to it, so a module that fails to import fails alone.
AVAILABLE: dict[str, str] = {
    "awake": "tuxtoys.modules.awake.module:Awake",
    "lightswitch": "tuxtoys.modules.lightswitch.module:LightSwitch",
    "locksmith": "tuxtoys.modules.locksmith.module:FileLocksmith",
    "newplus": "tuxtoys.modules.newplus.module:NewPlus",
    "alwaysontop": "tuxtoys.modules.alwaysontop.module:AlwaysOnTop",
    "imageresizer": "tuxtoys.modules.imageresizer.module:ImageResizer",
    "renameplus": "tuxtoys.modules.renameplus.module:RenamePlus",
    "hosts": "tuxtoys.modules.hosts.module:HostsFileEditor",
    "envvars": "tuxtoys.modules.envvars.module:EnvironmentVariables",
    "colorpicker": "tuxtoys.modules.colorpicker.module:ColorPicker",
    "screenruler": "tuxtoys.modules.screenruler.module:ScreenRuler",
    "textextractor": "tuxtoys.modules.textextractor.module:TextExtractor",
    "shortcutguide": "tuxtoys.modules.shortcutguide.module:ShortcutGuide",
}
