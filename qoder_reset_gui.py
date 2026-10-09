#!/usr/bin/env python3
"""
Qoder Reset Tool - Modern GUI Version
Implemented using PyQt5, fully designed according to user prototype
"""

__version__ = "1.3.2"

import os
import sys
import csv
import json
import uuid
import shutil
import hashlib
import subprocess
import webbrowser
import platform
import random
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable, Mapping, Optional, Tuple

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    HAS_PYQT5 = True
except ImportError:
    HAS_PYQT5 = False


def resolve_qoder_data_dir(
    system: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    home_dir: Optional[Path] = None,
) -> Path:
    system = system or platform.system()
    env = env or os.environ
    home_dir = home_dir or Path.home()

    if system == "Windows":
        # Prefer %APPDATA% when available; home/AppData/Roaming is only a fallback.
        appdata = env.get("APPDATA")
        if appdata:
            return Path(appdata) / "Qoder"
        return home_dir / "AppData" / "Roaming" / "Qoder"

    if system == "Linux":
        xdg_config_home = env.get("XDG_CONFIG_HOME")
        base = Path(xdg_config_home) if xdg_config_home else (home_dir / ".config")
        return base / "Qoder"

    # macOS (and default fallback)
    return home_dir / "Library" / "Application Support" / "Qoder"


def _qoder_platform_value(system: Optional[str] = None) -> str:
    system = system or platform.system()
    if system == "Windows":
        return "win32"
    if system == "Linux":
        return "linux"
    return "darwin"


def _windows_qoder_pids(tasklist_output: str) -> list:
    return [
        row[1].strip()
        for row in csv.reader(tasklist_output.splitlines())
        if len(row) >= 2
        and row[0].strip().casefold() == "qoder ide.exe"
        and row[1].strip().isdigit()
    ]


def kill_qoder_process(
    system: Optional[str] = None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Tuple[bool, str]:
    """
    Best-effort attempt to terminate Qoder.
    Returns (success, details) where details is stdout/stderr text when available.
    """
    system = system or platform.system()

    if system == "Windows":
        result = run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            details = getattr(result, "stderr", "") or getattr(result, "stdout", "")
            return False, details.strip()

        qoder_pids = _windows_qoder_pids(getattr(result, "stdout", ""))
        if not qoder_pids:
            return True, ""

        kill_results = []
        for pid in qoder_pids:
            kill_results.append(
                run(
                    ["taskkill", "/F", "/T", "/PID", pid],
                    capture_output=True,
                    text=True,
                )
            )
        result = kill_results[-1]
        details = "\n".join(
            text.strip()
            for kill_result in kill_results
            for text in (
                getattr(kill_result, "stdout", ""),
                getattr(kill_result, "stderr", ""),
            )
            if text and text.strip()
        )
        return all(item.returncode == 0 for item in kill_results), details
    elif system == "Darwin":
        result = run(["pkill", "-x", "Qoder"], capture_output=True, text=True)
    elif system == "Linux":
        result = run(["pkill", "-x", "qoder"], capture_output=True, text=True)
    else:
        return False, f"Unsupported platform: {system}"

    details = ""
    if getattr(result, "stdout", None):
        details += result.stdout.strip()
    if getattr(result, "stderr", None):
        if details:
            details += "\n"
        details += result.stderr.strip()

    # On Windows taskkill returns non-zero when the process isn't found; treat that as not fatal.
    if system == "Windows" and "not found" in details.lower():
        return True, details

    return result.returncode == 0, details


def reset_qoder_machine_id(qoder_support_dir: Path) -> str:
    if not qoder_support_dir.exists():
        raise FileNotFoundError(f"Qoder data directory not found: {qoder_support_dir}")

    new_machine_id = str(uuid.uuid4())
    machine_id_file = qoder_support_dir / "machineid"
    machine_id_file.write_text(new_machine_id, encoding="utf-8")
    return new_machine_id


def reset_qoder_telemetry(
    qoder_support_dir: Path, system: Optional[str] = None
) -> Mapping[str, str]:
    if not qoder_support_dir.exists():
        raise FileNotFoundError(f"Qoder data directory not found: {qoder_support_dir}")

    storage_json_file = qoder_support_dir / "User" / "globalStorage" / "storage.json"
    storage_json_file.parent.mkdir(parents=True, exist_ok=True)

    if storage_json_file.exists():
        try:
            data = json.loads(storage_json_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    else:
        data = {}

    new_uuid = str(uuid.uuid4())
    machine_id_hash = hashlib.sha256(new_uuid.encode()).hexdigest()
    device_id = str(uuid.uuid4())
    sqm_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    installation_id = str(uuid.uuid4())

    data["telemetry.machineId"] = machine_id_hash
    data["telemetry.devDeviceId"] = device_id
    data["telemetry.sqmId"] = sqm_id
    data["telemetry.sessionId"] = session_id
    data["telemetry.installationId"] = installation_id

    # Additional identifiers commonly used as fallbacks.
    data["telemetry.clientId"] = str(uuid.uuid4())
    data["telemetry.userId"] = str(uuid.uuid4())
    data["telemetry.anonymousId"] = str(uuid.uuid4())
    data["machineId"] = machine_id_hash
    data["deviceId"] = device_id
    data["installationId"] = str(uuid.uuid4())
    data["hardwareId"] = str(uuid.uuid4())
    data["platformId"] = str(uuid.uuid4())

    data["system.platform"] = _qoder_platform_value(system)
    data["system.arch"] = platform.machine()

    storage_json_file.write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "telemetry.machineId": machine_id_hash,
        "telemetry.devDeviceId": device_id,
        "telemetry.sqmId": sqm_id,
        "telemetry.sessionId": session_id,
        "telemetry.installationId": installation_id,
    }


def check_is_qoder_running(
    system: Optional[str] = None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> bool:
    """Check if Qoder is currently running (cross-platform)."""
    system = system or platform.system()
    try:
        if system == "Windows":
            result = run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
            )
            return bool(_windows_qoder_pids(getattr(result, "stdout", "")))
        elif system == "Darwin":
            result = run(["pgrep", "-x", "Qoder"], capture_output=True, text=True)
            return result.returncode == 0
        elif system == "Linux":
            result = run(["pgrep", "-x", "qoder"], capture_output=True, text=True)
            return result.returncode == 0
        return False
    except Exception:
        return False


def wait_for_qoder_exit(timeout: float = 5.0, poll_interval: float = 0.25) -> bool:
    """Wait briefly for Qoder and its file handles to be released."""
    deadline = time.monotonic() + timeout
    while check_is_qoder_running():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(poll_interval, remaining))
    return True


def collect_windows_machine_diagnostics(
    work_dir: Optional[Path] = None,
    system: Optional[str] = None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> str:
    """Collect the requested Windows hardware, SafeStore, and Qoder CLI details."""
    system = system or platform.system()
    if system != "Windows":
        raise OSError("Windows machine diagnostics are only available on Windows.")

    script = r"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'
$sections = New-Object 'System.Collections.Generic.List[string]'

$sections.Add('=== C: FILESYSTEM VOLUME ===')
try {
    $volume = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    if ($null -eq $volume) { throw 'C: volume was not found.' }
    $sections.Add("Drive: $($volume.DeviceID)`nVolumeSerial: $($volume.VolumeSerialNumber)`nFileSystem: $($volume.FileSystem)")
} catch {
    $sections.Add("ERROR: $($_.Exception.Message)")
}

$sections.Add('')
$sections.Add('=== MAC ADDRESSES ===')
try {
    $adapters = Get-NetAdapter |
        Select-Object ifIndex, Name, Status, HardwareInterface, MacAddress, InterfaceDescription |
        Sort-Object ifIndex |
        Format-Table -AutoSize |
        Out-String -Width 200
    $sections.Add($adapters.TrimEnd())
} catch {
    $sections.Add("ERROR: $($_.Exception.Message)")
}

$sections.Add('')
$sections.Add('=== SAFESTORE FILES ===')
try {
    $safeStoreDir = 'C:\Users\Public\Documents\Alibaba\SafeStore'
    if (Test-Path -LiteralPath $safeStoreDir) {
        $files = Get-ChildItem -LiteralPath $safeStoreDir -Force |
            Select-Object FullName, Length, CreationTimeUtc, LastWriteTimeUtc |
            Format-Table -AutoSize |
            Out-String -Width 200
        $sections.Add($files.TrimEnd())
    } else {
        $sections.Add('SafeStore directory does not exist.')
    }
} catch {
    $sections.Add("ERROR: $($_.Exception.Message)")
}

$sections.Add('')
$sections.Add('=== WINDOWS INSTALL TIME ===')
try {
    $registryPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
    $installTime = (Get-ItemProperty -Path $registryPath -Name InstallTime).InstallTime
    $fileTime = [Int64]$installTime
    $sections.Add("RegistryPath: HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion`nValueName: InstallTime`nRawFILETIME: $installTime`nHexFILETIME: $('0x{0:X16}' -f $fileTime)`nInstallTimeUtc: $([DateTime]::FromFileTimeUtc($fileTime).ToString('o'))")
} catch {
    $sections.Add("ERROR: $($_.Exception.Message)")
}

$sections.Add('')
$sections.Add('=== QODER MACHINE INFO ===')
try {
    $qoderExe = 'C:\Program Files\Qoder IDE\resources\app\resources\bin\x86_64_windows\Qoder.exe'
    if (Test-Path -LiteralPath $qoderExe) {
        $workDir = (Get-Location).Path
        $sections.Add("WorkDir: $workDir")
        $machineInfo = (& $qoderExe machine-info --workDir $workDir 2>&1 | Out-String).TrimEnd()
        $machineInfoExitCode = $LASTEXITCODE
        if ($machineInfo) { $sections.Add($machineInfo) } else { $sections.Add('Qoder returned no output.') }
        if ($null -ne $machineInfoExitCode -and $machineInfoExitCode -ne 0) {
            $sections.Add("Qoder exit code: $machineInfoExitCode")
        }
    } else {
        $sections.Add("Qoder executable not found: $qoderExe")
    }
} catch {
    $sections.Add("ERROR: $($_.Exception.Message)")
}

Write-Output ($sections -join [Environment]::NewLine)
"""
    result = run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(work_dir or Path.cwd()),
        timeout=60,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"PowerShell diagnostics failed with exit code {result.returncode}"
            + (f": {details}" if details else ".")
        )
    report = result.stdout.strip()
    if not report:
        raise RuntimeError("PowerShell diagnostics returned no output.")
    return report


def randomize_windows_install_time_and_clear_safestore(
    system: Optional[str] = None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> str:
    """Set a random valid Windows InstallTime and remove SafeStore contents."""
    system = system or platform.system()
    if system != "Windows":
        raise OSError("This operation is only available on Windows.")

    script = r"""
$ErrorActionPreference = 'Stop'
$safeStoreDir = 'C:\Users\Public\Documents\Alibaba\SafeStore'
$registrySubKey = 'SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator privileges are required. Restart Qoder-Free as Administrator.'
}

$registryKey = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($registrySubKey, $true)
if ($null -eq $registryKey) {
    throw 'Could not open the Windows CurrentVersion registry key for writing.'
}
try {
    $oldInstallTime = $registryKey.GetValue('InstallTime', $null)
    if ($null -eq $oldInstallTime) {
        throw 'The InstallTime registry value does not exist.'
    }

    $startFileTime = [DateTime]::new(2000, 1, 1, 0, 0, 0, [DateTimeKind]::Utc).ToFileTimeUtc()
    $endFileTime = [DateTime]::UtcNow.ToFileTimeUtc()
    $randomBytes = New-Object byte[] 8
    $randomGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $randomGenerator.GetBytes($randomBytes)
    } finally {
        $randomGenerator.Dispose()
    }
    $range = [UInt64]($endFileTime - $startFileTime)
    $offset = [BitConverter]::ToUInt64($randomBytes, 0) % $range
    $newInstallTime = [Int64]([UInt64]$startFileTime + $offset)
    $registryKey.SetValue(
        'InstallTime',
        $newInstallTime,
        [Microsoft.Win32.RegistryValueKind]::QWord
    )
    $registryKey.Flush()
} finally {
    $registryKey.Dispose()
}

$removedFiles = 0
if (Test-Path -LiteralPath $safeStoreDir -PathType Container) {
    $removedFiles = @(Get-ChildItem -LiteralPath $safeStoreDir -File -Recurse -Force).Count
    $entries = @(Get-ChildItem -LiteralPath $safeStoreDir -Force)
    foreach ($entry in $entries) {
        Remove-Item -LiteralPath $entry.FullName -Recurse -Force
    }
}

[PSCustomObject]@{
    PreviousInstallTimeHex = ('0x{0:X16}' -f [Int64]$oldInstallTime)
    NewInstallTimeHex = ('0x{0:X16}' -f $newInstallTime)
    NewInstallTimeUtc = [DateTime]::FromFileTimeUtc($newInstallTime).ToString('o')
    SafeStoreFilesDeleted = $removedFiles
    SafeStoreDirectoryExists = (Test-Path -LiteralPath $safeStoreDir -PathType Container)
} | ConvertTo-Json -Compress
"""
    result = run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Windows InstallTime/SafeStore operation failed with exit code {result.returncode}"
            + (f": {details}" if details else ".")
        )
    report = result.stdout.strip()
    if not report:
        raise RuntimeError("Windows InstallTime/SafeStore operation returned no output.")
    return report


def randomize_windows_physical_adapter_macs(
    system: Optional[str] = None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> str:
    """Assign random locally administered MAC addresses to eligible physical adapters."""
    system = system or platform.system()
    if system != "Windows":
        raise OSError("Changing network adapter MAC addresses is only available on Windows.")

    script = r"""
$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Administrator privileges are required. Restart Qoder-Free as Administrator.'
}

$adapters = @(Get-NetAdapter -Physical -ErrorAction Stop |
    Where-Object { $_.HardwareInterface -and $_.MacAddress })
if ($adapters.Count -eq 0) {
    throw 'No eligible physical network adapters were found.'
}

$randomGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
try {
    $results = foreach ($adapter in $adapters) {
        $randomBytes = New-Object byte[] 6
        $randomGenerator.GetBytes($randomBytes)
        $randomBytes[0] = ($randomBytes[0] -band 0xFE) -bor 0x02
        $newMacAddress = ($randomBytes | ForEach-Object { $_.ToString('X2') }) -join '-'
        try {
            Set-NetAdapter -Name $adapter.Name -MacAddress $newMacAddress -Confirm:$false -ErrorAction Stop
            [PSCustomObject]@{
                Adapter = $adapter.Name
                PreviousMac = $adapter.MacAddress
                NewMac = $newMacAddress
                Success = $true
                Error = ''
            }
        } catch {
            [PSCustomObject]@{
                Adapter = $adapter.Name
                PreviousMac = $adapter.MacAddress
                NewMac = $newMacAddress
                Success = $false
                Error = $_.Exception.Message
            }
        }
    }
} finally {
    $randomGenerator.Dispose()
}

