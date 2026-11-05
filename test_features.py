import json
import os
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from qoder_reset_gui import (
    QoderResetGUI,
    backup_qoder_identity,
    list_qoder_backups,
    restore_qoder_identity,
    check_for_updates,
    check_is_qoder_running,
    kill_qoder_process,
    run_cli,
    parse_args,
    wait_for_qoder_exit,
    collect_windows_machine_diagnostics,
    randomize_windows_install_time_and_clear_safestore,
    randomize_windows_physical_adapter_macs,
    randomize_windows_c_volume_serial,
)


def test_backup_and_restore_qoder_identity(tmp_path):
    qoder_dir = tmp_path / "Qoder"
    storage_json = qoder_dir / "User" / "globalStorage" / "storage.json"
    storage_json.parent.mkdir(parents=True, exist_ok=True)
    
    orig_machine_id = str(uuid.uuid4())
    (qoder_dir / "machineid").write_text(orig_machine_id, encoding="utf-8")
    (qoder_dir / "hardware_info.json").write_text(json.dumps({"cpu": "test_cpu"}), encoding="utf-8")
    storage_json.write_text(json.dumps({"telemetry.machineId": "orig_telemetry"}), encoding="utf-8")

    # 1. Create backup
    backup_path = backup_qoder_identity(qoder_dir)
    assert backup_path.is_dir()
    assert (backup_path / "manifest.json").is_file()
    assert (backup_path / "machineid").read_text(encoding="utf-8") == orig_machine_id
    assert (backup_path / "storage.json").is_file()

    # 2. List backups
    backups = list_qoder_backups(qoder_dir)
    assert len(backups) == 1
    assert backups[0] == backup_path

    # 3. Modify original files (simulate reset)
    (qoder_dir / "machineid").write_text("new_id", encoding="utf-8")
    storage_json.write_text(json.dumps({"telemetry.machineId": "new_telemetry"}), encoding="utf-8")

    # 4. Restore backup
    success, msg = restore_qoder_identity(backup_path, qoder_dir)
    assert success is True
    assert (qoder_dir / "machineid").read_text(encoding="utf-8") == orig_machine_id
    restored_storage = json.loads(storage_json.read_text(encoding="utf-8"))
    assert restored_storage["telemetry.machineId"] == "orig_telemetry"


def test_check_is_qoder_running_mock():
    mock_run = MagicMock(
        return_value=MagicMock(
            returncode=0, stdout='"Qoder IDE.exe","5348","Console","1","20,000 K"'
        )
    )
    assert check_is_qoder_running(system="Windows", run=mock_run) is True

    mock_run_stopped = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
    assert check_is_qoder_running(system="Linux", run=mock_run_stopped) is False


def test_kill_qoder_process_windows_targets_only_qoder_ide_pids():
    mock_run = MagicMock(
        side_effect=[
            MagicMock(
                returncode=0,
                stdout=(
                    '"Qoder.exe","7556","Console","1","20,000 K"\n'
                    '"Qoder IDE.exe","14440","Console","1","20,000 K"\n'
                    '"other.exe","5772","Console","1","10,000 K"\n'
                    '"qoder.exe","372","Console","1","30,000 K"'
                ),
                stderr="",
            ),
            MagicMock(returncode=0, stdout="terminated 14440", stderr=""),
        ]
    )

    success, details = kill_qoder_process(system="Windows", run=mock_run)

    assert success is True
    assert "terminated 14440" in details
    assert [call.args[0] for call in mock_run.call_args_list] == [
        ["tasklist", "/FO", "CSV", "/NH"],
        ["taskkill", "/F", "/T", "/PID", "14440"],
    ]


def test_wait_for_qoder_exit_waits_until_process_stops():
    with patch(
        "qoder_reset_gui.check_is_qoder_running",
        side_effect=[True, True, False],
    ) as is_running:
        assert wait_for_qoder_exit(timeout=1, poll_interval=0) is True

    assert is_running.call_count == 3


