import json
import uuid
from pathlib import Path

from qoder_reset_gui import resolve_qoder_data_dir, reset_qoder_machine_id, reset_qoder_telemetry


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

