import os
from pathlib import Path


def test_configure_qt_runtime_finds_platform_plugins():
    import qoder_reset_gui

    env_keys = [
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QT_QPA_PLATFORM",
        "QODER_QT_QPA_PLATFORM",
        "QODER_QT_RESET_ENV",
    ]
    old_env = {k: os.environ.get(k) for k in env_keys}
    try:
        for k in env_keys:
            os.environ.pop(k, None)

        info = qoder_reset_gui._configure_qt_runtime()
        assert isinstance(info, dict)

        platforms_dir = info.get("platforms_dir")
        assert platforms_dir, "Expected to discover Qt 'platforms' plugins directory"
        assert Path(platforms_dir).is_dir()
        assert any(Path(platforms_dir).iterdir()), "Expected platform plugins to be present"
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