def test_wait_for_qoder_exit_reports_timeout():
    with patch("qoder_reset_gui.check_is_qoder_running", return_value=True):
        assert wait_for_qoder_exit(timeout=0) is False


def test_collect_windows_machine_diagnostics_runs_powershell_in_work_dir(tmp_path):
    report = "=== C: FILESYSTEM VOLUME ===\nVolumeSerial: 1234"
    mock_run = MagicMock(
        return_value=MagicMock(returncode=0, stdout=report, stderr="")
    )

    result = collect_windows_machine_diagnostics(
        work_dir=tmp_path,
        system="Windows",
        run=mock_run,
    )

    assert result == report
    args, kwargs = mock_run.call_args
    assert args[0][0] == "powershell.exe"
    assert "Get-NetAdapter" in args[0][-1]
    assert kwargs["cwd"] == str(tmp_path)
    assert kwargs["timeout"] == 60


def test_collect_windows_machine_diagnostics_rejects_non_windows():
    with pytest.raises(OSError, match="only available on Windows"):
        collect_windows_machine_diagnostics(system="Linux")


def test_randomize_windows_install_time_and_clear_safestore_runs_elevated_script():
    report = '{"NewInstallTimeHex":"0x01DC7D8B04A71A65","SafeStoreFilesDeleted":2}'
    mock_run = MagicMock(
        return_value=MagicMock(returncode=0, stdout=report, stderr="")
    )

    result = randomize_windows_install_time_and_clear_safestore(
        system="Windows",
        run=mock_run,
    )

    assert result == report
    args, kwargs = mock_run.call_args
    script = args[0][-1]
    assert args[0][0] == "powershell.exe"
    assert "RegistryValueKind]::QWord" in script
    assert "RandomNumberGenerator" in script
    assert "Remove-Item -LiteralPath" in script
    assert "Administrator privileges are required" in script
    assert kwargs["timeout"] == 60


def test_randomize_windows_install_time_and_clear_safestore_reports_failure():
    mock_run = MagicMock(
        return_value=MagicMock(
            returncode=1,
            stdout="",
            stderr="Administrator privileges are required",
        )
    )

    with pytest.raises(RuntimeError, match="Administrator privileges are required"):
        randomize_windows_install_time_and_clear_safestore(
            system="Windows",
            run=mock_run,
        )


def test_randomize_windows_install_time_and_clear_safestore_rejects_non_windows():
    with pytest.raises(OSError, match="only available on Windows"):
        randomize_windows_install_time_and_clear_safestore(system="Linux")


def test_randomize_windows_physical_adapter_macs_reports_success_and_partial_failure():
    output = json.dumps(
        [
            {
                "Adapter": "Ethernet",
                "PreviousMac": "00-11-22-33-44-55",
                "NewMac": "02-12-34-56-78-9A",
                "Success": True,
                "Error": "",
            },
            {
                "Adapter": "Wi-Fi",
                "PreviousMac": "00-AA-BB-CC-DD-EE",
                "NewMac": "02-98-76-54-32-10",
                "Success": False,
                "Error": "Driver does not support the requested property",
            },
        ]
    )
    mock_run = MagicMock(
        return_value=MagicMock(returncode=0, stdout=output, stderr="")
    )

    report = randomize_windows_physical_adapter_macs(
        system="Windows",
        run=mock_run,
    )

    assert "Partial success: 1 of 2 adapters changed." in report
    assert "Ethernet: 00-11-22-33-44-55 -> 02-12-34-56-78-9A" in report
    assert "Wi-Fi: failed: Driver does not support" in report
    script = mock_run.call_args.args[0][-1]
    assert "Get-NetAdapter -Physical" in script
    assert "RandomNumberGenerator" in script
    assert "Set-NetAdapter -Name" in script
    assert "Administrator privileges are required" in script