ConvertTo-Json -InputObject @($results) -Compress -Depth 3
"""
    result = run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Windows MAC address operation failed with exit code {result.returncode}"
            + (f": {details}" if details else ".")
        )
    try:
        results = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Windows MAC address operation returned invalid output.") from exc
    if not isinstance(results, list) or not results:
        raise RuntimeError("No eligible physical network adapters were found.")

    report_lines = []
    succeeded = 0
    for item in results:
        if not isinstance(item, dict) or not item.get("Adapter"):
            raise RuntimeError("Windows MAC address operation returned an invalid adapter result.")
        if item.get("Success") is True:
            succeeded += 1
            report_lines.append(
                f"{item['Adapter']}: {item.get('PreviousMac', 'unknown')} -> {item.get('NewMac', 'unknown')}"
            )
        else:
            report_lines.append(
                f"{item['Adapter']}: failed: {item.get('Error') or 'driver rejected the MAC address'}"
            )
    if succeeded == 0:
        raise RuntimeError("No MAC addresses were changed.\n" + "\n".join(report_lines))
    if succeeded < len(results):
        report_lines.insert(0, f"Partial success: {succeeded} of {len(results)} adapters changed.")
    return "\n".join(report_lines)


def randomize_windows_c_volume_serial(
    executable: Optional[Path] = None,
    system: Optional[str] = None,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> str:
    """Change the C: volume serial using an installed Microsoft Sysinternals VolumeID."""
    system = system or platform.system()
    if system != "Windows":
        raise OSError("Changing the C: volume serial is only available on Windows.")

    executable_names = ("VolumeID64.exe", "Volumeid.exe", "volumeid.exe")
    candidates = []
    if executable is not None:
        candidates.append(Path(executable))
    else:
        for name in executable_names:
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))
        for directory in (Path(__file__).resolve().parent, Path(sys.executable).resolve().parent):
            candidates.extend(directory / name for name in executable_names)

    volume_id_executable = next((path for path in candidates if path.is_file()), None)
    if volume_id_executable is None:
        raise FileNotFoundError(
            "Sysinternals VolumeID was not found. Download the official VolumeID utility "
            "from https://learn.microsoft.com/sysinternals/downloads/volumeid, then place "
            "Volumeid.exe or VolumeID64.exe beside Qoder-Free or add it to PATH."
        )

    serial = uuid.uuid4().hex[:8].upper()
    formatted_serial = f"{serial[:4]}-{serial[4:]}"
    result = run(
        [str(volume_id_executable), "C:", formatted_serial],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    output = "\n".join(
        text.strip()
        for text in (result.stdout, result.stderr)
        if text and text.strip()
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"VolumeID failed with exit code {result.returncode}"
            + (f":\n{output}" if output else ". Run Qoder-Free as Administrator.")
        )
    return (
        f"Requested C: volume serial: {formatted_serial}\n"
        "Restart Windows for the new serial to take effect on NTFS."
        + (f"\n\nVolumeID output:\n{output}" if output else "")
    )


def backup_qoder_identity(
    qoder_support_dir: Path,
    backup_dest_dir: Optional[Path] = None,
) -> Path:
    """
    Back up Qoder identity files (machineid, storage.json, hardware_info.json)
    to a timestamped directory. Returns the path of the created backup directory.
    """
    if not qoder_support_dir.exists():
        raise FileNotFoundError(f"Qoder data directory not found: {qoder_support_dir}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if backup_dest_dir is None:
        backup_base = qoder_support_dir.parent / "Qoder_Backups"
        target_dir = backup_base / f"backup_{timestamp}"
    else:
        target_dir = backup_dest_dir

    target_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "timestamp": timestamp,
        "created_at": datetime.now().isoformat(),
        "version": __version__,
        "platform": platform.system(),
        "files_backed_up": [],
    }

    # Backup machineid and auxiliary id files
    id_files = [
        "machineid",
        "deviceid",
        "hardware_uuid",
        "system_uuid",
        "platform_id",
        "installation_id",
        "hardware_info.json",
    ]
    for filename in id_files:
        src = qoder_support_dir / filename
        if src.is_file():
            dst = target_dir / filename
            shutil.copy2(src, dst)
            manifest["files_backed_up"].append(filename)

    # Backup storage.json
    storage_json = qoder_support_dir / "User" / "globalStorage" / "storage.json"
    if storage_json.is_file():
        storage_dest = target_dir / "storage.json"
        shutil.copy2(storage_json, storage_dest)
        manifest["files_backed_up"].append("User/globalStorage/storage.json")

    manifest_file = target_dir / "manifest.json"
    manifest_file.write_text(
        json.dumps(manifest, indent=4, ensure_ascii=False), encoding="utf-8"
    )
    return target_dir


def list_qoder_backups(qoder_support_dir: Optional[Path] = None) -> list:
    """List available identity backups, ordered newest first."""
    qoder_dir = qoder_support_dir or resolve_qoder_data_dir()
    backup_base = qoder_dir.parent / "Qoder_Backups"
    if not backup_base.is_dir():
        return []
    backups = [
        p
        for p in backup_base.iterdir()
        if p.is_dir() and (p / "manifest.json").is_file()
    ]
    backups.sort(key=lambda p: p.name, reverse=True)
    return backups


def restore_qoder_identity(
    backup_dir: Path, qoder_support_dir: Path
) -> Tuple[bool, str]:
    """Restore identity files from backup into qoder_support_dir."""
    if not backup_dir.is_dir():
        return False, f"Backup directory not found: {backup_dir}"

    qoder_support_dir.mkdir(parents=True, exist_ok=True)
    restored_count = 0

    for src in backup_dir.iterdir():
        if src.name in ("manifest.json", "storage.json"):
            continue
        if src.is_file():
            dst = qoder_support_dir / src.name
            shutil.copy2(src, dst)
            restored_count += 1

    storage_backup = backup_dir / "storage.json"
    if storage_backup.is_file():
        storage_dest = qoder_support_dir / "User" / "globalStorage" / "storage.json"
        storage_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(storage_backup, storage_dest)
        restored_count += 1

    return True, f"Successfully restored {restored_count} files from {backup_dir.name}"


def check_for_updates(current_version: str = __version__) -> Mapping[str, object]:
    """Check GitHub releases API for newer Qoder-Free versions."""
    url = "https://api.github.com/repos/VoDaiLocz/Qoder-Free/releases/latest"
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"Qoder-Free-Updater/{current_version}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                tag_name = data.get("tag_name", "").lstrip("v")
                html_url = data.get(
                    "html_url",
                    "https://github.com/VoDaiLocz/Qoder-Free/releases/latest",
                )
                body = data.get("body", "")

                def _parse_v(v: str):
                    return [int(x) if x.isdigit() else x for x in v.split(".")]

                has_update = False
                if tag_name:
                    try:
                        has_update = _parse_v(tag_name) > _parse_v(current_version)
                    except Exception:
                        has_update = tag_name != current_version

                return {
                    "success": True,
                    "has_update": has_update,
                    "latest_version": tag_name or "unknown",
                    "current_version": current_version,
                    "url": html_url,
                    "release_notes": body,
                }
    except Exception as e:
        return {
            "success": False,
            "has_update": False,
            "error": str(e),
            "latest_version": "unknown",
            "current_version": current_version,
            "url": "https://github.com/VoDaiLocz/Qoder-Free/releases/latest",
            "release_notes": "",
        }

    return {
        "success": False,
        "has_update": False,
        "error": "Unknown error",
        "latest_version": "unknown",
        "current_version": current_version,
        "url": "https://github.com/VoDaiLocz/Qoder-Free/releases/latest",
        "release_notes": "",
    }


def _configure_qt_runtime():
    """
    Best-effort Qt plugin path hardening.

    Helps avoid: "This application failed to start because no Qt platform plugin could be initialized"
    """
    # Some environments carry a broken/mismatched QT_PLUGIN_PATH that breaks plugin discovery.
    # Prefer the PyQt5-bundled plugins path (or PyInstaller bundle) when available.
    env_keys = (
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
    )

    def _set_if_missing(key, value):
        if value and not os.environ.get(key):
            os.environ[key] = value

    def _first_existing_dir(candidates):
        for candidate in candidates:
            try:
                if candidate and Path(candidate).is_dir():
                    return str(Path(candidate))
            except Exception:
                continue
        return None

    def _platforms_dir(plugins_dir):
        if not plugins_dir:
            return None
        platforms = Path(plugins_dir) / "platforms"
        return str(platforms) if platforms.is_dir() else None

    try:
        # PyInstaller onefile/onedir support
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            base = Path(getattr(sys, "_MEIPASS"))
            plugin_candidates = [
                base / "PyQt5" / "Qt5" / "plugins",
                base / "PyQt5" / "Qt" / "plugins",
                base / "Qt5" / "plugins",
                base / "Qt" / "plugins",
                base / "plugins",
            ]
            plugins_dir = _first_existing_dir(plugin_candidates)
        else:
            # Normal (non-frozen) Python install
            plugins_dir = None
            try:
                plugins_dir = QLibraryInfo.location(QLibraryInfo.PluginsPath)
            except Exception:
                plugins_dir = None

            if not plugins_dir:
                try:
                    import PyQt5  # type: ignore

                    pyqt_root = Path(PyQt5.__file__).resolve().parent
                    plugins_dir = _first_existing_dir(
                        [
                            pyqt_root / "Qt5" / "plugins",
                            pyqt_root / "Qt" / "plugins",
                        ]
                    )
                except Exception:
                    plugins_dir = None

        platforms_dir = _platforms_dir(plugins_dir)

        if plugins_dir:
            try:
                QCoreApplication.addLibraryPath(str(plugins_dir))
            except Exception:
                pass

        if platforms_dir:
            _set_if_missing("QT_QPA_PLATFORM_PLUGIN_PATH", str(platforms_dir))

        # Allow end-users to override QPA platform when they know they need it
        # (e.g. headless Linux: offscreen).
        override_platform = os.environ.get("QODER_QT_QPA_PLATFORM")
        if override_platform:
            os.environ["QT_QPA_PLATFORM"] = override_platform

        # Keep existing env unless user explicitly requests reset via QODER_QT_RESET_ENV=1
        if os.environ.get("QODER_QT_RESET_ENV") == "1":
            for key in env_keys:
                os.environ.pop(key, None)
            if platforms_dir:
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms_dir)

        return {
            "plugins_dir": plugins_dir,
            "platforms_dir": platforms_dir,
            "frozen": bool(getattr(sys, "frozen", False)),
        }
    except Exception:
        return {"plugins_dir": None, "platforms_dir": None, "frozen": False}


class QoderResetGUI(QMainWindow):
    def __init__(self):
        """Initialize the main application window"""
        super().__init__()
        self.current_language = "en"  # Default to English
        self.init_translations()
        self.init_ui()

    def init_translations(self):
        """Initialize multilingual dictionary"""
        self.translations = {
            "zh": {  # Tiếng Trung
                "window_title": "Qoder-Free",
                "intro_text": "Qoder-Free 主要用于重置 Qoder 应用程序的用户身份信息",
                "operation_area": "操作区域:",
                "one_click_config": "一键修改配置",
                "close_qoder": "关闭 Qoder",
                "reset_machine_id": "重置机器 ID",
                "reset_telemetry": "重置遥测数据",
                "deep_identity_clean": "深度身份清理",
                "login_identity_clean": "清理登录身份",
                "hardware_fingerprint_reset": "硬件指纹重置",
                "backup_identity": "备份身份数据",
                "restore_identity": "恢复身份数据",
                "check_update": "检查更新",
                "advanced_options": "高级选项",
                "preserve_chat": "保留对话记录",
                "operation_log": "操作日志:",
                "clear_log": "清空日志",
                "github": "Github",
                "language": "语言",
                "diagnostic_report": "复制诊断报告",
                "windows_machine_diagnostics": "Windows 设备信息",
                "machine_diagnostics_title": "Windows 设备诊断",
                "machine_diagnostics_privacy": "结果可能包含硬件标识符和机器令牌；分享前请先检查。",
                "randomize_install_time_safestore": "重置安装时间和 SafeStore",
                "confirm_install_time_safestore": "此操作会更改 Windows 安装时间，并永久删除 SafeStore 中的所有内容。需要管理员权限。是否继续？",
                "install_time_safestore_title": "确认 Windows 系统更改",
                "randomize_adapter_macs": "随机更改所有网卡 MAC",
                "confirm_adapter_macs": "此操作会为所有符合条件的物理网卡设置随机 MAC 地址。网卡可能会短暂断开连接，部分驱动可能不支持。需要管理员权限。是否继续？",
                "adapter_macs_title": "确认 MAC 地址更改",
                "randomize_volume_serial": "更改 C: 卷序列号",
                "confirm_volume_serial": "此操作会使用 Microsoft Sysinternals VolumeID 随机更改 C: 卷序列号。需要管理员权限，NTFS 卷需要重启后生效。请先关闭使用该卷的应用。是否继续？",
                "volume_serial_title": "确认卷序列号更改",
                "issue_note": "注意: 本工具仅重置本地 Qoder 数据，服务端额度由 Qoder 控制。",
                # 日志消息
                "tool_started": "Qoder-Free 重置工具已启动",
                "log_cleared": "日志已清空",
                "qoder_running": "Qoder 正在运行",
                "qoder_not_running": "Qoder 未运行",
                "qoder_directory_exists": "Qoder 目录存在",
                "machine_id": "机器 ID",
                "telemetry_machine_id": "遥测机器 ID",
                "device_id": "设备 ID",
                "cache_directories_found": "个缓存目录",
                "chat_directories_found": "个对话相关目录",
                "identity_files_found": "个身份识别文件",
                "status_check_complete": "状态检查完成，可以开始操作",
                "backup_success": "身份数据已成功备份至:",
                "restore_success": "身份数据恢复成功！",
                # 对话框消息
                "qoder_detected_running": "检测到 Qoder 正在运行",
                "please_close_qoder": "请手动关闭 Qoder 应用程序",
                "confirm_one_click": "确认一键修改",
                "confirm_deep_clean": "确认深度清理",
                "confirm_login_clean": "确认清理登录身份",
                "confirm_backup": "确认备份当前的 Qoder 身份数据吗？",
                "confirm_restore": "确认从备份恢复 Qoder 身份数据吗？",
                "no_backups_found": "未找到任何可用备份",
                "update_available": "发现新版本",
                "latest_version_installed": "已是最新版本",
                "operation_complete": "操作完成",
                "operation_failed": "操作失败",
                "error": "错误",
                "success": "成功",
                "warning": "警告",
                "status_check": "状态检查",
            },
            "en": {  # Tiếng Anh
                "window_title": "Qoder-Free",
                "intro_text": "Qoder-Free is mainly used to reset user identity information of Qoder application",
                "operation_area": "Operation Area:",
                "one_click_config": "One-Click Configuration",
                "close_qoder": "Close Qoder",
                "reset_machine_id": "Reset Machine ID",
                "reset_telemetry": "Reset Telemetry",
                "deep_identity_clean": "Deep Identity Cleanup",
                "login_identity_clean": "Clean Login Identity",
                "hardware_fingerprint_reset": "Hardware Fingerprint Reset",
                "backup_identity": "Backup Identity",
                "restore_identity": "Restore Identity",
                "check_update": "Check Updates",
                "advanced_options": "Advanced Options",
                "preserve_chat": "Preserve Chat History",
                "operation_log": "Operation Log:",
                "clear_log": "Clear Log",
                "github": "Github",
                "language": "Language",
                "diagnostic_report": "Copy Diagnostic Report",
                "windows_machine_diagnostics": "Windows Device Details",
                "machine_diagnostics_title": "Windows Machine Diagnostics",
                "machine_diagnostics_privacy": "Results may include hardware identifiers and a machine token. Review them before sharing.",
                "randomize_install_time_safestore": "Randomize InstallTime & Clear SafeStore",
                "confirm_install_time_safestore": "This changes Windows InstallTime and permanently deletes all SafeStore contents. Administrator access is required. Continue?",
                "install_time_safestore_title": "Confirm Windows System Changes",
                "randomize_adapter_macs": "Randomize All Adapter MACs",
                "confirm_adapter_macs": "This assigns a random MAC address to every eligible physical network adapter. Adapters may disconnect briefly, and some drivers may not support this. Administrator access is required. Continue?",
                "adapter_macs_title": "Confirm MAC Address Changes",
                "randomize_volume_serial": "Change C: Volume Serial",
                "confirm_volume_serial": "This uses Microsoft Sysinternals VolumeID to randomize the C: volume serial. Administrator access is required, and NTFS changes take effect after a restart. Close applications using this volume first. Continue?",
                "volume_serial_title": "Confirm Volume Serial Change",
                "issue_note": "Note: this tool can reset local Qoder data, but server-side trial credits and model access are controlled by Qoder.",
                # Log messages
                "tool_started": "Qoder-Free reset tool started",
                "log_cleared": "Log cleared",
                "qoder_running": "Qoder is running",
                "qoder_not_running": "Qoder is not running",
                "qoder_directory_exists": "Qoder directory exists",
                "machine_id": "Machine ID",
                "telemetry_machine_id": "Telemetry Machine ID",
                "device_id": "Device ID",
                "cache_directories_found": "cache directories found",
                "chat_directories_found": "chat-related directories found",
                "identity_files_found": "identity files found",
                "status_check_complete": "Status check completed, ready to operate",
                "backup_success": "Identity data successfully backed up to:",
                "restore_success": "Identity data restored successfully!",
                # Dialog messages
                "qoder_detected_running": "Qoder Detected Running",
                "please_close_qoder": "Please close Qoder application manually",
                "confirm_one_click": "Confirm One-Click Reset",
                "confirm_deep_clean": "Confirm Deep Cleanup",
                "confirm_login_clean": "Confirm Login Identity Cleanup",
                "confirm_close_qoder": "Confirm Close Qoder",
                "confirm_reset_machine_id": "Confirm Machine ID Reset",
                "confirm_reset_telemetry": "Confirm Telemetry Reset",
                "confirm_hardware_fingerprint_reset": "Confirm Hardware Fingerprint Reset",
                "confirm_backup": "Confirm backup of current Qoder identity data?",
                "confirm_restore": "Confirm restore of Qoder identity data from backup?",
                "no_backups_found": "No backups found",
                "update_available": "New version available",
                "latest_version_installed": "You are using the latest version",
                "operation_complete": "Operation Complete",
                "operation_failed": "Operation Failed",
                "error": "Error",
                "success": "Success",
                "warning": "Warning",
                "status_check": "Status Check",
            },
            "ru": {  # Tiếng Nga
                "window_title": "Qoder-Free",
                "intro_text": "Qoder-Free в основном используется для сброса пользовательской информации приложения Qoder",
                "operation_area": "Область операций:",
                "one_click_config": "Одним кликом",
                "close_qoder": "Закрыть Qoder",
                "reset_machine_id": "Сбросить ID машины",
                "reset_telemetry": "Сбросить телеметрию",
                "deep_identity_clean": "Глубокая очистка",
                "login_identity_clean": "Очистить вход",
                "hardware_fingerprint_reset": "Сброс железа",
                "backup_identity": "Резервная копия",
                "restore_identity": "Восстановление",
                "check_update": "Проверить обновления",
                "advanced_options": "Дополнительно",
                "preserve_chat": "Сохранить чат",
                "operation_log": "Журнал операций:",
                "clear_log": "Очистить журнал",
                "github": "Github",
                "language": "Язык",
                "diagnostic_report": "Копировать отчет",
                "windows_machine_diagnostics": "Данные устройства Windows",
                "machine_diagnostics_title": "Диагностика Windows",
                "machine_diagnostics_privacy": "Результаты могут содержать идентификаторы оборудования и токен машины. Проверьте их перед отправкой.",
                "randomize_install_time_safestore": "Изменить время установки и очистить SafeStore",
                "confirm_install_time_safestore": "Будет изменено время установки Windows и безвозвратно удалено содержимое SafeStore. Требуются права администратора. Продолжить?",
                "install_time_safestore_title": "Подтверждение изменений Windows",
                "randomize_adapter_macs": "Изменить MAC всех адаптеров",
                "confirm_adapter_macs": "Для всех подходящих физических сетевых адаптеров будут заданы случайные MAC-адреса. Возможны кратковременные отключения; некоторые драйверы могут не поддерживать эту функцию. Требуются права администратора. Продолжить?",
                "adapter_macs_title": "Подтверждение изменения MAC-адресов",
                "randomize_volume_serial": "Изменить серийный номер диска C:",
                "confirm_volume_serial": "С помощью Microsoft Sysinternals VolumeID будет изменен серийный номер диска C:. Требуются права администратора; для NTFS изменения вступят в силу после перезагрузки. Сначала закройте приложения, использующие этот диск. Продолжить?",
                "volume_serial_title": "Подтверждение изменения серийного номера диска",
                "issue_note": "Примечание: инструмент сбрасывает локальные данные Qoder; баланс триала контролируется сервером.",
                # Сообщения журнала
                "tool_started": "Инструмент сброса Qoder-Free запущен",
                "log_cleared": "Журнал очищен",
                "qoder_running": "Qoder запущен",
                "qoder_not_running": "Qoder не запущен",
                "qoder_directory_exists": "Папка Qoder существует",
                "machine_id": "ID машины",
                "telemetry_machine_id": "ID машины телеметрии",
                "device_id": "ID устройства",
                "cache_directories_found": "папок кеша найдено",
                "chat_directories_found": "папок чата найдено",
                "identity_files_found": "файлов идентификации найдено",
                "status_check_complete": "Проверка статуса завершена, готов к работе",
                "backup_success": "Данные успешно сохранены в:",
                "restore_success": "Данные успешно восстановлены!",
                # Диалоговые сообщения
                "qoder_detected_running": "Обнаружен запущенный Qoder",
                "please_close_qoder": "Пожалуйста, закройте приложение Qoder вручную",
                "confirm_one_click": "Подтвердить сброс одним кликом",
                "confirm_deep_clean": "Подтвердить глубокую очистку",
                "confirm_login_clean": "Подтвердить очистку входа",
                "confirm_backup": "Подтвердить создание резервной копии?",
                "confirm_restore": "Подтвердить восстановление из копии?",
                "no_backups_found": "Резервные копии не найдены",
                "update_available": "Доступна новая версия",
                "latest_version_installed": "У вас установлена последняя версия",
                "operation_complete": "Операция завершена",
                "operation_failed": "Операция не удалась",
                "error": "Ошибка",
                "success": "Успех",
                "warning": "Предупреждение",
                "status_check": "Проверка статуса",
            },
            "pt-br": {  # Tiếng Bồ Đào Nha (Brazil)
                "window_title": "Qoder-Free",
                "intro_text": "Qoder-Free é principalmente usado para redefinir as informações de identidade do usuário do aplicativo Qoder",
                "operation_area": "Área de Operações:",
                "one_click_config": "Configuração com um clique",
                "close_qoder": "Fechar Qoder",
                "reset_machine_id": "Redefinir ID da Máquina",
                "reset_telemetry": "Redefinir Telemetria",
                "deep_identity_clean": "Limpeza Profunda de Identidade",
                "login_identity_clean": "Limpar Login",
                "hardware_fingerprint_reset": "Reset de Hardware",
                "backup_identity": "Backup de Identidade",
                "restore_identity": "Restaurar Identidade",
                "check_update": "Verificar Atualizações",
                "advanced_options": "Opções Avançadas",
                "preserve_chat": "Preservar Histórico do chat",
                "operation_log": "Log de Operações:",
                "clear_log": "Limpar Log",
                "github": "Github",
                "language": "Idioma",
                "diagnostic_report": "Copiar Relatório",
                "windows_machine_diagnostics": "Dados do dispositivo Windows",
                "machine_diagnostics_title": "Diagnóstico do Windows",
                "machine_diagnostics_privacy": "Os resultados podem conter identificadores de hardware e um token da máquina. Revise antes de compartilhar.",
                "randomize_install_time_safestore": "Alterar InstallTime e limpar SafeStore",
                "confirm_install_time_safestore": "Isso altera o InstallTime do Windows e exclui permanentemente o conteúdo do SafeStore. É necessário acesso de administrador. Continuar?",
                "install_time_safestore_title": "Confirmar alterações do Windows",
                "randomize_adapter_macs": "Alterar MAC de todos os adaptadores",
                "confirm_adapter_macs": "Um endereço MAC aleatório será definido para cada adaptador físico elegível. Os adaptadores podem desconectar brevemente e alguns drivers podem não oferecer suporte. É necessário acesso de administrador. Continuar?",
                "adapter_macs_title": "Confirmar alteração dos endereços MAC",
                "randomize_volume_serial": "Alterar serial do volume C:",
                "confirm_volume_serial": "Isso usa o Microsoft Sysinternals VolumeID para alterar aleatoriamente o serial do volume C:. É necessário acesso de administrador; alterações em NTFS só entram em vigor após reiniciar. Feche primeiro os aplicativos que usam este volume. Continuar?",
                "volume_serial_title": "Confirmar alteração do serial do volume",
                "issue_note": "Nota: esta ferramenta redefine dados locais do Qoder; o crédito de avaliação é controlado pelo servidor.",
                # Mensagens de log
                "tool_started": "Ferramenta de redefinição Qoder-Free iniciada",
                "log_cleared": "Log limpo",
                "qoder_running": "Qoder está em execução",
                "qoder_not_running": "Qoder não está em execução",
                "qoder_directory_exists": "Diretório Qoder existe",
                "machine_id": "ID da Máquina",
                "telemetry_machine_id": "ID da Máquina de Telemetria",
                "device_id": "ID do Dispositivo",
                "cache_directories_found": "diretórios de cache encontrados",
                "chat_directories_found": "diretórios relacionados ao chat encontrados",
                "identity_files_found": "arquivos de identidade encontrados",
                "status_check_complete": "Verificação de status concluída, pronto para operar",
                "backup_success": "Dados de identidade salvos em:",
                "restore_success": "Dados de identidade restaurados com sucesso!",
                # Mensagens de diálogo
                "qoder_detected_running": "Qoder Detectado em Execução",
                "please_close_qoder": "Por favor, feche o aplicativo Qoder manualmente",
                "confirm_one_click": "Confirmar Redefinição com um clique",
                "confirm_deep_clean": "Confirmar Limpeza Profunda",
                "confirm_login_clean": "Confirmar Limpeza de Identidade de Login",
                "confirm_backup": "Confirmar backup dos dados de identidade?",
                "confirm_restore": "Confirmar restauração da identidade?",
                "no_backups_found": "Nenhum backup encontrado",
                "update_available": "Nova versão disponível",
                "latest_version_installed": "Você está usando a versão mais recente",
                "operation_complete": "Operação Concluída",
                "operation_failed": "Operação Falhou",
                "error": "Erro",
                "success": "Sucesso",
                "warning": "Aviso",
                "status_check": "Verificação de Status",
            },
            "vi": {  # Tiếng Việt
                "window_title": "Qoder-Free: Công Cụ Làm Sạch",
                "intro_text": "Công cụ giúp bạn đặt lại và làm sạch thông tin nhận dạng của ứng dụng Qoder một cách dễ dàng và an toàn.",
                "operation_area": "Khu Vực Thao Tác:",
                "one_click_config": "Cấu Hình Một Chạm",
                "close_qoder": "Đóng Qoder",
                "reset_machine_id": "Đặt Lại ID Máy",
                "reset_telemetry": "Đặt Lại Dữ Liệu Điện Toán",
                "deep_identity_clean": "Làm Sạch Danh Tính Sâu",
                "login_identity_clean": "Xóa Thông Tin Đăng Nhập",
                "hardware_fingerprint_reset": "Đặt Lại Dấu Vân Tay Phần Cứng",
                "backup_identity": "Sao Lưu Danh Tính",
                "restore_identity": "Khôi Phục Danh Tính",
                "check_update": "Kiểm Tra Cập Nhật",
                "advanced_options": "Tùy Chọn Nâng Cao",
                "preserve_chat": "Giữ Lại Lịch Sử Trò Chuyện",
                "operation_log": "Nhật Ký Thao Tác:",
                "clear_log": "Xóa Nhật Ký",
                "github": "Liên Kết GitHub",
                "language": "Ngôn Ngữ",
                "diagnostic_report": "Sao Chép Báo Cáo Chẩn Đoán",
                "windows_machine_diagnostics": "Thông Tin Thiết Bị Windows",
                "machine_diagnostics_title": "Chẩn Đoán Máy Windows",
                "machine_diagnostics_privacy": "Kết quả có thể chứa mã nhận dạng phần cứng và mã thông báo máy. Hãy kiểm tra trước khi chia sẻ.",
                "randomize_install_time_safestore": "Đổi InstallTime và xóa SafeStore",
                "confirm_install_time_safestore": "Thao tác này thay đổi InstallTime của Windows và xóa vĩnh viễn nội dung SafeStore. Cần quyền quản trị viên. Tiếp tục?",
                "install_time_safestore_title": "Xác nhận thay đổi Windows",
                "randomize_adapter_macs": "Đổi MAC tất cả bộ điều hợp",
                "confirm_adapter_macs": "Thao tác này đặt địa chỉ MAC ngẫu nhiên cho mọi bộ điều hợp mạng vật lý đủ điều kiện. Kết nối có thể gián đoạn trong thời gian ngắn và một số trình điều khiển có thể không hỗ trợ. Cần quyền quản trị viên. Tiếp tục?",
                "adapter_macs_title": "Xác nhận thay đổi địa chỉ MAC",
                "randomize_volume_serial": "Đổi số sê-ri ổ C:",
                "confirm_volume_serial": "Thao tác này dùng Microsoft Sysinternals VolumeID để đổi ngẫu nhiên số sê-ri ổ C:. Cần quyền quản trị viên; thay đổi trên NTFS có hiệu lực sau khi khởi động lại. Hãy đóng ứng dụng đang dùng ổ đĩa này trước. Tiếp tục?",
                "volume_serial_title": "Xác nhận đổi số sê-ri ổ đĩa",
                "issue_note": "Lưu ý: công cụ chỉ đặt lại dữ liệu Qoder cục bộ; trial credit và quyền dùng model có thể do máy chủ Qoder quyết định.",
                # Các thông báo nhật ký
                "tool_started": "Công cụ đặt lại Qoder-Free đã được khởi động",
                "log_cleared": "Nhật ký đã được xóa",
                "qoder_running": "Qoder đang chạy",
                "qoder_not_running": "Qoder không chạy",
                "qoder_directory_exists": "Thư mục Qoder tồn tại",
                "machine_id": "ID Máy",
                "telemetry_machine_id": "ID Máy Điện Toán",
                "device_id": "ID Thiết Bị",
                "cache_directories_found": "thư mục bộ nhớ đệm được tìm thấy",
                "chat_directories_found": "thư mục liên quan đến trò chuyện được tìm thấy",
                "identity_files_found": "tệp nhận dạng được tìm thấy",
                "status_check_complete": "Kiểm tra trạng thái hoàn tất, sẵn sàng thực hiện",
                "backup_success": "Đã sao lưu dữ liệu nhận dạng vào:",
                "restore_success": "Khôi phục dữ liệu nhận dạng thành công!",
                # Các thông báo hộp thoại
                "qoder_detected_running": "Phát Hiện Qoder Đang Chạy",
                "please_close_qoder": "Vui lòng đóng ứng dụng Qoder theo cách thủ công",
                "confirm_one_click": "Xác Nhận Đặt Lại Một Chạm",
                "confirm_deep_clean": "Xác Nhận Làm Sạch Sâu",
                "confirm_login_clean": "Xác Nhận Xóa Thông Tin Đăng Nhập",
                "confirm_close_qoder": "Xác Nhận Đóng Qoder",
                "confirm_reset_machine_id": "Xác Nhận Đặt Lại ID Máy",
                "confirm_reset_telemetry": "Xác Nhận Đặt Lại Telemetry",
                "confirm_hardware_fingerprint_reset": "Xác Nhận Đặt Lại Dấu Vân Tay Phần Cứng",
                "confirm_backup": "Xác nhận sao lưu dữ liệu nhận dạng Qoder hiện tại?",
                "confirm_restore": "Xác nhận khôi phục nhận dạng Qoder từ bản sao lưu?",
                "no_backups_found": "Không tìm thấy bản sao lưu nào",
                "update_available": "Đã có phiên bản mới",
                "latest_version_installed": "Bạn đang dùng phiên bản mới nhất",
                "operation_complete": "Thao Tác Hoàn Tất",
                "operation_failed": "Thao Tác Thất Bại",
                "error": "Lỗi",
                "success": "Thành Công",
                "warning": "Cảnh Báo",
                "status_check": "Kiểm Tra Trạng Thái",
            },
        }

    def tr(self, key):
        """Get translation text for the current language"""
        return (
            self.translations.get(self.current_language, {}).get(key)
            or self.translations.get("en", {}).get(key)
            or key
        )

    def init_ui(self):
        """Initialize the user interface"""
        # Set window properties
        self.setWindowTitle(self.tr("window_title"))
        self.setMinimumSize(860, 680)
        self.resize(940, 870)

        # Set application-wide font
        font = QFont("Segoe UI", 10)
        QApplication.setFont(font)

        # Create main widget and layout
        main_widget = QWidget()
        main_widget.setObjectName("appRoot")
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(24, 22, 24, 18)
        main_layout.setSpacing(14)

        # Title Label
        self.title_label = QLabel(self.tr("window_title"))
        self.title_label.setObjectName("titleLabel")
        main_layout.addWidget(self.title_label)

        # Intro Label
        self.intro_label = QLabel(self.tr("intro_text"))
        self.intro_label.setObjectName("introLabel")
        self.intro_label.setWordWrap(True)
        main_layout.addWidget(self.intro_label)

        self.issue_note_label = QLabel(self.tr("issue_note"))
        self.issue_note_label.setObjectName("issueNoteLabel")
        self.issue_note_label.setWordWrap(True)
        main_layout.addWidget(self.issue_note_label)

        # Language Selector
        language_layout = QHBoxLayout()
        language_layout.setSpacing(10)
        self.language_label = QLabel(self.tr("language"))
        self.language_selector = QComboBox()
        self.language_selector.addItems(["English", "Tiếng Việt", "中文", "Русский"])
        self.language_selector.setCurrentText("English")
        self.language_selector.currentTextChanged.connect(self.change_language)

        language_layout.addWidget(self.language_label)
        language_layout.addWidget(self.language_selector)
        language_layout.addStretch()
        main_layout.addLayout(language_layout)

        # Nút một chạm
        self.one_click_btn = self.create_styled_button(
            self.tr("one_click_config"), "#1f6feb", self.one_click_reset
        )
        self.one_click_btn.setMinimumHeight(52)
        main_layout.addWidget(self.one_click_btn)

        # Bố cục các nút chức năng
        self.operation_title = QLabel(self.tr("operation_area"))
        self.operation_title.setObjectName("sectionLabel")
        main_layout.addWidget(self.operation_title)

        button_layout = QGridLayout()
        button_layout.setSpacing(10)

        # Nút đóng Qoder
        self.close_qoder_btn = self.create_styled_button(
            self.tr("close_qoder"), "#c2410c", self.close_qoder
        )
        button_layout.addWidget(self.close_qoder_btn, 0, 0)

        # Nút đặt lại ID máy
        self.reset_machine_id_btn = self.create_styled_button(
            self.tr("reset_machine_id"), "#2563eb", self.reset_machine_id
        )
        button_layout.addWidget(self.reset_machine_id_btn, 0, 1)

        # Nút đặt lại dữ liệu điện toán
        self.reset_telemetry_btn = self.create_styled_button(
            self.tr("reset_telemetry"), "#15803d", self.reset_telemetry
        )
        button_layout.addWidget(self.reset_telemetry_btn, 0, 2)

        self.login_clean_btn = self.create_styled_button(
            self.tr("login_identity_clean"), "#475569", self.login_identity_cleanup
        )
        button_layout.addWidget(self.login_clean_btn, 1, 0)

        # Nút làm sạch danh tính sâu
        self.deep_clean_btn = self.create_styled_button(
            self.tr("deep_identity_clean"), "#a16207", self.deep_identity_cleanup
        )
        button_layout.addWidget(self.deep_clean_btn, 1, 1)

        self.hardware_reset_btn = self.create_styled_button(
            self.tr("hardware_fingerprint_reset"),
            "#7c3aed",
            self.hardware_fingerprint_reset,
        )
        button_layout.addWidget(self.hardware_reset_btn, 1, 2)

        # Hàng mới: Sao lưu, Khôi phục, Kiểm tra cập nhật
        self.backup_btn = self.create_styled_button(
            self.tr("backup_identity"), "#0891b2", self.backup_identity
        )
        button_layout.addWidget(self.backup_btn, 2, 0)

        self.restore_btn = self.create_styled_button(
            self.tr("restore_identity"), "#4f46e5", self.restore_identity
        )
        button_layout.addWidget(self.restore_btn, 2, 1)

        self.check_update_btn = self.create_styled_button(
            self.tr("check_update"), "#0284c7", self.check_update_action
        )
        button_layout.addWidget(self.check_update_btn, 2, 2)

        self.diagnostic_btn = self.create_styled_button(
            self.tr("diagnostic_report"), "#334155", self.copy_diagnostic_report
        )
        button_layout.addWidget(self.diagnostic_btn, 3, 0)

        self.machine_diagnostics_btn = self.create_styled_button(
            self.tr("windows_machine_diagnostics"),
            "#475569",
            self.show_windows_machine_diagnostics,
        )
        button_layout.addWidget(self.machine_diagnostics_btn, 4, 0)

        self.install_time_safestore_btn = self.create_styled_button(
            self.tr("randomize_install_time_safestore"),
            "#b45309",
            self.randomize_install_time_and_clear_safestore,
        )
        self.install_time_safestore_btn.setEnabled(platform.system() == "Windows")
        button_layout.addWidget(self.install_time_safestore_btn, 4, 1)

        self.adapter_macs_btn = self.create_styled_button(
            self.tr("randomize_adapter_macs"),
            "#be123c",
            self.randomize_network_adapter_macs,
        )
        self.adapter_macs_btn.setEnabled(platform.system() == "Windows")
        button_layout.addWidget(self.adapter_macs_btn, 4, 2)

        self.volume_serial_btn = self.create_styled_button(
            self.tr("randomize_volume_serial"),
            "#7c2d12",
            self.randomize_c_volume_serial,
        )
        self.volume_serial_btn.setEnabled(platform.system() == "Windows")
        button_layout.addWidget(self.volume_serial_btn, 5, 0)

        self.github_btn = self.create_styled_button(
            self.tr("github"), "#0f766e", self.open_github
        )
        button_layout.addWidget(self.github_btn, 3, 1)

        self.clear_log_btn = self.create_styled_button(
            self.tr("clear_log"), "#64748b", self.clear_log
        )
        button_layout.addWidget(self.clear_log_btn, 3, 2)

        # Thêm bố cục nút vào bố cục chính
        main_layout.addLayout(button_layout)

        # Preserve Chat Checkbox
        self.preserve_chat_checkbox = QCheckBox(self.tr("preserve_chat"))
        self.preserve_chat_checkbox.setChecked(True)
        main_layout.addWidget(self.preserve_chat_checkbox)

        # Log Area
        log_layout = QVBoxLayout()
        self.log_title = QLabel(self.tr("operation_log"))
        self.log_title.setObjectName("sectionLabel")
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(190)

        log_layout.addWidget(self.log_title)
        log_layout.addWidget(self.log_text)

        main_layout.addLayout(log_layout)

        # Set main layout
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Set overall window style
        self.setStyleSheet("""
            QMainWindow, QWidget#appRoot {
                background-color: #f7f8fa;
            }
            QWidget {
                color: #111827;
            }
            QLabel#titleLabel {
                color: #0f172a;
                font-size: 26px;
                font-weight: 700;
            }
            QLabel#introLabel {
                color: #475569;
                font-size: 13px;
                line-height: 1.35;
            }
            QLabel#issueNoteLabel {
                background-color: #fff7ed;
                border: 1px solid #fed7aa;
                border-radius: 6px;
                color: #7c2d12;
                padding: 8px 10px;
            }
            QLabel#sectionLabel {
                color: #334155;
                font-size: 13px;
                font-weight: 700;
                margin-top: 4px;
            }
            QComboBox {
                background-color: white;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 6px 10px;
                min-width: 150px;
            }
            QCheckBox {
                color: #334155;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QTextEdit {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 6px;
                color: #dbeafe;
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)

        # Status bar with version info
        self.statusBar().showMessage(f"Qoder-Free v{__version__}")
        self.statusBar().setStyleSheet("""
            QStatusBar {
                background-color: #ecf0f1;
                color: #7f8c8d;
                font-size: 12px;
            }
        """)

        # Initialize status check
        self.initialize_status_check()

    def create_styled_button(self, text, color, connect_func):
        """Tạo nút với phong cách thống nhất"""
        btn = QPushButton(text)
        btn.setMinimumHeight(42)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-size: 12px;
                font-weight: 700;
                border: none;
                border-radius: 6px;
                padding: 9px 12px;
            }}
            QPushButton:hover {{
                background-color: {color}EE;
            }}
            QPushButton:pressed {{
                background-color: {color}CC;
            }}
            QPushButton:disabled {{
                background-color: #94a3b8;
                color: #e2e8f0;
            }}
        """)
        btn.clicked.connect(connect_func)
        return btn

    def change_language(self, language_text):
        """Change the application language"""
        try:
            # Normalize language text
            language_text = language_text.strip()

            # Map language display text to language codes
            language_map = {
                "English": "en",
                "Tiếng Việt": "vi",
                "中文": "zh",
                "Русский": "ru",
            }

            # Get language code, default to English
            language = language_map.get(language_text, "en")

            # Update current language
            self.current_language = language

            # Update UI elements with translations
            self.setWindowTitle(self.tr("window_title"))

            # Update labels
            self.title_label.setText(self.tr("window_title"))
            self.intro_label.setText(self.tr("intro_text"))
            self.issue_note_label.setText(self.tr("issue_note"))
            self.language_label.setText(self.tr("language"))
            self.operation_title.setText(self.tr("operation_area"))
            self.log_title.setText(self.tr("operation_log"))

            # Update buttons with translations
            button_translations = {
                "one_click_btn": "one_click_config",
                "close_qoder_btn": "close_qoder",
                "reset_machine_id_btn": "reset_machine_id",
                "reset_telemetry_btn": "reset_telemetry",
                "login_clean_btn": "login_identity_clean",
                "deep_clean_btn": "deep_identity_clean",
                "hardware_reset_btn": "hardware_fingerprint_reset",
                "backup_btn": "backup_identity",
                "restore_btn": "restore_identity",
                "check_update_btn": "check_update",
                "diagnostic_btn": "diagnostic_report",
                "machine_diagnostics_btn": "windows_machine_diagnostics",
                "install_time_safestore_btn": "randomize_install_time_safestore",
                "adapter_macs_btn": "randomize_adapter_macs",
                "volume_serial_btn": "randomize_volume_serial",
                "clear_log_btn": "clear_log",
                "github_btn": "github",
            }

            # Update buttons with translated texts
            for btn_name, translation_key in button_translations.items():
                if hasattr(self, btn_name):
                    getattr(self, btn_name).setText(self.tr(translation_key))

            # Update checkbox
            self.preserve_chat_checkbox.setText(self.tr("preserve_chat"))

            # Optional: log the language change
            self.log(f"Language changed to: {language_text}")

        except Exception as e:
            # Log any errors during language change
            self.log(f"Error changing language: {e}")
            # Fallback to English
            self.current_language = "en"

        # Ensure language selector reflects the current selection
        language_index = self.language_selector.findText(language_text)
        if language_index >= 0:
            self.language_selector.setCurrentIndex(language_index)

    def update_ui_text(self):
        """更新界面文本"""
        # 更新窗口标题
        self.setWindowTitle(self.tr("window_title"))

        # 更新标签文本
        self.title_label.setText(self.tr("window_title"))
        self.intro_label.setText(self.tr("intro_text"))
        self.issue_note_label.setText(self.tr("issue_note"))
        self.language_label.setText(self.tr("language"))
        self.operation_title.setText(self.tr("operation_area"))
        self.log_title.setText(self.tr("operation_log"))

        # 更新按钮文本
        self.one_click_btn.setText(self.tr("one_click_config"))
        self.close_qoder_btn.setText(self.tr("close_qoder"))
        self.reset_machine_id_btn.setText(self.tr("reset_machine_id"))
        self.reset_telemetry_btn.setText(self.tr("reset_telemetry"))
        self.deep_clean_btn.setText(self.tr("deep_identity_clean"))
        self.login_clean_btn.setText(self.tr("login_identity_clean"))
        self.hardware_reset_btn.setText(self.tr("hardware_fingerprint_reset"))
        self.backup_btn.setText(self.tr("backup_identity"))
        self.restore_btn.setText(self.tr("restore_identity"))
        self.check_update_btn.setText(self.tr("check_update"))
        self.diagnostic_btn.setText(self.tr("diagnostic_report"))
        self.machine_diagnostics_btn.setText(self.tr("windows_machine_diagnostics"))
        self.install_time_safestore_btn.setText(
            self.tr("randomize_install_time_safestore")
        )
        self.adapter_macs_btn.setText(self.tr("randomize_adapter_macs"))
        self.volume_serial_btn.setText(self.tr("randomize_volume_serial"))
        self.clear_log_btn.setText(self.tr("clear_log"))
        self.github_btn.setText(self.tr("github"))

        # 更新复选框文本
        self.preserve_chat_checkbox.setText(self.tr("preserve_chat"))

        # 清空日志并重新初始化
        self.log_text.clear()
        self.log("Qoder-Free reset tool started")
        self.log("=" * 50)

    def log(self, message):
        """Log messages with timestamp in English"""
        if getattr(self, "_reset_cleanup_failures", None) is not None:
            message_text = str(message)
            if any(
                marker in message_text.lower()
                for marker in (
                    "cleanup failed",
                    "failed to clear",
                    "failed to clean",
                    "failed to remove",
                )
            ):
                self._reset_cleanup_failures.append(message_text)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)

    def initialize_status_check(self):
        """Kiểm tra trạng thái ban đầu của Qoder"""
        try:
            self.log("Qoder-Free reset tool started")
            self.log("=" * 50)

            # 1. Kiểm tra trạng thái Qoder
            self.log("1. Checking Qoder process status...")
            is_running = self.is_qoder_running()
            if is_running:
                self.log("   ❌ Qoder is running")
            else:
                self.log("   ✅ Qoder is not running")

            # 2. Kiểm tra thư mục Qoder
            self.log("2. Checking Qoder directory...")
            qoder_support_dir = self.get_qoder_data_dir()
            if qoder_support_dir.exists():
                self.log("   ✅ Qoder directory exists")
            else:
                self.log("   ❌ Qoder directory not found")

            # 3. Kiểm tra file Machine ID
            self.log("3. Checking Machine ID file...")
            machine_id_file = qoder_support_dir / "machineid"
            if machine_id_file.exists():
                with open(machine_id_file, "r") as f:
                    machine_id = f.read().strip()
                self.log(f"   ✅ Machine ID: {machine_id}")
            else:
                self.log("   ❌ Machine ID file not found")

            # 4. Kiểm tra file Telemetry
            self.log("4. Checking Telemetry data files...")
            storage_json_file = qoder_support_dir / "User/globalStorage/storage.json"
            if storage_json_file.exists():
                with open(storage_json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                telemetry_machine_id = data.get("telemetry.machineId", "N/A")
                device_id = data.get("telemetry.devDeviceId", "N/A")

                self.log(f"   ✅ Telemetry Machine ID: {telemetry_machine_id[:16]}...")
                self.log(f"   ✅ Device ID: {device_id}")
            else:
                self.log("   ❌ Telemetry data file not found")

            # 5. Kiểm tra thư mục cache
            self.log("5. Checking cache directories...")
            cache_dirs = list(qoder_support_dir.glob("**/Cache*"))
            self.log(f"   ✅ Found {len(cache_dirs)}/7 cache directories")

            # 6. Kiểm tra thư mục chat
            self.log("6. Checking chat-related directories...")
            chat_dirs = list(qoder_support_dir.glob("**/Chat*"))
            self.log(f"   ✅ Found {len(chat_dirs)}/4 chat-related directories")

            # 7. Kiểm tra file nhận dạng
            self.log("7. Checking identity files...")
            identity_files = list(qoder_support_dir.glob("**/identity*"))
            self.log(f"   ✅ Found {len(identity_files)}/6 identity files")

            # 8. Kiểm tra SharedClientCache
            self.log("8. Checking SharedClientCache internal files...")
            shared_cache_files = list(qoder_support_dir.glob("**/SharedClientCache*"))
            self.log(
                f"   ✅ SharedClientCache internal files: {len(shared_cache_files)}/4"
            )

            # 9. Kiểm tra Keychain và chứng chỉ
            self.log("9. Checking Keychain and certificate storage...")
            cert_files = list(qoder_support_dir.glob("**/cert*"))
            self.log(f"   ✅ Found {len(cert_files)}/3 certificate/security files")

            # 10. Kiểm tra nhật ký hoạt động người dùng
            self.log("10. Checking user activity logs...")
            activity_logs = list(qoder_support_dir.glob("**/activity*"))
            self.log(f"   ✅ Found {len(activity_logs)}/6 activity log files")

            # 11. Kiểm tra file dấu vân tay thiết bị
            self.log("11. Checking device fingerprint-related files...")
            fingerprint_files = list(qoder_support_dir.glob("**/fingerprint*"))
            self.log(f"   ✅ Found {len(fingerprint_files)}/7 device fingerprint files")

            self.log("=" * 50)
            self.log("Status check completed, ready to operate")

        except Exception as e:
            self.log(f"Error during status check: {e}")

    def clear_log(self):
        """Clear log contents"""
        self.log_text.clear()
        self.log("Log cleared")

    def collect_diagnostic_report(self):
        """Collect non-secret state useful for GitHub issue reports."""
        qoder_support_dir = self.get_qoder_data_dir()
        lines = [
            f"Qoder-Free version: {__version__}",
            f"OS: {platform.system()} {platform.release()} ({platform.machine()})",
            f"Python: {platform.python_version()}",
            f"Qoder running: {self.is_qoder_running()}",
            f"Qoder data dir: {qoder_support_dir}",
            f"Qoder data dir exists: {qoder_support_dir.exists()}",
        ]

        machine_id_file = qoder_support_dir / "machineid"
        lines.append(f"machineid file exists: {machine_id_file.exists()}")
        if machine_id_file.exists():
            try:
                machine_id = machine_id_file.read_text(encoding="utf-8").strip()
                lines.append(f"machineid prefix: {machine_id[:8]}...")
            except Exception as exc:
                lines.append(f"machineid read error: {exc}")

        storage_json_file = (
            qoder_support_dir / "User" / "globalStorage" / "storage.json"
        )
        lines.append(f"storage.json exists: {storage_json_file.exists()}")
        if storage_json_file.exists():
            try:
                data = json.loads(storage_json_file.read_text(encoding="utf-8"))
                telemetry_keys = sorted(
                    key for key in data.keys() if "telemetry" in str(key).lower()
                )
                login_like_keys = sorted(
                    key
                    for key in data.keys()
                    if any(
                        token in str(key).lower()
                        for token in ("auth", "token", "login", "session")
                    )
                )
                lines.append(f"telemetry key count: {len(telemetry_keys)}")
                lines.append(f"telemetry keys: {', '.join(telemetry_keys) or 'none'}")
                lines.append(f"login/session-like key count: {len(login_like_keys)}")
            except Exception as exc:
                lines.append(f"storage.json parse error: {exc}")

        lines.append("")
        lines.append(
            "Limit note: local reset can change local identifiers, but trial credits and model access may be decided server-side by Qoder."
        )
        return "\n".join(lines)

    def copy_diagnostic_report(self):
        """Copy diagnostic report and log it for issue follow-up."""
        try:
            report = self.collect_diagnostic_report()
            QApplication.clipboard().setText(report)
            self.log("Diagnostic report copied to clipboard.")
            self.log("Use it when replying to GitHub issues #13/#14.")
            QMessageBox.information(
                self,
                self.tr("success"),
                "Diagnostic report copied to clipboard.",
            )
        except Exception as e:
            self.log(f"Error collecting diagnostic report: {e}")
            QMessageBox.critical(
                self,
                self.tr("error"),
                f"Failed to collect diagnostic report: {e}",
            )

    def show_windows_machine_diagnostics(self):
        """Collect and display Windows machine details in a read-only dialog."""
        try:
            report = collect_windows_machine_diagnostics()
            dialog = QDialog(self)
            dialog.setWindowTitle(self.tr("machine_diagnostics_title"))
            dialog.resize(760, 600)

            layout = QVBoxLayout(dialog)
            privacy_note = QLabel(self.tr("machine_diagnostics_privacy"))
            privacy_note.setWordWrap(True)
            layout.addWidget(privacy_note)

            report_view = QTextEdit()
            report_view.setReadOnly(True)
            report_view.setPlainText(report)
            layout.addWidget(report_view)

            buttons = QDialogButtonBox(QDialogButtonBox.Close)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            self.log("Windows machine diagnostics collected.")
            dialog.exec_()
        except Exception as exc:
            self.log(f"Error collecting Windows machine diagnostics: {exc}")
            QMessageBox.critical(
                self,
                self.tr("error"),
                f"Failed to collect Windows machine diagnostics: {exc}",
            )

    def randomize_install_time_and_clear_safestore(self):
        """Confirm and apply Windows InstallTime and SafeStore changes."""
        reply = QMessageBox.warning(
            self,
            self.tr("install_time_safestore_title"),
            self.tr("confirm_install_time_safestore"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            report = randomize_windows_install_time_and_clear_safestore()
            self.log(f"Windows InstallTime/SafeStore operation completed: {report}")
            QMessageBox.information(
                self,
                self.tr("success"),
                f"Windows InstallTime/SafeStore operation completed:\n{report}",
            )
        except Exception as exc:
            self.log(f"Error changing Windows InstallTime/SafeStore: {exc}")
            QMessageBox.critical(
                self,
                self.tr("error"),
                f"Failed to change Windows InstallTime/SafeStore: {exc}",
            )

    def randomize_network_adapter_macs(self):
        """Confirm and randomize MAC addresses for eligible physical adapters."""
        reply = QMessageBox.warning(
            self,
            self.tr("adapter_macs_title"),
            self.tr("confirm_adapter_macs"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            report = randomize_windows_physical_adapter_macs()
            self.log(f"Windows network adapter MAC operation completed:\n{report}")
            message = f"Network adapter MAC operation completed:\n{report}"
            if report.startswith("Partial success:"):
                QMessageBox.warning(self, self.tr("warning"), message)
            else:
                QMessageBox.information(self, self.tr("success"), message)
        except Exception as exc:
            self.log(f"Error changing network adapter MAC addresses: {exc}")
            QMessageBox.critical(
                self,
                self.tr("error"),
                f"Failed to change network adapter MAC addresses: {exc}",
            )

    def randomize_c_volume_serial(self):
        """Confirm and change the Windows C: volume serial using Sysinternals."""
        reply = QMessageBox.warning(
            self,
            self.tr("volume_serial_title"),
            self.tr("confirm_volume_serial"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            report = randomize_windows_c_volume_serial()
            self.log(f"C: volume serial change completed:\n{report}")
            QMessageBox.information(
                self,
                self.tr("success"),
                report,
            )
        except Exception as exc:
            self.log(f"Error changing C: volume serial: {exc}")
            QMessageBox.critical(
                self,
                self.tr("error"),
                f"Failed to change C: volume serial: {exc}",
            )

    def get_qoder_data_dir(self):
        """Get Qoder data directory path (cross-platform support)"""
        return resolve_qoder_data_dir()

    def is_qoder_running(self):
        """Check if Qoder is currently running"""
        return check_is_qoder_running()

    def backup_identity(self):
        """Backup current Qoder identity files."""
        try:
            qoder_dir = self.get_qoder_data_dir()
            if not qoder_dir.exists():
                QMessageBox.warning(
                    self, self.tr("warning"), f"Qoder directory not found: {qoder_dir}"
                )
                return

            reply = QMessageBox.question(
                self,
                self.tr("backup_identity"),
                self.tr("confirm_backup"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

            backup_path = backup_qoder_identity(qoder_dir)
            self.log(f"Identity data successfully backed up to: {backup_path.name}")
            QMessageBox.information(
                self,
                self.tr("success"),
                f"{self.tr('backup_success')}\n{backup_path}",
            )
        except Exception as e:
            self.log(f"❌ Backup failed: {e}")
            QMessageBox.critical(self, self.tr("error"), f"Backup failed: {e}")

    def restore_identity(self):
        """Restore Qoder identity from backup."""
        try:
            qoder_dir = self.get_qoder_data_dir()
            backups = list_qoder_backups(qoder_dir)
            if not backups:
                QMessageBox.warning(
                    self, self.tr("warning"), self.tr("no_backups_found")
                )
                return

            latest_backup = backups[0]
            reply = QMessageBox.question(
                self,
                self.tr("restore_identity"),
                f"{self.tr('confirm_restore')}\n({latest_backup.name})",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

            success, message = restore_qoder_identity(latest_backup, qoder_dir)
            if success:
                self.log(f"✅ {message}")
                QMessageBox.information(
                    self, self.tr("success"), f"{self.tr('restore_success')}\n{message}"
                )
            else:
                self.log(f"❌ Restore failed: {message}")
                QMessageBox.warning(self, self.tr("error"), message)
        except Exception as e:
            self.log(f"❌ Restore failed: {e}")
            QMessageBox.critical(self, self.tr("error"), f"Restore failed: {e}")

    def check_update_action(self):
        """Check for updates on GitHub."""
        try:
            self.log("🔍 Checking for updates...")
            info = check_for_updates()
            if not info.get("success"):
                self.log(f"⚠️ Could not check updates: {info.get('error')}")
                QMessageBox.information(
                    self,
                    self.tr("check_update"),
                    f"Unable to check updates: {info.get('error')}\n\nYou can check manually at:\n{info.get('url')}",
                )
                return

            if info.get("has_update"):
                self.log(f"🎉 New version available: v{info['latest_version']}")
                reply = QMessageBox.question(
                    self,
                    self.tr("update_available"),
                    f"New version v{info['latest_version']} is available! (Current: v{info['current_version']})\n\nOpen download page?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )
                if reply == QMessageBox.Yes:
                    webbrowser.open(str(info.get("url")))
            else:
                self.log(f"✅ Qoder-Free is up-to-date (v{__version__})")
                QMessageBox.information(
                    self,
                    self.tr("check_update"),
                    f"{self.tr('latest_version_installed')} (v{__version__})",
                )
        except Exception as e:
            self.log(f"❌ Update check failed: {e}")
            QMessageBox.critical(self, self.tr("error"), f"Update check failed: {e}")

    def generate_system_version(self, system_type):
        """根据系统类型生成合适的系统版本号"""
        if system_type == "Darwin":  # macOS
            # macOS 版本号格式: 14.x.x (Sonoma), 13.x.x (Ventura), 12.x.x (Monterey)
            major_versions = [12, 13, 14, 15]  # 支持新版本
            major = random.choice(major_versions)
            minor = random.randint(0, 6)
            patch = random.randint(0, 9)
            return f"{major}.{minor}.{patch}"
        elif system_type == "Windows":
            # Windows 10/11 版本号
            versions = [
                "10.0.19045",  # Windows 10 22H2
                "10.0.22621",  # Windows 11 22H2
                "10.0.22631",  # Windows 11 23H2
                "10.0.26100",  # Windows 11 24H2
            ]
            base_version = random.choice(versions)
            # 添加随机的小版本号
            build_suffix = random.randint(1, 999)
            return f"{base_version}.{build_suffix}"
        else:  # Linux 或其他系统
            # Linux 内核版本号格式: 5.x.x, 6.x.x
            major_versions = [5, 6]
            major = random.choice(major_versions)
            if major == 5:
                minor = random.randint(10, 19)  # 5.10-5.19
            else:  # major == 6
                minor = random.randint(0, 8)  # 6.0-6.8
            patch = random.randint(0, 50)
            return f"{major}.{minor}.{patch}"

    def close_qoder(self):
        """Close Qoder application"""
        try:
            # Check if Qoder is running
            if not self.is_qoder_running():
                self.log("Qoder is not running.")
                return

            # Confirm closing
            reply = QMessageBox.question(
                self,
                self.tr("confirm_close_qoder"),
                "Are you sure you want to close Qoder?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Execute Qoder closing operation
                self.log("Closing Qoder...")
                ok, details = kill_qoder_process()
                if ok:
                    self.log("✅ Qoder process terminated.")
                else:
                    self.log("⚠️  Failed to terminate Qoder process.")
                if details:
                    self.log(details)

                QMessageBox.information(
                    self,
                    self.tr("success") if ok else self.tr("warning"),
                    (
                        "Qoder has been closed successfully."
                        if ok
                        else "Failed to close Qoder."
                    ),
                )
        except Exception as e:
            # Log error
            self.log(f"Error closing Qoder: {str(e)}")
            QMessageBox.critical(
                self, self.tr("error"), f"Failed to close Qoder: {str(e)}"
            )

    def login_identity_cleanup(self):
        """Clean login-related identity information"""
        try:
            qoder_support_dir = self.get_qoder_data_dir()
            self.perform_login_identity_cleanup(qoder_support_dir)

            # Prompt successful cleanup
            QMessageBox.information(
                self, self.tr("success"), "Login identity cleaned successfully."
            )
        except Exception as e:
            # Log error
            self.log(f"Error during login identity cleanup: {e}")
            QMessageBox.critical(
                self, self.tr("error"), f"Failed to clean login identity: {e}"
            )

    def perform_login_identity_cleanup(self, qoder_support_dir):
        """Clean login/session identity files inside the Qoder data directory."""
        cleaned_count = 0

        login_files = [
            "Network Persistent State",
            "Cookies",
            "Cookies-journal",
            "Login Data",
            "Login Data-journal",
            "Web Data",
            "Web Data-journal",
            "Trust Tokens",
            "Trust Tokens-journal",
            "TransportSecurity",
        ]

        for login_file in login_files:
            file_path = qoder_support_dir / login_file
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.log(f"   Removed login file: {login_file}")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"   Failed to remove login file {login_file}: {e}")

        login_dirs = [
            "Session Storage",
            "blob_storage",
        ]

        for login_dir in login_dirs:
            dir_path = qoder_support_dir / login_dir
            if dir_path.exists():
                try:
                    shutil.rmtree(dir_path)
                    self.log(f"   Removed login directory: {login_dir}")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"   Failed to remove login directory {login_dir}: {e}")

        storage_json_file = (
            qoder_support_dir / "User" / "globalStorage" / "storage.json"
        )
        if storage_json_file.exists():
            try:
                data = json.loads(storage_json_file.read_text(encoding="utf-8"))
                login_keywords = (
                    "accessToken",
                    "refreshToken",
                    "auth",
                    "credential",
                    "login",
                    "oauth",
                    "session",
                    "token",
                    "user.account",
                )
                removed_keys = [
                    key
                    for key in list(data.keys())
                    if any(
                        keyword.lower() in str(key).lower()
                        for keyword in login_keywords
                    )
                ]
                for key in removed_keys:
                    data.pop(key, None)
                    self.log(f"   Removed login setting: {key}")

                if removed_keys:
                    storage_json_file.write_text(
                        json.dumps(data, indent=4, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    cleaned_count += len(removed_keys)
            except Exception as e:
                self.log(f"   Failed to clean login settings: {e}")

        self.log(f"   Login identity cleanup finished; processed {cleaned_count} item(s)")

    def reset_telemetry(self):
        """Reset telemetry data"""
        try:
            # Check if Qoder is running
            if self.is_qoder_running():
                QMessageBox.warning(
                    self,
                    self.tr("warning"),
                    self.tr("qoder_detected_running")
                    + "\n"
                    + self.tr("please_close_qoder"),
                )
                return

            # Confirm reset
            reply = QMessageBox.question(
                self,
                self.tr("confirm_reset_telemetry"),
                "Are you sure you want to reset Telemetry data?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Execute telemetry reset operation
                self.log("Resetting Telemetry data...")
                qoder_support_dir = self.get_qoder_data_dir()
                updated = reset_qoder_telemetry(qoder_support_dir)
                self.log(
                    f"   New Telemetry Machine ID: {updated['telemetry.machineId'][:16]}..."
                )
                self.log(f"   New Device ID: {updated['telemetry.devDeviceId']}")
                self.log(f"   New SQM ID: {updated['telemetry.sqmId']}")

                QMessageBox.information(
                    self,
                    self.tr("success"),
                    "Telemetry data has been reset successfully.",
                )
        except Exception as e:
            # Log error
            self.log(f"Error resetting Telemetry data: {str(e)}")
            QMessageBox.critical(
                self, self.tr("error"), f"Failed to reset Telemetry data: {str(e)}"
            )

    def reset_machine_id(self):
        """Reset machine ID"""
        try:
            # Check if Qoder is running
            if self.is_qoder_running():
                QMessageBox.warning(
                    self,
                    self.tr("warning"),
                    self.tr("qoder_detected_running")
                    + "\n"
                    + self.tr("please_close_qoder"),
                )
                return

            # Confirm reset
            reply = QMessageBox.question(
                self,
                self.tr("confirm_reset_machine_id"),
                "Are you sure you want to reset the Machine ID?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Execute machine ID reset operation
                self.log("Resetting Machine ID...")
                qoder_support_dir = self.get_qoder_data_dir()
                new_machine_id = reset_qoder_machine_id(qoder_support_dir)
                self.log(f"   New Machine ID: {new_machine_id}")

                QMessageBox.information(
                    self, self.tr("success"), "Machine ID has been reset successfully."
                )
        except Exception as e:
            # Log error
            self.log(f"Error resetting Machine ID: {str(e)}")
            QMessageBox.critical(
                self, self.tr("error"), f"Failed to reset Machine ID: {str(e)}"
            )

    def deep_identity_cleanup(self):
        """Perform deep identity cleanup"""
        try:
            # Check if Qoder is running
            if self.is_qoder_running():
                QMessageBox.warning(
                    self,
                    self.tr("warning"),
                    self.tr("qoder_detected_running")
                    + "\n"
                    + self.tr("please_close_qoder"),
                )
                return

            # Confirm cleanup
            reply = QMessageBox.question(
                self,
                self.tr("confirm_deep_clean"),
                "This will perform a deep identity cleanup. Are you sure?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Execute deep identity cleanup
                self.log("Performing deep identity cleanup...")
                qoder_support_dir = self.get_qoder_data_dir()
                if not qoder_support_dir.exists():
                    raise FileNotFoundError(
                        f"Qoder data directory not found: {qoder_support_dir}"
                    )

                preserve_chat = self.preserve_chat_checkbox.isChecked()
                self.perform_advanced_identity_cleanup(qoder_support_dir, preserve_chat)
                self.perform_login_identity_cleanup(qoder_support_dir)
                self.perform_super_deep_cleanup(qoder_support_dir)

                # Prompt cleanup success
                QMessageBox.information(
                    self,
                    self.tr("success"),
                    "Deep identity cleanup completed successfully.",
                )
        except Exception as e:
            # Log error
            self.log(f"Error during deep identity cleanup: {str(e)}")
            QMessageBox.critical(
                self,
                self.tr("error"),
                f"Failed to perform deep identity cleanup: {str(e)}",
            )

    def hardware_fingerprint_reset(self):
        """Reset hardware fingerprint"""
        try:
            # Check if Qoder is running
            if self.is_qoder_running():
                QMessageBox.warning(
                    self,
                    self.tr("warning"),
                    self.tr("qoder_detected_running")
                    + "\n"
                    + self.tr("please_close_qoder"),
                )
                return

            # Confirm reset
            reply = QMessageBox.question(
                self,
                self.tr("confirm_hardware_fingerprint_reset"),
                "This will reset all hardware-related identifiers. Are you sure?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Execute hardware fingerprint reset
                self.log("Resetting hardware fingerprint...")
                qoder_support_dir = self.get_qoder_data_dir()
                self.perform_hardware_fingerprint_reset(qoder_support_dir)

                # Prompt reset success
                QMessageBox.information(
                    self,
                    self.tr("success"),
                    "Hardware fingerprint reset completed successfully.",
                )
        except Exception as e:
            # Log error
            self.log(f"Error resetting hardware fingerprint: {str(e)}")
            QMessageBox.critical(
                self,
                self.tr("error"),
                f"Failed to reset hardware fingerprint: {str(e)}",
            )

    def one_click_reset(self):
        """Run the one-click reset."""
        try:
            # If Qoder is running, offer to close it automatically so we can patch its data.
            if self.is_qoder_running():
                reply = QMessageBox.question(
                    self,
                    self.tr("confirm_close_qoder"),
                    self.tr("qoder_detected_running")
                    + "\n"
                    + self.tr("please_close_qoder")
                    + "\n\nClose Qoder now and continue?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply != QMessageBox.Yes:
                    return

                ok, details = kill_qoder_process()
                if details:
                    self.log(details)
                if not wait_for_qoder_exit():
                    self.log("Qoder is still running; retrying process termination...")
                    ok, details = kill_qoder_process()
                    if details:
                        self.log(details)
                if not wait_for_qoder_exit():
                    QMessageBox.warning(
                        self,
                        self.tr("warning"),
                        "Qoder is still running and may be holding files open. Close all Qoder windows and helper processes, then retry.",
                    )
                    return
                if not ok:
                    self.log("Qoder process was not detected after the termination attempt.")

            # 确认操作
            reply = QMessageBox.question(
                self,
                self.tr("confirm_one_click"),
                "Are you sure you want to perform a one-click reset?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                preserve_chat = self.preserve_chat_checkbox.isChecked()

                # 执行重置操作
                self.log("Performing one-click reset...")
                self.perform_full_reset(preserve_chat=preserve_chat)

                # 提示操作完成
                QMessageBox.information(
                    self, self.tr("success"), "One-click reset completed successfully."
                )

                self.log("One-click reset completed.")
        except Exception as e:
            # 记录错误
            self.log(f"Error during one-click reset: {str(e)}")
            QMessageBox.critical(self, self.tr("error"), f"An error occurred: {str(e)}")

    def perform_full_reset(self, preserve_chat=True):
        """执行完整重置"""
        qoder_support_dir = self.get_qoder_data_dir()

        if not qoder_support_dir.exists():
            raise FileNotFoundError("Qoder application data directory was not found")

        self._reset_cleanup_failures = []

        # 1. Reset machine identifiers.
        self.log("1. Resetting machine ID...")
        reset_qoder_machine_id(qoder_support_dir)
        self.log("   Primary machine ID reset")

        # 增强：创建多个可能的机器ID文件
        additional_id_files = [
            "deviceid",
            "hardware_uuid",
            "system_uuid",
            "platform_id",
            "installation_id",
        ]
        for id_file in additional_id_files:
            file_path = qoder_support_dir / id_file
            new_id = str(uuid.uuid4())
            with open(file_path, "w") as f:
                f.write(new_id)
            self.log(f"   Created identifier file: {id_file}")

        # 2. Reset telemetry data.
        self.log("2. Resetting telemetry data...")
        updated = reset_qoder_telemetry(qoder_support_dir)
        storage_json_file = qoder_support_dir / "User/globalStorage/storage.json"
        with open(storage_json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Ensure system fingerprint fields are consistent with the current platform.
        data["system.platform"] = _qoder_platform_value()
        data["system.arch"] = platform.machine()
        data["system.version"] = self.generate_system_version(platform.system())

        # Optional identity cleanup: avoid deleting telemetry keys we just wrote.
        if not preserve_chat:
            identity_keywords = (
                "auth",
                "login",
                "token",
                "credential",
                "fingerprint",
                "tracking",
                "analytics",
            )
            protected_prefixes = ("telemetry.",)
            protected_keys = {
                "machineId",
                "deviceId",
                "installationId",
                "hardwareId",
                "platformId",
            }

            identity_keys_to_remove = []
            for key in list(data.keys()):
                key_lower = str(key).lower()
                if key in protected_keys or key_lower.startswith(protected_prefixes):
                    continue
                if any(keyword in key_lower for keyword in identity_keywords):
                    identity_keys_to_remove.append(key)

            for key in identity_keys_to_remove:
                data.pop(key, None)
                self.log(f"   Removed configuration key: {key}")
        else:
            self.log("   Preserve-chat mode: keeping non-identity settings")

        with open(storage_json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        self.log(f"   New telemetry machine ID: {updated['telemetry.machineId'][:16]}...")
        self.log(f"   New device ID: {updated['telemetry.devDeviceId']}")
        self.log(f"   New SQM ID: {updated['telemetry.sqmId']}")

        # 3. Clean cache data.
        self.log("3. Cleaning cache data...")
        cache_dirs = [
            "Cache",
            "blob_storage",
            "Code Cache",
            "SharedClientCache",
            "GPUCache",
            "DawnGraphiteCache",
            "DawnWebGPUCache",
            # 新增：更多可能包含指纹的缓存
            "ShaderCache",
            "DawnCache",
            "Dictionaries",
            "CachedData",
            "CachedProfilesData",
            "CachedExtensions",
            "IndexedDB",
            "CacheStorage",
            "WebSQL",
        ]

        cleaned = 0
        for cache_dir in cache_dirs:
            cache_path = qoder_support_dir / cache_dir
            if cache_path.exists():
                try:
                    shutil.rmtree(cache_path)
                    cleaned += 1
                except:
                    pass

        self.log(f"   Removed {cleaned} cache director(ies)")

        # 4. Clean identity-related files.
        self.log("4. Cleaning identity-related files...")
        identity_files = [
            "Network Persistent State",  # 网络服务器连接历史和指纹
            "TransportSecurity",  # HSTS等安全策略记录
            "Trust Tokens",
            "Trust Tokens-journal",  # 信任令牌数据库
            "SharedStorage",
            "SharedStorage-wal",  # 共享存储数据库
            "Preferences",  # 用户偏好设置（可能包含指纹）
            "Secure Preferences",  # 安全偏好设置
            "Login Credentials",  # 登录凭据（如果存在）
            "Web Data",
            "Web Data-journal",  # Web数据数据库（如果存在）
            "cert_transparency_reporter_state.json",  # 证书透明度状态
            "Local State",  # Chromium本地状态（包含加密密钥）
            "NetworkDataMigrated",  # 网络数据迁移标记
            # 新增：硬件指纹相关文件
            "DeviceMetadata",
            "HardwareInfo",
            "SystemInfo",
            "QuotaManager",
            "QuotaManager-journal",
            "origin_bound_certs",
            "Network Action Predictor",
            "AutofillStrikeDatabase",
            "AutofillStrikeDatabase-journal",
            "Feature Engagement Tracker",
            "PasswordStoreDefault",
            "PreferredApps",
            "UserPrefs",
            "UserPrefs.backup",
            "Platform Notifications",
            "VideoDecodeStats",
            "OriginTrials",
            "BrowserMetrics",
            "SafeBrowsing",
            "Visited Links",
            "History",
            "History-journal",
            "Favicons",
            "Favicons-journal",
            "Shortcuts",
            "Shortcuts-journal",
            "Top Sites",
            "Top Sites-journal",
        ]

        identity_cleaned = 0
        for identity_file in identity_files:
            file_path = qoder_support_dir / identity_file
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.log(f"   Removed: {identity_file}")
                    identity_cleaned += 1
                except Exception as e:
                    self.log(f"   Failed to remove {identity_file}: {e}")

        # 5. 清理存储目录
        storage_dirs = [
            "Service Worker",  # 服务工作者缓存
            "Certificate Revocation Lists",  # 证书撤销列表
            "SSLCertificates",  # SSL证书缓存
            "databases",  # 数据库目录
            "clp",  # 剪贴板数据，可能包含敏感信息
            "logs",  # 日志文件，可能记录用户活动
            "Backups",  # 备份文件，可能包含历史身份信息
            "CachedExtensionVSIXs",  # 扩展缓存，显示用户安装的扩展
        ]

        # 根据是否保留对话记录来决定清理哪些存储目录
        if not preserve_chat:
            # 如果不保留对话记录，清理所有存储目录
            storage_dirs.extend(
                [
                    "Local Storage",  # 本地存储数据库（可能包含对话索引）
                    "Session Storage",  # 会话存储
                    "WebStorage",  # Web存储
                    "Shared Dictionary",  # 共享字典
                ]
            )
            self.log("   Chat history is not being preserved; cleaning all storage directories")
        else:
            # 如果保留对话记录，保留可能包含对话索引的存储
            # 但仍需清理可能包含身份信息的存储
            storage_dirs.extend(
                [
                    "Session Storage",  # 会话存储（可能包含身份信息）
                    "WebStorage",  # Web存储（可能包含身份信息）
                    "Shared Dictionary",  # 共享字典
                ]
            )
            self.log("   Preserve-chat mode: keeping Local Storage, which may contain chat indexes")

        for storage_dir in storage_dirs:
            storage_path = qoder_support_dir / storage_dir
            if storage_path.exists():
                try:
                    shutil.rmtree(storage_path)
                    self.log(f"   Removed: {storage_dir}")
                    identity_cleaned += 1
                except Exception as e:
                    self.log(f"   Failed to remove {storage_dir}: {e}")

        self.log(f"   Removed {identity_cleaned} identity-related file(s)/directory(ies)")

        # 5. Run advanced identity cleanup.
        self.log("5. Running advanced identity cleanup...")
        self.perform_advanced_identity_cleanup(qoder_support_dir, preserve_chat)

        # 6. Clean login state.
        self.log("6. Cleaning login state...")
        self.perform_login_identity_cleanup(qoder_support_dir)

        # 7. Reset hardware fingerprint data.
        self.log("7. Resetting hardware fingerprint data...")
        self.perform_hardware_fingerprint_reset(qoder_support_dir)

        # 8. Run deep cleanup.
        self.log("8. Running deep cleanup...")
        self.perform_super_deep_cleanup(qoder_support_dir)

        # 9. Handle chat history.
        if preserve_chat:
            self.log("9. Preserving chat history...")
            self.log("   Chat history preserved")
        else:
            self.log("9. Clearing chat history...")
            self.clear_chat_history(qoder_support_dir)

        cleanup_failures = self._reset_cleanup_failures
        self._reset_cleanup_failures = None
        if cleanup_failures:
            preview = "; ".join(cleanup_failures[:3])
            remaining = len(cleanup_failures) - 3
            if remaining > 0:
                preview += f"; and {remaining} more cleanup failure(s)"
            raise RuntimeError(
                f"Reset is incomplete: {len(cleanup_failures)} cleanup operation(s) failed. {preview}"
            )

    def perform_advanced_identity_cleanup(self, qoder_support_dir, preserve_chat=False):
        """执行高级身份清理，清除所有可能的身份识别信息"""
        try:
            self.log("Starting advanced identity cleanup...")
            cleaned_count = 0

            # 1. 清理 SharedClientCache 内部文件
            shared_cache = qoder_support_dir / "SharedClientCache"
            if shared_cache.exists():
                # 总是清理这些关键的身份文件（会重新生成）
                critical_files = [".info", ".lock", "mcp.json"]
                for file_name in critical_files:
                    file_path = shared_cache / file_name
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            self.log(f"   Removed: SharedClientCache/{file_name}")
                            cleaned_count += 1
                        except Exception as e:
                            self.log(f"   Failed to remove {file_name}: {e}")

                # 总是清理 cache 目录（缓存数据）
                cache_dir = shared_cache / "cache"
                if cache_dir.exists():
                    try:
                        shutil.rmtree(cache_dir)
                        self.log("   Removed: SharedClientCache/cache")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   Failed to remove SharedClientCache/cache: {e}")

                # 根据保留对话设置决定是否清理 index 目录
                index_dir = shared_cache / "index"
                if index_dir.exists():
                    if not preserve_chat:
                        # 不保留对话：清理所有索引
                        try:
                            shutil.rmtree(index_dir)
                            self.log("   Removed: SharedClientCache/index")
                            cleaned_count += 1
                        except Exception as e:
                            self.log(f"   Failed to remove SharedClientCache/index: {e}")
                    else:
                        # 保留对话：只清理非对话相关的索引
                        # 保留可能包含对话搜索索引的文件
                        for index_item in index_dir.iterdir():
                            if (
                                index_item.is_dir()
                                and "chat" not in index_item.name.lower()
                            ):
                                try:
                                    shutil.rmtree(index_item)
                                    self.log(
                                        f"   Removed: SharedClientCache/index/{index_item.name}"
                                    )
                                    cleaned_count += 1
                                except Exception as e:
                                    self.log(
                                        f"   Failed to remove SharedClientCache/index/{index_item.name}: {e}"
                                    )
                        self.log("   Preserve-chat mode: retaining possible chat indexes")

            # 2. 清理系统级别的身份文件
            system_files = ["code.lock", "languagepacks.json"]

            for sys_file in system_files:
                file_path = qoder_support_dir / sys_file
                if file_path.exists():
                    try:
                        file_path.unlink()
                        self.log(f"   Removed: {sys_file}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   Failed to remove {sys_file}: {e}")

            # 3. 清理崩溃报告目录（可能包含设备信息）
            crashpad_dir = qoder_support_dir / "Crashpad"
            if crashpad_dir.exists():
                try:
                    shutil.rmtree(crashpad_dir)
                    self.log("   Removed: Crashpad")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"   Failed to remove Crashpad: {e}")

            # 4. 清理缓存目录（CachedData和 CachedProfilesData）
            cached_dirs = ["CachedData", "CachedProfilesData"]
            for cached_dir in cached_dirs:
                dir_path = qoder_support_dir / cached_dir
                if dir_path.exists():
                    try:
                        shutil.rmtree(dir_path)
                        self.log(f"   Removed: {cached_dir}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   Failed to remove {cached_dir}: {e}")

            # 5. 清理 socket 文件
            import glob

            socket_pattern = str(qoder_support_dir / "*.sock")
            socket_files = glob.glob(socket_pattern)
            for socket_file in socket_files:
                try:
                    Path(socket_file).unlink()
                    self.log(f"   Removed: {Path(socket_file).name}")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"   Failed to remove {Path(socket_file).name}: {e}")

            # 6. 清理设备指纹和活动记录文件（新增）
            fingerprint_and_activity_files = [
                "DeviceMetadata",
                "HardwareInfo",
                "SystemInfo",
                "QuotaManager",
                "QuotaManager-journal",
                "ActivityLog",
                "EventLog",
                "UserActivityLog",
                "origin_bound_certs",
                "Network Action Predictor",
                "AutofillStrikeDatabase",
                "AutofillStrikeDatabase-journal",
                "Feature Engagement Tracker",
                "PasswordStoreDefault",
                "PreferredApps",
                "UserPrefs",
                "UserPrefs.backup",
            ]

            for file_name in fingerprint_and_activity_files:
                file_path = qoder_support_dir / file_name
                if file_path.exists():
                    try:
                        if file_path.is_dir():
                            shutil.rmtree(file_path)
                        else:
                            file_path.unlink()
                        self.log(f"   Removed: {file_name}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   Failed to remove {file_name}: {e}")

            # 7. 清理数据库目录内的所有文件（新增）
            databases_dir = qoder_support_dir / "databases"
            if databases_dir.exists():
                try:
                    shutil.rmtree(databases_dir)
                    self.log("   Removed: databases directory and all contents")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"   Failed to remove databases: {e}")

            # 8. 清理 Electron 相关的持久化数据（新增）
            electron_files = [
                "Dictionaries",
                "Platform Notifications",
                "ShaderCache",
                "VideoDecodeStats",
                "OriginTrials",
                "BrowserMetrics",
                "AutofillRegexes",
                "SafeBrowsing",
            ]

            for electron_file in electron_files:
                file_path = qoder_support_dir / electron_file
                if file_path.exists():
                    try:
                        if file_path.is_dir():
                            shutil.rmtree(file_path)
                        else:
                            file_path.unlink()
                        self.log(f"   Removed: {electron_file}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   Failed to remove {electron_file}: {e}")

            self.log(f"   Advanced identity cleanup finished; processed {cleaned_count} item(s)")

        except Exception as e:
            self.log(f"   Advanced identity cleanup failed: {e}")

    def clear_chat_history(self, qoder_support_dir):
        """清除对话记录"""
        try:
            cleared = 0

            # 1. Remove workspace chat sessions.
            workspace_storage = qoder_support_dir / "User/workspaceStorage"
            if workspace_storage.exists():
                for workspace_dir in workspace_storage.iterdir():
                    if workspace_dir.is_dir():
                        # 清除chatSessions目录
                        chat_sessions = workspace_dir / "chatSessions"
                        if chat_sessions.exists():
                            try:
                                shutil.rmtree(chat_sessions)
                                self.log(
                                    f"   Removed: {chat_sessions.relative_to(qoder_support_dir)}"
                                )
                                cleared += 1
                            except Exception as e:
                                self.log(
                                    f"   Failed to remove {chat_sessions.relative_to(qoder_support_dir)}: {e}"
                                )

                        # 清除chatEditingSessions目录
                        chat_editing = workspace_dir / "chatEditingSessions"
                        if chat_editing.exists():
                            try:
                                shutil.rmtree(chat_editing)
                                self.log(
                                    f"   Removed: {chat_editing.relative_to(qoder_support_dir)}"
                                )
                                cleared += 1
                            except Exception as e:
                                self.log(
                                    f"   Failed to remove {chat_editing.relative_to(qoder_support_dir)}: {e}"
                                )

            # 2. Remove history.
            history_dir = qoder_support_dir / "User/History"
            if history_dir.exists():
                try:
                    shutil.rmtree(history_dir)
                    self.log("   Removed: User/History")
                    cleared += 1
                except Exception as e:
                    self.log(f"   Failed to remove User/History: {e}")

            # 3. Remove chat-related session storage.
            session_storage = qoder_support_dir / "Session Storage"
            if session_storage.exists():
                try:
                    shutil.rmtree(session_storage)
                    self.log("   Removed: Session Storage")
                    cleared += 1
                except Exception as e:
                    self.log(f"   Failed to remove Session Storage: {e}")

            # 4. Remove chat-related user settings.
            user_data_file = qoder_support_dir / "User/globalStorage/storage.json"
            if user_data_file.exists():
                try:
                    with open(user_data_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # 清除对话相关的键
                    chat_keys = [
                        key
                        for key in data.keys()
                        if "chat" in key.lower()
                        or "conversation" in key.lower()
                        or "history" in key.lower()
                        or "session" in key.lower()
                    ]

                    if chat_keys:
                        for key in chat_keys:
                            del data[key]
                            self.log(f"   Removed setting: {key}")

                        with open(user_data_file, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)

                        cleared += 1

                except Exception as e:
                    self.log(f"   Failed to clean user settings: {e}")

            self.log(f"   Chat history cleanup finished; processed {cleared} item(s)")

        except Exception as e:
            self.log(f"   Chat history cleanup failed: {e}")

    def open_github(self):
        """打开GitHub链接"""
        self.log("Opening GitHub issues page...")
        webbrowser.open("https://github.com/VoDaiLocz/Qoder-Free/issues")

    def _write_fake_hardware_info(self, qoder_support_dir):
        """Create fake hardware information used by hardware fingerprint reset."""
        try:
            # 5. Create fake hardware information (interference detection)
            self.log("5. Creating fake hardware information...")
            try:
                # Generate appropriate fake hardware information based on system type
                system_type = platform.system()
                self.log(f"   Detected system type: {system_type}")

                if system_type == "Darwin":  # macOS
                    fake_hardware_info = {
                        "cpu": {
                            "name": f"Apple M{random.randint(2, 5)} Pro",
                            "cores": random.choice([8, 10, 12, 16]),
                            "threads": random.choice([8, 10, 12, 16]),
                            "frequency": f"{random.uniform(2.0, 4.0):.1f}GHz",
                        },
                        "gpu": {
                            "name": f"Apple M{random.randint(2, 5)} Pro GPU",
                            "memory": f"{random.choice([16, 24, 32])}GB",
                            "cores": random.choice([16, 19, 24, 32]),
                        },
                        "memory": {
                            "total": f"{random.choice([16, 24, 32, 64])}GB",
                            "type": "LPDDR5",
                            "speed": f"{random.choice([6400, 7467])}MT/s",
                        },
                    }
                elif system_type == "Windows":  # Windows
                    cpu_brands = ["Intel", "AMD"]
                    cpu_brand = random.choice(cpu_brands)

                    if cpu_brand == "Intel":
                        cpu_series = random.choice(["Core i5", "Core i7", "Core i9"])
                        cpu_gen = random.randint(12, 14)
                        cpu_model = f"{random.randint(600, 900)}{'K' if random.choice([True, False]) else ''}"
                        cpu_name = f"Intel {cpu_series}-{cpu_gen}{cpu_model}"
                    else:  # AMD
                        cpu_series = random.choice(["Ryzen 5", "Ryzen 7", "Ryzen 9"])
                        cpu_gen = random.randint(5000, 7000)
                        cpu_name = f"AMD {cpu_series} {cpu_gen}X"

                    gpu_brands = ["NVIDIA", "AMD", "Intel"]
                    gpu_brand = random.choice(gpu_brands)

                    if gpu_brand == "NVIDIA":
                        gpu_series = random.choice(
                            ["RTX 4060", "RTX 4070", "RTX 4080", "RTX 4090"]
                        )
                        gpu_name = f"NVIDIA GeForce {gpu_series}"
                        gpu_memory = f"{random.choice([8, 12, 16, 24])}GB"
                    elif gpu_brand == "AMD":
                        gpu_series = random.choice(
                            ["RX 7600", "RX 7700 XT", "RX 7800 XT", "RX 7900 XTX"]
                        )
                        gpu_name = f"AMD Radeon {gpu_series}"
                        gpu_memory = f"{random.choice([8, 12, 16, 20])}GB"
                    else:  # Intel
                        gpu_series = random.choice(["Arc A750", "Arc A770", "Iris Xe"])
                        gpu_name = f"Intel {gpu_series}"
                        gpu_memory = f"{random.choice([8, 12, 16])}GB"

                    fake_hardware_info = {
                        "cpu": {
                            "name": cpu_name,
                            "cores": random.choice([6, 8, 12, 16, 24]),
                            "threads": random.choice([12, 16, 20, 24, 32]),
                            "frequency": f"{random.uniform(3.0, 5.0):.1f}GHz",
                        },
                        "gpu": {
                            "name": gpu_name,
                            "memory": gpu_memory,
                            "cores": random.choice([1024, 1536, 2048, 2560]),
                        },
                        "memory": {
                            "total": f"{random.choice([16, 24, 32])}GB",
                            "type": "LPDDR5",
                            "speed": f"{random.choice([4266, 5500, 6400])}MHz",
                        },
                    }
                else:
                    # Default case for other systems
                    fake_hardware_info = {
                        "cpu": {
                            "name": "Generic CPU",
                            "cores": random.choice([4, 6, 8]),
                            "threads": random.choice([8, 12, 16]),
                            "frequency": f"{random.uniform(2.0, 4.0):.1f}GHz",
                        },
                        "gpu": {
                            "name": "Generic GPU",
                            "memory": f"{random.choice([4, 8, 12])}GB",
                            "cores": random.choice([512, 1024, 1536]),
                        },
                        "memory": {
                            "total": f"{random.choice([8, 16, 24])}GB",
                            "type": "DDR4",
                            "speed": f"{random.choice([2400, 3200, 4000])}MHz",
                        },
                    }

                # Write fake hardware information to a file
                hardware_file = qoder_support_dir / "hardware_info.json"
                with open(hardware_file, "w", encoding="utf-8") as f:
                    json.dump(fake_hardware_info, f, indent=4, ensure_ascii=False)

                self.log("   Successfully created fake hardware information")

            except Exception as e:
                self.log(f"   Failed to create fake hardware information: {e}")

        except Exception as e:
            self.log(f"Error during hardware fingerprint reset: {e}")
            raise

    def perform_super_deep_cleanup(self, qoder_support_dir):
        """🛡️ 执行超级深度清理（安全增强版，只清理与Qoder相关的文件）"""
        try:
            self.log("Starting deep cleanup...")
            cleaned_count = 0

            # 1. 清理系统级别的身份文件
            self.log("1. Cleaning system-level identity files...")
            system_identity_files = [
                # 日志和临时文件
                "logs",
                "tmp",
                "temp",
                "crash_dumps",
                # 更多可能的身份识别文件
                "identity.json",
                "machine.json",
                "device.json",
                "fingerprint.json",
                "tracking.json",
                "analytics.json",
                # 浏览器相关文件
                "BrowserUserAgent",
                "ClientHints",
                "NavigatorInfo",
                "ScreenInfo",
                "TimezoneInfo",
                "LanguageInfo",
                # 网络相关文件
                "DNSCache",
                "HTTPCache",
                "ProxySettings",
                "NetworkConfiguration",
                "ConnectionHistory",
                # 系统信息文件
                "OSInfo",
                "HardwareProfile",
                "SystemMetrics",
                "PerformanceInfo",
                "MemoryInfo",
                "DiskInfo",
                # 用户活动相关
                "UserActivity",
                "AppUsage",
                "FeatureUsage",
                "InteractionHistory",
                "AccessLog",
                "AuditLog",
                # 安全相关文件
                "SecuritySettings",
                "CertificateStore",
                "TrustStore",
                "EncryptionKeys",
                "AuthTokens",
                "SessionKeys",
                # 缓存相关文件
                "MetadataCache",
                "ThumbnailCache",
                "IndexCache",
                "SearchCache",
                "QueryCache",
                "ResultsCache",
                # 扩展和插件相关
                "ExtensionData",
                "PluginData",
                "AddonData",
                "ExtensionPrefs",
                "PluginPrefs",
                "AddonPrefs",
                # 更多 WebKit 相关文件
                "WebKitCache",
                "WebProcessCache",
                "PluginProcessCache",
                "RenderProcessCache",
                "GPUProcessCache",
                # 更多 Chromium 相关文件
                "ChromiumState",
                "ChromiumPrefs",
                "ChromiumHistory",
                "ChromiumCookies",
                "ChromiumSessions",
            ]

            for file_name in system_identity_files:
                file_path = qoder_support_dir / file_name
                if file_path.exists():
                    try:
                        if file_path.is_dir():
                            shutil.rmtree(file_path)
                        else:
                            file_path.unlink()
                        self.log(f"   Removed: {file_name}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   Failed to remove {file_name}: {e}")

            # 2. 谨慎清理指定扩展名的可疑文件（增加安全检查）
            self.log("2. Cleaning selected file extensions...")
            suspicious_extensions = [
                ".tmp",
                ".temp",
                ".cache",
                ".lock",
                ".pid",
                ".sock",
                ".session",
                ".fingerprint",
                ".tracking",
                ".analytics",
            ]

            # 🚫 绝对安全白名单 - 永远不删除的重要文件
            safe_keywords = [
                "settings",
                "config",
                "workspace",
                "preference",
                "backup",
                "license",
                "certificate",
            ]
            protected_keywords = [
                "settings",
                "config",
                "workspace",
                "preference",
                "user",
                "important",
                "backup",
                "license",
                "key",
                "certificate",
                "password",
                "auth",
                "secret",
                "critical",
                "system",
                "apple",
                "microsoft",
                "windows",
                "macos",
                "safari",
                "chrome",
            ]

            # ✅ 只清理与这些应用相关的文件
            qoder_keywords = ["qoder", "vscode", "electron", "code-", "ms-vscode"]

            for root, dirs, files in os.walk(qoder_support_dir):
                for file in files:
                    file_path = Path(root) / file
                    file_ext = file_path.suffix.lower()

                    if file_ext in suspicious_extensions:
                        # 安全检查：跳过重要文件
                        is_safe_file = any(
                            safe_word in file.lower() for safe_word in safe_keywords
                        )

                        # 🛡️ 多重安全检查
                        is_protected = any(
                            keyword in file.lower() for keyword in protected_keywords
                        )
                        is_in_qoder_dir = str(qoder_support_dir) in str(file_path)
                        is_qoder_related = any(
                            keyword in file.lower() or keyword in root.lower()
                            for keyword in qoder_keywords
                        )

                        # ✅ 只有同时满足以下条件才删除：
                        # 1. 在Qoder目录内  2. 与Qoder相关  3. 不在保护列表
                        if is_in_qoder_dir and is_qoder_related and not is_protected:
                            try:
                                file_path.unlink()
                                self.log(f"   Removed selected file: {file}")
                                cleaned_count += 1
                            except Exception as e:
                                self.log(f"   Failed to remove {file}: {e}")
                        else:
                            if not is_qoder_related:
                                self.log(f"   Skipped unrelated file: {file}")
                            if is_safe_file:
                                self.log(f"   Protected file: {file}")

            # 3. 清理隐藏文件和目录
            self.log("3. Cleaning hidden files...")
            for root, dirs, files in os.walk(qoder_support_dir):
                # 清理隐藏文件（以点开头）
                for file in files:
                    if file.startswith(".") and file not in [".gitignore", ".gitkeep"]:
                        file_path = Path(root) / file
                        try:
                            file_path.unlink()
                            self.log(f"   Removed hidden file: {file}")
                            cleaned_count += 1
                        except Exception as e:
                            self.log(f"   Failed to remove hidden file {file}: {e}")

                # 清理隐藏目录（以点开头）
                for dir_name in dirs[:]:
                    if dir_name.startswith(".") and dir_name not in [".git"]:
                        dir_path = Path(root) / dir_name
                        try:
                            shutil.rmtree(dir_path)
                            self.log(f"   Removed hidden directory: {dir_name}")
                            dirs.remove(dir_name)  # 从遍历中移除
                            cleaned_count += 1
                        except Exception as e:
                            self.log(f"   Failed to remove hidden directory {dir_name}: {e}")

            # 4. 重置文件权限（防止文件时间戳检测）
            self.log("4. Resetting file permissions...")
            try:
                # 重置整个目录的权限
                if platform.system() != "Windows":
                    subprocess.run(
                        ["chmod", "-R", "755", str(qoder_support_dir)],
                        check=False,
                        timeout=30,
                    )
                    self.log("   File permissions reset")
            except Exception as e:
                self.log(f"   Failed to reset file permissions: {e}")

            # 5. Do not create decoy files. Keeping cleanup output minimal makes
            # diagnostics easier and avoids adding new state that users did not ask for.
            self.log("5. Skipping decoy-file creation")

            # 6. 安全清理系统级别的缓存（macOS）
            if platform.system() == "Darwin":
                self.log("6. Cleaning selected macOS user cache entries...")
                try:
                    # 只清理用户级别的系统缓存，不影响系统稳定性
                    user_system_cache_paths = [
                        Path.home() / "Library/Caches",
                        Path.home()
                        / "Library/Application Support/com.apple.sharedfilelist",
                    ]

                    for cache_path in user_system_cache_paths:
                        if cache_path.exists() and cache_path != qoder_support_dir:
                            # 只清理与 Qoder/VSCode 相关的文件，不影响其他应用
                            for item in cache_path.iterdir():
                                item_name_lower = item.name.lower()
                                if any(
                                    keyword in item_name_lower
                                    for keyword in [
                                        "qoder",
                                        "vscode",
                                        "com.microsoft.vscode",
                                        "electron",
                                    ]
                                ):
                                    try:
                                        if item.is_dir():
                                            shutil.rmtree(item)
                                        else:
                                            item.unlink()
                                        self.log(f"   Removed system cache entry: {item.name}")
                                        cleaned_count += 1
                                    except Exception as e:
                                        self.log(
                                            f"   Failed to clean system cache entry {item.name}: {e}"
                                        )

                    # 不清理 LaunchServices，避免影响系统功能
                    self.log("   Skipped LaunchServices cleanup to protect system stability")

                except Exception as e:
                    self.log(f"   macOS user cache cleanup failed: {e}")

            elif platform.system() == "Windows":
                self.log("6. Cleaning selected Windows user cache entries...")
                try:
                    # 只清理用户级别的缓存，不影响系统
                    user_cache_paths = [
                        Path(os.environ.get("LOCALAPPDATA", "")) / "Temp",
                        Path(os.environ.get("APPDATA", ""))
                        / "Microsoft"
                        / "Windows"
                        / "Recent",
                    ]

                    for cache_path in user_cache_paths:
                        if cache_path.exists():
                            for item in cache_path.iterdir():
                                if any(
                                    keyword in item.name.lower()
                                    for keyword in ["qoder", "vscode", "electron"]
                                ):
                                    try:
                                        if item.is_dir():
                                            shutil.rmtree(item)
                                        else:
                                            item.unlink()
                                        self.log(f"   Removed Windows cache entry: {item.name}")
                                        cleaned_count += 1
                                    except Exception as e:
                                        self.log(f"   Failed to remove cache entry: {e}")
                except Exception as e:
                    self.log(f"   Windows user cache cleanup failed: {e}")

            self.log(f"   Deep cleanup finished; processed {cleaned_count} item(s)")

        except Exception as e:
            self.log(f"   Deep cleanup failed: {e}")

    def perform_hardware_fingerprint_reset(self, qoder_support_dir):
        """Thực hiện reset dấu vân tay phần cứng"""
        try:
            # Kiểm tra thư mục tồn tại
            if not qoder_support_dir.exists():
                raise Exception("Không tìm thấy thư mục Qoder")

            # Sinh UUID mới
            import uuid
            import json
            import hashlib

            # Tạo các ID mới
            new_machine_id = str(uuid.uuid4())
            new_device_id = str(uuid.uuid4())
            machine_id_hash = hashlib.sha256(new_machine_id.encode()).hexdigest()

            # Đường dẫn file storage
            storage_json_file = qoder_support_dir / "User/globalStorage/storage.json"

            # Đọc và cập nhật file storage
            if storage_json_file.exists():
                with open(storage_json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Cập nhật các trường liên quan đến hardware
                data["telemetry.machineId"] = machine_id_hash
                data["telemetry.devDeviceId"] = new_device_id
                data["machineId"] = machine_id_hash

                with open(storage_json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

            # Ghi log
            self.log(
                f"Reset hardware fingerprint: New Machine ID {machine_id_hash[:16]}..."
            )
            self.log(f"New Device ID: {new_device_id}")
            self._write_fake_hardware_info(qoder_support_dir)

        except Exception as e:
            self.log(f"Error resetting hardware fingerprint: {e}")
            raise


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="Qoder-Free: Privacy & Machine ID Reset Tool for Qoder AI IDE"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in command-line interface mode without opening GUI",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Perform 1-Click full reset of Qoder machine ID & telemetry",
    )
    parser.add_argument(
        "--preserve-chat",
        action="store_true",
        default=True,
        help="Preserve chat history during reset (default: True)",
    )
    parser.add_argument(
        "--no-preserve-chat",
        action="store_false",
        dest="preserve_chat",
        help="Do not preserve chat history during reset",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a backup of current Qoder identity files",
    )
    parser.add_argument(
        "--restore",
        nargs="?",
        const="latest",
        default=None,
        help="Restore identity files from latest or specified backup path",
    )
    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="List available identity backups",
    )
    parser.add_argument(
        "--check-update",
        action="store_true",
        help="Check GitHub for newer versions of Qoder-Free",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Display current Qoder installation, running state, and IDs",
    )
    parser.add_argument(
        "--close-qoder",
        action="store_true",
        help="Terminate running Qoder processes",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"Qoder-Free v{__version__}",
    )
    return parser.parse_args()


def run_cli(args) -> int:
    qoder_dir = resolve_qoder_data_dir()
    print("=" * 60)
    print(f"🔒 Qoder-Free v{__version__} [CLI Mode]")
    print(f"Platform: {platform.system()} ({platform.machine()})")
    print(f"Qoder Data Directory: {qoder_dir}")
    print("=" * 60)

    if args.close_qoder:
        print("[*] Terminating Qoder processes...")
        success, details = kill_qoder_process()
        if success:
            print("[+] Qoder process terminated or not running.")
        else:
            print(f"[-] Failed to terminate Qoder: {details}")

    if args.check_update:
        print("[*] Checking for updates on GitHub...")
        update_info = check_for_updates()
        if update_info.get("success"):
            if update_info.get("has_update"):
                print(
                    f"[!] New version available: v{update_info['latest_version']} (Current: v{update_info['current_version']})"
                )
                print(f"    Download at: {update_info['url']}")
            else:
                print(f"[+] You are using the latest version (v{__version__}).")
        else:
            print(
                f"[-] Could not check updates: {update_info.get('error', 'Unknown error')}"
            )

    if args.list_backups:
        print("[*] Available Backups:")
        backups = list_qoder_backups(qoder_dir)
        if not backups:
            print("    No backups found.")
        else:
            for b in backups:
                print(f"    - {b.name} ({b})")

    if args.backup:
        print("[*] Creating identity backup...")
        try:
            backup_path = backup_qoder_identity(qoder_dir)
            print(f"[+] Backup created successfully at: {backup_path}")
        except Exception as e:
            print(f"[-] Backup failed: {e}")
            return 1

    if args.restore is not None:
        print("[*] Restoring identity from backup...")
        backups = list_qoder_backups(qoder_dir)
        if args.restore == "latest":
            if not backups:
                print("[-] No backups found to restore.")
                return 1
            target_backup = backups[0]
        else:
            target_backup = Path(args.restore)
            if not target_backup.is_dir():
                print(f"[-] Specified backup path does not exist: {target_backup}")
                return 1

        print(f"[*] Restoring from: {target_backup}")
        success, msg = restore_qoder_identity(target_backup, qoder_dir)
        if success:
            print(f"[+] {msg}")
        else:
            print(f"[-] Restore failed: {msg}")
            return 1

    if args.status:
        is_running = check_is_qoder_running()
        dir_exists = qoder_dir.exists()
        print(f"[*] Qoder Status:")
        print(f"    - Running: {'YES (Active)' if is_running else 'NO (Stopped)'}")
        print(f"    - Data directory exists: {'YES' if dir_exists else 'NO'}")
        if dir_exists:
            machine_id_file = qoder_dir / "machineid"
            if machine_id_file.is_file():
                try:
                    m_id = machine_id_file.read_text(encoding="utf-8").strip()
                    print(f"    - Machine ID: {m_id}")
                except Exception:
                    pass
            storage_file = qoder_dir / "User" / "globalStorage" / "storage.json"
            if storage_file.is_file():
                try:
                    data = json.loads(storage_file.read_text(encoding="utf-8"))
                    print(
                        f"    - Telemetry Machine ID: {data.get('telemetry.machineId', 'N/A')[:16]}..."
                    )
                    print(f"    - Device ID: {data.get('telemetry.devDeviceId', 'N/A')}")
                except Exception:
                    pass

    if args.reset:
        if check_is_qoder_running():
            print("[*] Qoder is running. Terminating processes first...")
            kill_qoder_process()

        # Auto-backup before reset
        try:
            b_path = backup_qoder_identity(qoder_dir)
            print(f"[+] Pre-reset backup saved to: {b_path.name}")
        except Exception:
            pass

        print(
            f"[*] Performing 1-Click Reset (preserve_chat={args.preserve_chat})..."
        )
        try:
            if not qoder_dir.exists():
                qoder_dir.mkdir(parents=True, exist_ok=True)

            # 1. Reset machine id
            m_id = reset_qoder_machine_id(qoder_dir)
            print(f"    [+] Machine ID reset: {m_id}")

            # Additional ID files
            for id_file in [
                "deviceid",
                "hardware_uuid",
                "system_uuid",
                "platform_id",
                "installation_id",
            ]:
                (qoder_dir / id_file).write_text(str(uuid.uuid4()), encoding="utf-8")

            # 2. Reset telemetry
            t_data = reset_qoder_telemetry(qoder_dir)
            print(
                f"    [+] Telemetry reset: {t_data.get('telemetry.machineId', '')[:16]}..."
            )

            # 3. Clean cache
            cache_dirs = [
                "Cache",
                "blob_storage",
                "Code Cache",
                "SharedClientCache",
                "GPUCache",
                "DawnGraphiteCache",
                "DawnWebGPUCache",
                "IndexedDB",
                "CacheStorage",
            ]
            c_count = 0
            for cd in cache_dirs:
                cp = qoder_dir / cd
                if cp.exists():
                    try:
                        shutil.rmtree(cp)
                        c_count += 1
                    except Exception:
                        pass
            print(f"    [+] Cleared {c_count} cache directories.")

            # 4. Clean identity files
            identity_files = [
                "Network Persistent State",
                "Cookies",
                "Cookies-journal",
                "Trust Tokens",
                "Trust Tokens-journal",
                "TransportSecurity",
                "Local State",
            ]
            f_count = 0
            for ifile in identity_files:
                ip = qoder_dir / ifile
                if ip.is_file():
                    try:
                        ip.unlink()
                        f_count += 1
                    except Exception:
                        pass
            print(f"    [+] Cleared {f_count} identity files.")

            # 5. Fake hardware info
            fake_hw = {
                "cpu_id": str(uuid.uuid4()),
                "bios_serial": str(uuid.uuid4()),
                "motherboard_uuid": str(uuid.uuid4()),
                "disk_serial": str(uuid.uuid4()),
                "mac_address": f"{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}",
                "reset_timestamp": datetime.now().isoformat(),
            }
            (qoder_dir / "hardware_info.json").write_text(
                json.dumps(fake_hw, indent=4), encoding="utf-8"
            )
            print("    [+] Generated new hardware fingerprint profile.")

            print("[SUCCESS] Qoder-Free Reset completed successfully!")
            return 0
        except Exception as e:
            print(f"[-] Reset failed: {e}")
            return 1

    return 0


def main():
    args = parse_args()

    # Determine if CLI mode should be executed
    cli_flags_present = any(
        [
            args.cli,
            args.reset,
            args.backup,
            args.restore is not None,
            args.list_backups,
            args.check_update,
            args.status,
            args.close_qoder,
        ]
    )

    if cli_flags_present or not HAS_PYQT5:
        if not HAS_PYQT5 and not cli_flags_present:
            print("Notice: PyQt5 is not installed. Running in CLI status mode.")
            print("To launch the GUI, run: pip install PyQt5")
            print("Use --help to see all available CLI commands.")
            print()
            args.status = True
        sys.exit(run_cli(args))

    _configure_qt_runtime()
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Set global style sheet
    app.setStyleSheet("""
        QMessageBox {
            background-color: white;
            color: black;
        }
        QMessageBox QLabel {
            color: black;
        }
        QMessageBox QPushButton {
            background-color: white;
            color: black;
            border: 1px solid #ccc;
            padding: 5px 15px;
        }
    """)

    window = QoderResetGUI()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
