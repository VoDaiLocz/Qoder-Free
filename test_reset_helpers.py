import json
import uuid
from pathlib import Path

from PyQt5.QtWidgets import QApplication

from qoder_reset_gui import (
    QoderResetGUI,
    resolve_qoder_data_dir,
    reset_qoder_machine_id,
    reset_qoder_telemetry,
)


def test_resolve_qoder_data_dir_windows_prefers_appdata(tmp_path):
    home_dir = tmp_path / "home"
    appdata = tmp_path / "AppData" / "Roaming"
    expected = appdata / "Qoder"

    resolved = resolve_qoder_data_dir(
        system="Windows",
        env={"APPDATA": str(appdata)},
        home_dir=home_dir,
    )
    assert resolved == expected


def test_reset_qoder_machine_id_writes_machineid(tmp_path):
    new_machine_id = reset_qoder_machine_id(tmp_path)
    assert (tmp_path / "machineid").is_file()
    assert (tmp_path / "machineid").read_text(encoding="utf-8") == new_machine_id
    uuid.UUID(new_machine_id)


def test_reset_qoder_telemetry_creates_and_updates_storage_json(tmp_path):
    storage_json_file = tmp_path / "User" / "globalStorage" / "storage.json"
    storage_json_file.parent.mkdir(parents=True, exist_ok=True)
    storage_json_file.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")

    updated = reset_qoder_telemetry(tmp_path, system="Linux")
    assert storage_json_file.is_file()

    data = json.loads(storage_json_file.read_text(encoding="utf-8"))
    assert data["foo"] == "bar"
    assert data["telemetry.machineId"] == updated["telemetry.machineId"]
    assert data["telemetry.devDeviceId"] == updated["telemetry.devDeviceId"]
    assert data["telemetry.sqmId"] == updated["telemetry.sqmId"]
    assert data["system.platform"] == "linux"


def test_full_reset_runs_login_and_deep_cleanup_without_crashing(tmp_path):
    qoder_dir = tmp_path / "Qoder"
    storage_json_file = qoder_dir / "User" / "globalStorage" / "storage.json"
    storage_json_file.parent.mkdir(parents=True, exist_ok=True)
    storage_json_file.write_text(
        json.dumps(
            {
                "foo": "bar",
                "telemetry.machineId": "old-machine",
                "telemetry.devDeviceId": "old-device",
                "auth.accessToken": "secret",
                "session.id": "old-session",
            }
        ),
        encoding="utf-8",
    )
    (qoder_dir / "machineid").write_text(str(uuid.uuid4()), encoding="utf-8")
    (qoder_dir / "Cookies").write_text("cookie", encoding="utf-8")
    (qoder_dir / "SharedClientCache" / "cache").mkdir(parents=True)

    app = QApplication.instance() or QApplication([])
    window = QoderResetGUI()
    window.get_qoder_data_dir = lambda: qoder_dir
    window.log = lambda message: None

    window.perform_full_reset(preserve_chat=True)

    data = json.loads(storage_json_file.read_text(encoding="utf-8"))
    uuid.UUID((qoder_dir / "machineid").read_text(encoding="utf-8"))
    assert data["foo"] == "bar"
    assert data["telemetry.machineId"] != "old-machine"
    assert data["telemetry.devDeviceId"] != "old-device"
    assert "auth.accessToken" not in data
    assert "session.id" not in data
    assert not (qoder_dir / "Cookies").exists()
    assert (qoder_dir / "hardware_info.json").is_file()
    assert app is not None