def test_randomize_windows_physical_adapter_macs_rejects_all_failures():
    output = json.dumps(
        [
            {
                "Adapter": "Ethernet",
                "PreviousMac": "00-11-22-33-44-55",
                "NewMac": "02-12-34-56-78-9A",
                "Success": False,
                "Error": "Not supported",
            }
        ]
    )
    mock_run = MagicMock(
        return_value=MagicMock(returncode=0, stdout=output, stderr="")
    )

    with pytest.raises(RuntimeError, match="No MAC addresses were changed"):
        randomize_windows_physical_adapter_macs(system="Windows", run=mock_run)


def test_randomize_windows_physical_adapter_macs_rejects_non_windows():
    with pytest.raises(OSError, match="only available on Windows"):
        randomize_windows_physical_adapter_macs(system="Linux")


def test_randomize_windows_c_volume_serial_invokes_installed_tool(tmp_path):
    executable = tmp_path / "VolumeID64.exe"
    executable.touch()
    mock_run = MagicMock(
        return_value=MagicMock(
            returncode=0,
            stdout="VolumeId updated",
            stderr="",
        )
    )

    report = randomize_windows_c_volume_serial(
        executable=executable,
        system="Windows",
        run=mock_run,
    )

    args, kwargs = mock_run.call_args
    assert args[0][0] == str(executable)
    assert args[0][1] == "C:"
    assert len(args[0][2]) == 9
    assert args[0][2][4] == "-"
    assert all(char in "0123456789ABCDEF-" for char in args[0][2])
    assert "Restart Windows" in report
    assert "VolumeId updated" in report
    assert kwargs["stdin"] == -3
    assert kwargs["timeout"] == 30


def test_randomize_windows_c_volume_serial_reports_missing_tool(tmp_path):
    with pytest.raises(FileNotFoundError, match="Sysinternals VolumeID was not found"):
        randomize_windows_c_volume_serial(
            executable=tmp_path / "missing.exe",
            system="Windows",
        )


def test_randomize_windows_c_volume_serial_reports_tool_failure(tmp_path):
    executable = tmp_path / "VolumeID64.exe"
    executable.touch()
    mock_run = MagicMock(
        return_value=MagicMock(
            returncode=5,
            stdout="",
            stderr="Access denied",
        )
    )

    with pytest.raises(RuntimeError, match="Access denied"):
        randomize_windows_c_volume_serial(
            executable=executable,
            system="Windows",
            run=mock_run,
        )


def test_randomize_windows_c_volume_serial_rejects_non_windows():
    with pytest.raises(OSError, match="only available on Windows"):
        randomize_windows_c_volume_serial(system="Linux")


def test_check_for_updates_parsing():
    # Test version comparison parsing
    info = check_for_updates(current_version="1.2.0")
    assert "success" in info
    assert "current_version" in info
    assert info["current_version"] == "1.2.0"


def test_run_cli_status(tmp_path, capsys):
    args = MagicMock()
    args.cli = True
    args.reset = False
    args.backup = False
    args.restore = None
    args.list_backups = False
    args.check_update = False
    args.status = True
    args.close_qoder = False

    ret = run_cli(args)
    assert ret == 0
    captured = capsys.readouterr()
    assert "🔒 Qoder-Free" in captured.out
    assert "Qoder Status:" in captured.out


def test_gui_backup_and_restore_methods(tmp_path):
    qoder_dir = tmp_path / "Qoder"
    qoder_dir.mkdir(parents=True, exist_ok=True)
    (qoder_dir / "machineid").write_text(str(uuid.uuid4()), encoding="utf-8")

    app = QApplication.instance() or QApplication([])
    window = QoderResetGUI()
    window.get_qoder_data_dir = lambda: qoder_dir
    window.log = lambda msg: None

    with patch("PyQt5.QtWidgets.QMessageBox.question", return_value=QApplication.instance().focusWidget() or 16384): # 16384 is QMessageBox.Yes
        with patch("PyQt5.QtWidgets.QMessageBox.information") as mock_info:
            window.backup_identity()
            assert mock_info.called

    assert len(list_qoder_backups(qoder_dir)) == 1
