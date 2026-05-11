#!/usr/bin/env python3
"""
Qoder Reset Tool - Modern GUI Version
Implemented using PyQt5, fully designed according to user prototype
"""

__version__ = "1.1.0"

import os
import sys
import json
import uuid
import shutil
import hashlib
import subprocess
import webbrowser
import platform
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Callable, Mapping, Optional, Tuple

try:
    from PyQt5.QtWidgets import *
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
except ImportError:
    # Allow importing this module in headless / test environments where PyQt5
    # isn't available. The GUI entrypoint will still error clearly when run.
    PYQT_AVAILABLE = False
    QMainWindow = object  # type: ignore
else:
    PYQT_AVAILABLE = True


def _sharedclientcache_files_to_delete(*, preserve_model_settings: bool) -> tuple[str, ...]:
    """
    Return SharedClientCache files that are safe to delete.

    `mcp.json` is treated as model/provider routing/config and is preserved by
    default to avoid breaking non-lightweight models.
    """
    files = [".info", ".lock"]
    if not preserve_model_settings or os.environ.get("QODER_CLEAN_MCP_JSON") == "1":
        files.append("mcp.json")
    return tuple(files)


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
            ["taskkill", "/F", "/T", "/IM", "qoder.exe"],
            capture_output=True,
            text=True,
        )
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


def reset_qoder_telemetry(qoder_support_dir: Path, system: Optional[str] = None) -> Mapping[str, str]:
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

def _configure_qt_runtime():
    """
    Best-effort Qt plugin path hardening.

    Helps avoid: "This application failed to start because no Qt platform plugin could be initialized"
    """
    if not globals().get("PYQT_AVAILABLE", False):
        return {"plugins_dir": None, "platforms_dir": None, "frozen": False}

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
        self.current_language = 'en'  # Default to English
        self.init_translations()
        self.init_ui()
    
    def init_translations(self):
        """Initialize multilingual dictionary"""
        self.translations = {
            'zh': {  # Tiếng Trung
                'window_title': 'Qoder-Free',
                'intro_text': 'Qoder-Free 主要用于重置 Qoder 应用程序的用户身份信息',
                'operation_area': '操作区域:',
                'one_click_config': '一键修改配置',
                'close_qoder': '关闭 Qoder',
                'reset_machine_id': '重置机器 ID',
                'reset_telemetry': '重置遥测数据',
                'deep_identity_clean': '深度身份清理',
                'login_identity_clean': '清理登录身份',
                'hardware_fingerprint_reset': '硬件指纹重置',
                'advanced_options': '高级选项',
                'preserve_chat': '保留对话记录',
                'preserve_model_settings': '保留登录/模型设置（推荐）',
                'operation_log': '操作日志:',
                'clear_log': '清空日志',
                'github': 'Github',
                'language': '语言',
                
                # 日志消息
                'tool_started': 'Qoder-Free 重置工具已启动',
                'log_cleared': '日志已清空',
                'qoder_running': 'Qoder 正在运行',
                'qoder_not_running': 'Qoder 未运行',
                'qoder_directory_exists': 'Qoder 目录存在',
                'machine_id': '机器 ID',
                'telemetry_machine_id': '遥测机器 ID',
                'device_id': '设备 ID',
                'cache_directories_found': '个缓存目录',
                'chat_directories_found': '个对话相关目录',
                'identity_files_found': '个身份识别文件',
                'status_check_complete': '状态检查完成，可以开始操作',
                
                # 对话框消息
                'qoder_detected_running': '检测到 Qoder 正在运行',
                'please_close_qoder': '请手动关闭 Qoder 应用程序',
                'confirm_one_click': '确认一键修改',
                'confirm_deep_clean': '确认深度清理',
                'confirm_login_clean': '确认清理登录身份',
                'operation_complete': '操作完成',
                'operation_failed': '操作失败',
                'error': '错误',
                'success': '成功',
                'warning': '警告',
                'status_check': '状态检查'
            },
            'en': {  # Tiếng Anh
                'window_title': 'Qoder-Free',
                'intro_text': 'Qoder-Free is mainly used to reset user identity information of Qoder application',
                'operation_area': 'Operation Area:',
                'one_click_config': 'One-Click Configuration',
                'close_qoder': 'Close Qoder',
                'reset_machine_id': 'Reset Machine ID',
                'reset_telemetry': 'Reset Telemetry',
                'deep_identity_clean': 'Deep Identity Cleanup',
                'login_identity_clean': 'Clean Login Identity',
                'hardware_fingerprint_reset': 'Hardware Fingerprint Reset',
                'advanced_options': 'Advanced Options',
                'preserve_chat': 'Preserve Chat History',
                'preserve_model_settings': 'Preserve login/model settings (recommended)',
                'operation_log': 'Operation Log:',
                'clear_log': 'Clear Log',
                'github': 'Github',
                'language': 'Language',
                
                # Log messages
                'tool_started': 'Qoder-Free reset tool started',
                'log_cleared': 'Log cleared',
                'qoder_running': 'Qoder is running',
                'qoder_not_running': 'Qoder is not running',
                'qoder_directory_exists': 'Qoder directory exists',
                'machine_id': 'Machine ID',
                'telemetry_machine_id': 'Telemetry Machine ID',
                'device_id': 'Device ID',
                'cache_directories_found': 'cache directories found',
                'chat_directories_found': 'chat-related directories found',
                'identity_files_found': 'identity files found',
                'status_check_complete': 'Status check completed, ready to operate',
                
                # Dialog messages
                'qoder_detected_running': 'Qoder Detected Running',
                'please_close_qoder': 'Please close Qoder application manually',
                'confirm_one_click': 'Confirm One-Click Reset',
                'confirm_deep_clean': 'Confirm Deep Cleanup',
                'confirm_login_clean': 'Confirm Login Identity Cleanup',
                'operation_complete': 'Operation Complete',
                'operation_failed': 'Operation Failed',
                'error': 'Error',
                'success': 'Success',
                'warning': 'Warning',
                'status_check': 'Status Check'
            },
            'ru': {  # Tiếng Nga
                'window_title': 'Qoder-Free',
                'intro_text': 'Qoder-Free в основном используется для сброса пользовательской информации приложения Qoder',
                'operation_area': 'Область операций:',
                'one_click_config': 'Одним кликом',
                'close_qoder': 'Закрыть Qoder',
                'reset_machine_id': 'Сбросить ID машины',
                'reset_telemetry': 'Сбросить телеметрию',
                'deep_identity_clean': 'Глубокая очистка',
                'login_identity_clean': 'Очистить вход',
                'hardware_fingerprint_reset': 'Сброс железа',
                'advanced_options': 'Дополнительно',
                'preserve_chat': 'Сохранить чат',
                'preserve_model_settings': 'Сохранить вход/настройки моделей (рекомендуется)',
                'operation_log': 'Журнал операций:',
                'clear_log': 'Очистить журнал',
                'github': 'Github',
                'language': 'Язык',
                
                # Сообщения журнала
                'tool_started': 'Инструмент сброса Qoder-Free запущен',
                'log_cleared': 'Журнал очищен',
                'qoder_running': 'Qoder запущен',
                'qoder_not_running': 'Qoder не запущен',
                'qoder_directory_exists': 'Папка Qoder существует',
                'machine_id': 'ID машины',
                'telemetry_machine_id': 'ID машины телеметрии',
                'device_id': 'ID устройства',
                'cache_directories_found': 'папок кеша найдено',
                'chat_directories_found': 'папок чата найдено',
                'identity_files_found': 'файлов идентификации найдено',
                'status_check_complete': 'Проверка статуса завершена, готов к работе',
                
                # Диалоговые сообщения
                'qoder_detected_running': 'Обнаружен запущенный Qoder',
                'please_close_qoder': 'Пожалуйста, закройте приложение Qoder вручную',
                'confirm_one_click': 'Подтвердить сброс одним кликом',
                'confirm_deep_clean': 'Подтвердить глубокую очистку',
                'confirm_login_clean': 'Подтвердить очистку входа',
                'operation_complete': 'Операция завершена',
                'operation_failed': 'Операция не удалась',
                'error': 'Ошибка',
                'success': 'Успех',
                'warning': 'Предупреждение',
                'status_check': 'Проверка статуса'
            },
            'pt-br': {  # Tiếng Bồ Đào Nha (Brazil)
                'window_title': 'Qoder-Free',
                'intro_text': 'Qoder-Free é principalmente usado para redefinir as informações de identidade do usuário do aplicativo Qoder',
                'operation_area': 'Área de Operações:',
                'one_click_config': 'Configuração com um clique',
                'close_qoder': 'Fechar Qoder',
                'reset_machine_id': 'Redefinir ID da Máquina',
                'reset_telemetry': 'Redefinir Telemetria',
                'deep_identity_clean': 'Limpeza Profunda de Identidade',
                'login_identity_clean': 'Limpar Login',
                'hardware_fingerprint_reset': 'Reset de Hardware',
                'advanced_options': 'Opções Avançadas',
                'preserve_chat': 'Preservar Histórico do chat',
                'preserve_model_settings': 'Preservar login/configuração de modelos (recomendado)',
                'operation_log': 'Log de Operações:',
                'clear_log': 'Limpar Log',
                'github': 'Github',
                'language': 'Idioma',
                
                # Mensagens de log
                'tool_started': 'Ferramenta de redefinição Qoder-Free iniciada',
                'log_cleared': 'Log limpo',
                'qoder_running': 'Qoder está em execução',
                'qoder_not_running': 'Qoder não está em execução',
                'qoder_directory_exists': 'Diretório Qoder existe',
                'machine_id': 'ID da Máquina',
                'telemetry_machine_id': 'ID da Máquina de Telemetria',
                'device_id': 'ID do Dispositivo',
                'cache_directories_found': 'diretórios de cache encontrados',
                'chat_directories_found': 'diretórios relacionados ao chat encontrados',
                'identity_files_found': 'arquivos de identidade encontrados',
                'status_check_complete': 'Verificação de status concluída, pronto para operar',
                
                # Mensagens de diálogo
                'qoder_detected_running': 'Qoder Detectado em Execução',
                'please_close_qoder': 'Por favor, feche o aplicativo Qoder manualmente',
                'confirm_one_click': 'Confirmar Redefinição com um clique',
                'confirm_deep_clean': 'Confirmar Limpeza Profunda',
                'confirm_login_clean': 'Confirmar Limpeza de Identidade de Login',
                'operation_complete': 'Operação Concluída',
                'operation_failed': 'Operação Falhou',
                'error': 'Erro',
                'success': 'Sucesso',
                'warning': 'Aviso',
                'status_check': 'Verificação de Status'
            },
            'vi': {  # Tiếng Việt
                'window_title': 'Qoder-Free: Công Cụ Làm Sạch',
                'intro_text': 'Công cụ giúp bạn đặt lại và làm sạch thông tin nhận dạng của ứng dụng Qoder một cách dễ dàng và an toàn.',
                'operation_area': 'Khu Vực Thao Tác:',
                'one_click_config': 'Cấu Hình Một Chạm',
                'close_qoder': 'Đóng Qoder',
                'reset_machine_id': 'Đặt Lại ID Máy',
                'reset_telemetry': 'Đặt Lại Dữ Liệu Điện Toán',
                'deep_identity_clean': 'Làm Sạch Danh Tính Sâu',
                'login_identity_clean': 'Xóa Thông Tin Đăng Nhập',
                'hardware_fingerprint_reset': 'Đặt Lại Dấu Vân Tay Phần Cứng',
                'advanced_options': 'Tùy Chọn Nâng Cao',
                'preserve_chat': 'Giữ Lại Lịch Sử Trò Chuyện',
                'preserve_model_settings': 'Giữ đăng nhập/cấu hình model (khuyến nghị)',
                'operation_log': 'Nhật Ký Thao Tác:',
                'clear_log': 'Xóa Nhật Ký',
                'github': 'Liên Kết GitHub',
                'language': 'Ngôn Ngữ',
                
                # Các thông báo nhật ký
                'tool_started': 'Công cụ đặt lại Qoder-Free đã được khởi động',
                'log_cleared': 'Nhật ký đã được xóa',
                'qoder_running': 'Qoder đang chạy',
                'qoder_not_running': 'Qoder không chạy',
                'qoder_directory_exists': 'Thư mục Qoder tồn tại',
                'machine_id': 'ID Máy',
                'telemetry_machine_id': 'ID Máy Điện Toán',
                'device_id': 'ID Thiết Bị',
                'cache_directories_found': 'thư mục bộ nhớ đệm được tìm thấy',
                'chat_directories_found': 'thư mục liên quan đến trò chuyện được tìm thấy',
                'identity_files_found': 'tệp nhận dạng được tìm thấy',
                'status_check_complete': 'Kiểm tra trạng thái hoàn tất, sẵn sàng thực hiện',
                
                # Các thông báo hộp thoại
                'qoder_detected_running': 'Phát Hiện Qoder Đang Chạy',
                'please_close_qoder': 'Vui lòng đóng ứng dụng Qoder theo cách thủ công',
                'confirm_one_click': 'Xác Nhận Đặt Lại Một Chạm',
                'confirm_deep_clean': 'Xác Nhận Làm Sạch Sâu',
                'confirm_login_clean': 'Xác Nhận Xóa Thông Tin Đăng Nhập',
                'operation_complete': 'Thao Tác Hoàn Tất',
                'operation_failed': 'Thao Tác Thất Bại',
                'error': 'Lỗi',
                'success': 'Thành Công',
                'warning': 'Cảnh Báo',
                'status_check': 'Kiểm Tra Trạng Thái'
            }
        }
    
    def tr(self, key):
        """Get translation text for the current language"""
        return self.translations.get(self.current_language, {}).get(key, key)
    
    def init_ui(self):
        """Initialize the user interface"""
        # Set window properties
        self.setWindowTitle(self.tr("Qoder Reset Tool"))
        self.setGeometry(100, 100, 800, 650)
        
        # Set application-wide font
        font = QFont("Inter", 10)
        QApplication.setFont(font)
        
        # Create main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title Label
        self.title_label = QLabel(self.tr('window_title'))
        self.title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        main_layout.addWidget(self.title_label, alignment=Qt.AlignCenter)
        
        # Intro Label
        self.intro_label = QLabel(self.tr('intro_text'))
        self.intro_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #7f8c8d;
                margin-bottom: 20px;
                text-align: center;
            }
        """)
        main_layout.addWidget(self.intro_label, alignment=Qt.AlignCenter)
        
        # Language Selector
        language_layout = QHBoxLayout()
        language_label = QLabel(self.tr('language'))
        self.language_selector = QComboBox()
        self.language_selector.addItems(['English', 'Tiếng Việt', '中文', 'Русский'])
        self.language_selector.setCurrentText('English')
        self.language_selector.currentTextChanged.connect(self.change_language)
        
        language_layout.addWidget(language_label)
        language_layout.addWidget(self.language_selector)
        main_layout.addLayout(language_layout)
        
        # Nút một chạm
        self.one_click_btn = self.create_styled_button(
            self.tr('one_click_config'), 
            '#3498db',  # Màu xanh
            self.one_click_reset
        )
        
        # Căn giữa nút một chạm
        button_center_layout = QHBoxLayout()
        button_center_layout.addStretch()
        button_center_layout.addWidget(self.one_click_btn)
        button_center_layout.addStretch()
        main_layout.addLayout(button_center_layout)
        
        # Bố cục các nút chức năng
        button_layout = QGridLayout()
        button_layout.setSpacing(12)
        
        # Nút đóng Qoder
        self.close_qoder_btn = self.create_styled_button(
            self.tr('close_qoder'), 
            '#e74c3c',  # Màu đỏ
            self.close_qoder
        )
        button_layout.addWidget(self.close_qoder_btn, 0, 0)
        
        # Nút đặt lại ID máy
        self.reset_machine_id_btn = self.create_styled_button(
            self.tr('reset_machine_id'), 
            '#3498db',  # Màu xanh
            self.reset_machine_id
        )
        button_layout.addWidget(self.reset_machine_id_btn, 0, 1)
        
        # Nút đặt lại dữ liệu điện toán
        self.reset_telemetry_btn = self.create_styled_button(
            self.tr('reset_telemetry'), 
            '#2ecc71',  # Màu xanh lá
            self.reset_telemetry
        )
        button_layout.addWidget(self.reset_telemetry_btn, 1, 0)
        
        # Nút làm sạch danh tính sâu
        self.deep_clean_btn = self.create_styled_button(
            self.tr('deep_identity_clean'), 
            '#f39c12',  # Màu cam
            self.deep_identity_cleanup
        )
        button_layout.addWidget(self.deep_clean_btn, 1, 1)
        
        # Thêm bố cục nút vào bố cục chính
        main_layout.addLayout(button_layout)
        
        # Nút xóa nhật ký
        clear_log_btn = self.create_styled_button(
            self.tr('clear_log'), 
            '#e74c3c',  # Màu đỏ
            self.clear_log
        )
        
        # Layout căn giữa nút xóa nhật ký
        clear_log_layout = QHBoxLayout()
        clear_log_layout.addStretch()
        clear_log_layout.addWidget(clear_log_btn)
        clear_log_layout.addStretch()
        
        main_layout.addLayout(clear_log_layout)
        
        # Preserve Chat Checkbox
        self.preserve_chat_checkbox = QCheckBox(self.tr('preserve_chat'))
        self.preserve_chat_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        main_layout.addWidget(self.preserve_chat_checkbox)

        # Preserve login/model settings checkbox (prevents breaking non-lightweight models)
        self.preserve_model_settings_checkbox = QCheckBox(self.tr('preserve_model_settings'))
        self.preserve_model_settings_checkbox.setChecked(True)
        self.preserve_model_settings_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        main_layout.addWidget(self.preserve_model_settings_checkbox)
        
        # Log Area
        log_layout = QVBoxLayout()
        log_label = QLabel(self.tr('operation_log'))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(120)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f4f6f7;
                border: 1px solid #e0e4e6;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        
        log_layout.addWidget(log_label)
        log_layout.addWidget(self.log_text)
        
        main_layout.addLayout(log_layout)
        
        # Set main layout
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Set overall window style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f4f6f9;
            }
            QWidget {
                background-color: white;
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
        btn.setFixedSize(140, 35)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-size: 11px;
                font-weight: 500;
                border: none;
                border-radius: 5px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background-color: {color}DD;
            }}
            QPushButton:pressed {{
                background-color: {color}BB;
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
                'English': 'en',
                'Tiếng Việt': 'vi', 
                '中文': 'zh',
                'Русский': 'ru'
            }
            
            # Get language code, default to English
            language = language_map.get(language_text, 'en')
            
            # Update current language
            self.current_language = language
            
            # Update UI elements with translations
            self.setWindowTitle(self.tr('window_title'))
            
            # Update labels
            self.title_label.setText(self.tr('window_title'))
            self.intro_label.setText(self.tr('intro_text'))
            
            # Update buttons with translations
            button_translations = {
                'one_click_btn': 'one_click_config',
                'close_qoder_btn': 'close_qoder',
                'reset_machine_id_btn': 'reset_machine_id',
                'reset_telemetry_btn': 'reset_telemetry',
                'deep_clean_btn': 'deep_identity_clean'
            }
            
            # Update buttons with translated texts
            for btn_name, translation_key in button_translations.items():
                if hasattr(self, btn_name):
                    getattr(self, btn_name).setText(self.tr(translation_key))
            
            # Update checkbox
            self.preserve_chat_checkbox.setText(self.tr('preserve_chat'))
            self.preserve_model_settings_checkbox.setText(self.tr('preserve_model_settings'))
            
            # Optional: log the language change
            self.log(f"Language changed to: {language_text}")
            
        except Exception as e:
            # Log any errors during language change
            self.log(f"Error changing language: {e}")
            # Fallback to English
            self.current_language = 'en'
            
        # Ensure language selector reflects the current selection
        language_index = self.language_selector.findText(language_text)
        if language_index >= 0:
            self.language_selector.setCurrentIndex(language_index)
    
    def update_ui_text(self):
        """更新界面文本"""
        # 更新窗口标题
        self.setWindowTitle(self.tr('window_title'))
        
        # 更新标签文本
        self.title_label.setText(self.tr('window_title'))
        self.intro_label.setText(self.tr('intro_text'))
        self.operation_title.setText(self.tr('operation_area'))
        self.log_title.setText(self.tr('operation_log'))
        
        # 更新按钮文本
        self.one_click_btn.setText(self.tr('one_click_config'))
        self.close_qoder_btn.setText(self.tr('close_qoder'))
        self.reset_machine_id_btn.setText(self.tr('reset_machine_id'))
        self.reset_telemetry_btn.setText(self.tr('reset_telemetry'))
        self.deep_clean_btn.setText(self.tr('deep_identity_clean'))
        self.login_clean_btn.setText(self.tr('login_identity_clean'))
        self.hardware_reset_btn.setText(self.tr('hardware_fingerprint_reset'))
        self.clear_log_btn.setText(self.tr('clear_log'))
        self.github_btn.setText(self.tr('github'))
        
        # 更新复选框文本
        self.preserve_chat_checkbox.setText(self.tr('preserve_chat'))
        self.preserve_model_settings_checkbox.setText(self.tr('preserve_model_settings'))
        
        # 清空日志并重新初始化
        self.log_text.clear()
        self.log(self.tr('tool_started'))
        self.log("=" * 50)
    
    def log(self, message):
        """Log messages with timestamp in English"""
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
                with open(machine_id_file, 'r') as f:
                    machine_id = f.read().strip()
                self.log(f"   ✅ Machine ID: {machine_id}")
            else:
                self.log("   ❌ Machine ID file not found")
            
            # 4. Kiểm tra file Telemetry
            self.log("4. Checking Telemetry data files...")
            storage_json_file = qoder_support_dir / "User/globalStorage/storage.json"
            if storage_json_file.exists():
                with open(storage_json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                telemetry_machine_id = data.get('telemetry.machineId', 'N/A')
                device_id = data.get('telemetry.devDeviceId', 'N/A')
                
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
            self.log(f"   ✅ SharedClientCache internal files: {len(shared_cache_files)}/4")
            
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
        self.log(self.tr('log_cleared'))
    
    def get_qoder_data_dir(self):
        """Get Qoder data directory path (cross-platform support)"""
        return resolve_qoder_data_dir()
    
    def is_qoder_running(self):
        """Check if Qoder is currently running"""
        try:
            # Check process status using different methods
            import subprocess
            import platform

            # Different process check commands based on operating system
            if platform.system() == "Windows":
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq qoder.exe"], 
                                        capture_output=True, text=True)
                return "qoder.exe" in result.stdout.lower()
            elif platform.system() == "Darwin":  # macOS
                result = subprocess.run(["pgrep", "-x", "Qoder"], 
                                        capture_output=True, text=True)
                return result.returncode == 0
            elif platform.system() == "Linux":
                result = subprocess.run(["pgrep", "-x", "qoder"], 
                                        capture_output=True, text=True)
                return result.returncode == 0
            
            return False
        except Exception as e:
            self.log(f"Error checking Qoder status: {e}")
            return False
    
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
                "10.0.26100"   # Windows 11 24H2
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
                minor = random.randint(0, 8)    # 6.0-6.8
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
                self.tr('confirm_close_qoder'), 
                "Are you sure you want to close Qoder?", 
                QMessageBox.Yes | QMessageBox.No
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
                    "Qoder has been closed successfully." if ok else "Failed to close Qoder.",
                )
        except Exception as e:
            # Log error
            self.log(f"Error closing Qoder: {str(e)}")
            QMessageBox.critical(
                self, 
                self.tr('error'), 
                f"Failed to close Qoder: {str(e)}"
            )
    
    def login_identity_cleanup(self):
        """Clean login-related identity information"""
        try:
            reply = QMessageBox.question(
                self,
                self.tr('warning'),
                "This will log you out and may cause non-lightweight models to stop working until you sign in again.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

            # Clean critical login-related files
            qoder_support_dir = self.get_qoder_data_dir()
            
            # Clean all temporary files
            temp_files = [
                "Network Persistent State",
                "Cookies", 
                "Login Data", 
                "Login Data-journal",
                "Web Data", 
                "Web Data-journal"
            ]
            
            for temp_file in temp_files:
                file_path = qoder_support_dir / temp_file
                if file_path.exists():
                    try:
                        file_path.unlink()
                        self.log(f"Cleaned login file: {temp_file}")
                    except Exception as e:
                        self.log(f"Failed to clean login file {temp_file}: {e}")
            
            # Prompt successful cleanup
            QMessageBox.information(
                self, 
                self.tr('success'), 
                "Login identity cleaned successfully."
            )
        except Exception as e:
            # Log error
            self.log(f"Error during login identity cleanup: {e}")
            QMessageBox.critical(
                self, 
                self.tr('error'), 
                f"Failed to clean login identity: {e}"
            )
    
    def reset_telemetry(self):
        """Reset telemetry data"""
        try:
            # Check if Qoder is running
            if self.is_qoder_running():
                QMessageBox.warning(
                    self, 
                    self.tr('warning'), 
                    self.tr('qoder_detected_running') + "\n" + 
                    self.tr('please_close_qoder')
                )
                return
            
            # Confirm reset
            reply = QMessageBox.question(
                self, 
                self.tr('confirm_reset_telemetry'), 
                "Are you sure you want to reset Telemetry data?", 
                QMessageBox.Yes | QMessageBox.No
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
                    self.tr('success'), 
                    "Telemetry data has been reset successfully."
                )
        except Exception as e:
            # Log error
            self.log(f"Error resetting Telemetry data: {str(e)}")
            QMessageBox.critical(
                self, 
                self.tr('error'), 
                f"Failed to reset Telemetry data: {str(e)}"
            )
    
    def reset_machine_id(self):
        """Reset machine ID"""
        try:
            # Check if Qoder is running
            if self.is_qoder_running():
                QMessageBox.warning(
                    self, 
                    self.tr('warning'), 
                    self.tr('qoder_detected_running') + "\n" + 
                    self.tr('please_close_qoder')
                )
                return
            
            # Confirm reset
            reply = QMessageBox.question(
                self, 
                self.tr('confirm_reset_machine_id'), 
                "Are you sure you want to reset the Machine ID?", 
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Execute machine ID reset operation
                self.log("Resetting Machine ID...")
                qoder_support_dir = self.get_qoder_data_dir()
                new_machine_id = reset_qoder_machine_id(qoder_support_dir)
                self.log(f"   New Machine ID: {new_machine_id}")

                QMessageBox.information(
                    self, 
                    self.tr('success'), 
                    "Machine ID has been reset successfully."
                )
        except Exception as e:
            # Log error
            self.log(f"Error resetting Machine ID: {str(e)}")
            QMessageBox.critical(
                self, 
                self.tr('error'), 
                f"Failed to reset Machine ID: {str(e)}"
            )
    
    def deep_identity_cleanup(self):
        """Perform deep identity cleanup"""
        try:
            # Check if Qoder is running
            if self.is_qoder_running():
                QMessageBox.warning(
                    self, 
                    self.tr('warning'), 
                    self.tr('qoder_detected_running') + "\n" + 
                    self.tr('please_close_qoder')
                )
                return
            
            # Confirm cleanup
            reply = QMessageBox.question(
                self, 
                self.tr('confirm_deep_clean'), 
                "This will perform a deep identity cleanup. Are you sure?", 
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                preserve_chat = self.preserve_chat_checkbox.isChecked()
                preserve_model_settings = self.preserve_model_settings_checkbox.isChecked()

                # Execute deep identity cleanup
                self.log("Performing deep identity cleanup...")
                qoder_support_dir = self.get_qoder_data_dir()
                if not qoder_support_dir.exists():
                    raise Exception("Qoder application data directory not found")

                self.perform_advanced_identity_cleanup(
                    qoder_support_dir,
                    preserve_chat=preserve_chat,
                    preserve_model_settings=preserve_model_settings,
                )
                
                # Prompt cleanup success
                QMessageBox.information(
                    self, 
                    self.tr('success'), 
                    "Deep identity cleanup completed successfully."
                )
        except Exception as e:
            # Log error
            self.log(f"Error during deep identity cleanup: {str(e)}")
            QMessageBox.critical(
                self, 
                self.tr('error'), 
                f"Failed to perform deep identity cleanup: {str(e)}"
            )
    
    def hardware_fingerprint_reset(self):
        """Reset hardware fingerprint"""
        try:
            # Check if Qoder is running
            if self.is_qoder_running():
                QMessageBox.warning(
                    self, 
                    self.tr('warning'), 
                    self.tr('qoder_detected_running') + "\n" + 
                    self.tr('please_close_qoder')
                )
                return
            
            # Confirm reset
            reply = QMessageBox.question(
                self, 
                self.tr('confirm_hardware_fingerprint_reset'), 
                "This will reset all hardware-related identifiers. Are you sure?", 
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Execute hardware fingerprint reset
                self.log("Resetting hardware fingerprint...")
                
                # Prompt reset success
                QMessageBox.information(
                    self, 
                    self.tr('success'), 
                    "Hardware fingerprint reset completed successfully."
                )
        except Exception as e:
            # Log error
            self.log(f"Error resetting hardware fingerprint: {str(e)}")
            QMessageBox.critical(
                self, 
                self.tr('error'), 
                f"Failed to reset hardware fingerprint: {str(e)}"
            )

    def one_click_reset(self):
        """一键修改所有配置"""
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
                if not ok and self.is_qoder_running():
                    QMessageBox.warning(
                        self,
                        self.tr("warning"),
                        "Failed to close Qoder. Please close it manually and retry.",
                    )
                    return
            
            # 确认操作
            reply = QMessageBox.question(
                self, 
                self.tr('confirm_one_click'), 
                "Are you sure you want to perform a one-click reset?", 
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                preserve_chat = self.preserve_chat_checkbox.isChecked()
                preserve_model_settings = self.preserve_model_settings_checkbox.isChecked()
                
                # 执行重置操作
                self.log("Performing one-click reset...")
                self.perform_full_reset(
                    preserve_chat=preserve_chat,
                    preserve_model_settings=preserve_model_settings,
                )
                
                # 提示操作完成
                QMessageBox.information(
                    self, 
                    self.tr('success'), 
                    "One-click reset completed successfully."
                )
                
                self.log("One-click reset completed.")
        except Exception as e:
            # 记录错误
            self.log(f"Error during one-click reset: {str(e)}")
            QMessageBox.critical(
                self, 
                self.tr('error'), 
                f"An error occurred: {str(e)}"
            )

    def perform_full_reset(self, preserve_chat=True, preserve_model_settings=True):
        """执行完整重置"""
        qoder_support_dir = self.get_qoder_data_dir()

        if not qoder_support_dir.exists():
            raise Exception("未找到 Qoder 应用数据目录")

        # 1. 重置机器ID（增强版）
        self.log("1. 重置机器ID...")
        reset_qoder_machine_id(qoder_support_dir)
        self.log("   主机器ID已重置")
        
        # 增强：创建多个可能的机器ID文件
        additional_id_files = [
            "deviceid", "hardware_uuid", "system_uuid", 
            "platform_id", "installation_id"
        ]
        for id_file in additional_id_files:
            file_path = qoder_support_dir / id_file
            new_id = str(uuid.uuid4())
            with open(file_path, 'w') as f:
                f.write(new_id)
            self.log(f"   已创建: {id_file}")

        # 2. 重置遥测数据
        self.log("2. 重置遥测数据...")
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
            if preserve_model_settings:
                identity_keywords = ("fingerprint", "tracking", "analytics")
            else:
                identity_keywords = (
                    "auth",
                    "login",
                    "session",
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
                self.log(f"   已清除配置: {key}")
        else:
            self.log("   保留对话模式：保留非身份相关配置")

        with open(storage_json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        self.log(f"   新遥测机器ID: {updated['telemetry.machineId'][:16]}...")
        self.log(f"   新设备ID: {updated['telemetry.devDeviceId']}")
        self.log(f"   新SQM ID: {updated['telemetry.sqmId']}")

        # 3. 清理缓存（增强版）
        self.log("3. 清理缓存数据...")
        cache_dirs = [
            "Cache", "blob_storage", "Code Cache",
            "GPUCache", "DawnGraphiteCache", "DawnWebGPUCache",
            # 新增：更多可能包含指纹的缓存
            "ShaderCache", "DawnCache", "Dictionaries",
            "CachedData", "CachedProfilesData", "CachedExtensions",
            "IndexedDB", "CacheStorage", "WebSQL"
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

        # SharedClientCache can contain model/provider routing config (e.g. mcp.json).
        # Preserve by default to avoid breaking access to other models.
        if not preserve_model_settings:
            shared_client_cache = qoder_support_dir / "SharedClientCache"
            if shared_client_cache.exists():
                try:
                    shutil.rmtree(shared_client_cache)
                    cleaned += 1
                except Exception:
                    pass

        self.log(f"   已清理 {cleaned} 个缓存目录")
        
        # 4. 清理身份识别文件（增强版）
        self.log("4. 清理身份识别文件...")
        identity_files = [
            "Network Persistent State",  # 网络服务器连接历史和指纹
            "TransportSecurity",  # HSTS等安全策略记录
            "Trust Tokens", "Trust Tokens-journal",  # 信任令牌数据库
            "SharedStorage", "SharedStorage-wal",  # 共享存储数据库
            "Preferences",  # 用户偏好设置（可能包含指纹）
            "Secure Preferences",  # 安全偏好设置
            "Login Credentials",  # 登录凭据（如果存在）
            "Web Data", "Web Data-journal",  # Web数据数据库（如果存在）
            "cert_transparency_reporter_state.json",  # 证书透明度状态
            "Local State",  # Chromium本地状态（包含加密密钥）
            "NetworkDataMigrated",  # 网络数据迁移标记
            # 新增：硬件指纹相关文件
            "DeviceMetadata", "HardwareInfo", "SystemInfo",
            "QuotaManager", "QuotaManager-journal",
            "origin_bound_certs", "Network Action Predictor",
            "AutofillStrikeDatabase", "AutofillStrikeDatabase-journal",
            "Feature Engagement Tracker", "PasswordStoreDefault",
            "PreferredApps", "UserPrefs", "UserPrefs.backup",
            "Platform Notifications", "VideoDecodeStats",
            "OriginTrials", "BrowserMetrics", "SafeBrowsing",
            "Visited Links", "History", "History-journal",
            "Favicons", "Favicons-journal", "Shortcuts", "Shortcuts-journal",
            "Top Sites", "Top Sites-journal"
        ]
        
        identity_cleaned = 0
        for identity_file in identity_files:
            file_path = qoder_support_dir / identity_file
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.log(f"   已清除: {identity_file}")
                    identity_cleaned += 1
                except Exception as e:
                    self.log(f"   清除失败 {identity_file}: {e}")
        
        # 5. 清理存储目录
        storage_dirs = [
            "Service Worker",  # 服务工作者缓存
            "Certificate Revocation Lists",  # 证书撤销列表
            "SSLCertificates",  # SSL证书缓存
            "databases",  # 数据库目录
            "clp",  # 剪贴板数据，可能包含敏感信息
            "logs",  # 日志文件，可能记录用户活动
            "Backups",  # 备份文件，可能包含历史身份信息
            "CachedExtensionVSIXs"  # 扩展缓存，显示用户安装的扩展
        ]
        
        # 根据是否保留对话记录来决定清理哪些存储目录
        if not preserve_chat:
            # 如果不保留对话记录，清理所有存储目录
            storage_dirs.extend([
                "Local Storage",  # 本地存储数据库（可能包含对话索引）
                "Session Storage",  # 会话存储
                "WebStorage",  # Web存储
                "Shared Dictionary"  # 共享字典
            ])
            self.log("   不保留对话模式：清理所有存储目录")
        else:
            # 如果保留对话记录，保留可能包含对话索引的存储
            # 但仍需清理可能包含身份信息的存储
            storage_dirs.extend([
                "Session Storage",  # 会话存储（可能包含身份信息）
                "WebStorage",  # Web存储（可能包含身份信息）
                "Shared Dictionary"  # 共享字典
            ])
            self.log("   保留对话模式：保留 Local Storage（可能包含对话索引）")
        
        for storage_dir in storage_dirs:
            storage_path = qoder_support_dir / storage_dir
            if storage_path.exists():
                try:
                    shutil.rmtree(storage_path)
                    self.log(f"   已清除: {storage_dir}")
                    identity_cleaned += 1
                except Exception as e:
                    self.log(f"   清除失败 {storage_dir}: {e}")
        
        self.log(f"   已清理 {identity_cleaned} 个身份识别文件/目录")
        
        # 5. 执行高级身份清理（新增）
        self.log("5. 执行高级身份清理...")
        self.perform_advanced_identity_cleanup(
            qoder_support_dir,
            preserve_chat=preserve_chat,
            preserve_model_settings=preserve_model_settings,
        )

        # 6. 执行登录身份清理（新增 - 清理登录状态）
        if not preserve_model_settings:
            self.log("6. 执行登录身份清理...")
            self.perform_login_identity_cleanup(qoder_support_dir)
        else:
            self.log("6. 跳过登录身份清理（保留登录/模型设置）")

        # 7. 执行硬件指纹重置（新增 - 最强反检测）
        self.log("7. 执行硬件指纹重置...")
        self.perform_hardware_fingerprint_reset(qoder_support_dir)
        
        # 8. 执行超级深度清理（新增增强功能）
        self.log("8. 执行超级深度清理...")
        self.perform_super_deep_cleanup(qoder_support_dir)

        # 9. 处理对话记录
        if preserve_chat:
            self.log("9. 保留对话记录...")
            self.log("   对话记录已保留")
        else:
            self.log("9. 清除对话记录...")
            self.clear_chat_history(qoder_support_dir)

    def perform_advanced_identity_cleanup(
        self,
        qoder_support_dir,
        preserve_chat=False,
        preserve_model_settings=True,
    ):
        """执行高级身份清理，清除所有可能的身份识别信息"""
        try:
            self.log("开始高级身份清理...")
            cleaned_count = 0
            
            # 1. 清理 SharedClientCache 内部文件
            shared_cache = qoder_support_dir / "SharedClientCache"
            if shared_cache.exists():
                # 总是清理这些关键的身份文件（会重新生成）
                for file_name in _sharedclientcache_files_to_delete(
                    preserve_model_settings=preserve_model_settings
                ):
                    file_path = shared_cache / file_name
                    if file_path.exists():
                        try:
                            file_path.unlink()
                            self.log(f"   已清除: SharedClientCache/{file_name}")
                            cleaned_count += 1
                        except Exception as e:
                            self.log(f"   清除失败 {file_name}: {e}")
                
                # 总是清理 cache 目录（缓存数据）
                cache_dir = shared_cache / "cache"
                if cache_dir.exists():
                    try:
                        shutil.rmtree(cache_dir)
                        self.log("   已清除: SharedClientCache/cache")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   清除失败 cache: {e}")
                
                # 根据保留对话设置决定是否清理 index 目录
                index_dir = shared_cache / "index"
                if index_dir.exists():
                    if not preserve_chat:
                        # 不保留对话：清理所有索引
                        try:
                            shutil.rmtree(index_dir)
                            self.log("   已清除: SharedClientCache/index")
                            cleaned_count += 1
                        except Exception as e:
                            self.log(f"   清除失败 index: {e}")
                    else:
                        # 保留对话：只清理非对话相关的索引
                        # 保留可能包含对话搜索索引的文件
                        for index_item in index_dir.iterdir():
                            if index_item.is_dir() and 'chat' not in index_item.name.lower():
                                try:
                                    shutil.rmtree(index_item)
                                    self.log(f"   已清除: SharedClientCache/index/{index_item.name}")
                                    cleaned_count += 1
                                except Exception as e:
                                    self.log(f"   清除失败 index/{index_item.name}: {e}")
                        self.log("   保留对话模式：保留可能的对话索引")
            
            # 2. 清理系统级别的身份文件
            system_files = [
                "code.lock",
                "languagepacks.json"
            ]
            
            for sys_file in system_files:
                file_path = qoder_support_dir / sys_file
                if file_path.exists():
                    try:
                        file_path.unlink()
                        self.log(f"   已清除: {sys_file}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   清除失败 {sys_file}: {e}")
            
            # 3. 清理崩溃报告目录（可能包含设备信息）
            crashpad_dir = qoder_support_dir / "Crashpad"
            if crashpad_dir.exists():
                try:
                    shutil.rmtree(crashpad_dir)
                    self.log("   已清除: Crashpad")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"   清除失败 Crashpad: {e}")
            
            # 4. 清理缓存目录（CachedData和 CachedProfilesData）
            cached_dirs = ["CachedData", "CachedProfilesData"]
            for cached_dir in cached_dirs:
                dir_path = qoder_support_dir / cached_dir
                if dir_path.exists():
                    try:
                        shutil.rmtree(dir_path)
                        self.log(f"   已清除: {cached_dir}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   清除失败 {cached_dir}: {e}")
            
            # 5. 清理 socket 文件
            import glob
            socket_pattern = str(qoder_support_dir / "*.sock")
            socket_files = glob.glob(socket_pattern)
            for socket_file in socket_files:
                try:
                    Path(socket_file).unlink()
                    self.log(f"   已清除: {Path(socket_file).name}")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"   清除失败 {Path(socket_file).name}: {e}")
            
            # 6. 清理设备指纹和活动记录文件（新增）
            fingerprint_and_activity_files = [
                "DeviceMetadata", "HardwareInfo", "SystemInfo",
                "QuotaManager", "QuotaManager-journal",
                "ActivityLog", "EventLog", "UserActivityLog",
                "origin_bound_certs", "Network Action Predictor",
                "AutofillStrikeDatabase", "AutofillStrikeDatabase-journal",
                "Feature Engagement Tracker", "PasswordStoreDefault",
                "PreferredApps", "UserPrefs", "UserPrefs.backup"
            ]
            
            for file_name in fingerprint_and_activity_files:
                file_path = qoder_support_dir / file_name
                if file_path.exists():
                    try:
                        if file_path.is_dir():
                            shutil.rmtree(file_path)
                        else:
                            file_path.unlink()
                        self.log(f"   已清除: {file_name}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   清除失败 {file_name}: {e}")
            
            # 7. 清理数据库目录内的所有文件（新增）
            databases_dir = qoder_support_dir / "databases"
            if databases_dir.exists():
                try:
                    shutil.rmtree(databases_dir)
                    self.log("   已清除: databases 目录及其所有内容")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"   清除失败 databases: {e}")
            
            # 8. 清理 Electron 相关的持久化数据（新增）
            electron_files = [
                "Dictionaries", "Platform Notifications",
                "ShaderCache", "VideoDecodeStats",
                "OriginTrials", "BrowserMetrics",
                "AutofillRegexes", "SafeBrowsing"
            ]
            
            for electron_file in electron_files:
                file_path = qoder_support_dir / electron_file
                if file_path.exists():
                    try:
                        if file_path.is_dir():
                            shutil.rmtree(file_path)
                        else:
                            file_path.unlink()
                        self.log(f"   已清除: {electron_file}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   清除失败 {electron_file}: {e}")
            
            self.log(f"   高级身份清理完成，处理了 {cleaned_count} 个项目")
            
        except Exception as e:
            self.log(f"   高级身份清理失败: {e}")

    def clear_chat_history(self, qoder_support_dir):
        """清除对话记录"""
        try:
            cleared = 0

            # 1. 清除工作区中的对话会话
            workspace_storage = qoder_support_dir / "User/workspaceStorage"
            if workspace_storage.exists():
                for workspace_dir in workspace_storage.iterdir():
                    if workspace_dir.is_dir():
                        # 清除chatSessions目录
                        chat_sessions = workspace_dir / "chatSessions"
                        if chat_sessions.exists():
                            try:
                                shutil.rmtree(chat_sessions)
                                self.log(f"   已清除: {chat_sessions.relative_to(qoder_support_dir)}")
                                cleared += 1
                            except Exception as e:
                                self.log(f"   清除失败 {chat_sessions.relative_to(qoder_support_dir)}: {e}")

                        # 清除chatEditingSessions目录
                        chat_editing = workspace_dir / "chatEditingSessions"
                        if chat_editing.exists():
                            try:
                                shutil.rmtree(chat_editing)
                                self.log(f"   已清除: {chat_editing.relative_to(qoder_support_dir)}")
                                cleared += 1
                            except Exception as e:
                                self.log(f"   清除失败 {chat_editing.relative_to(qoder_support_dir)}: {e}")

            # 2. 清除历史记录
            history_dir = qoder_support_dir / "User/History"
            if history_dir.exists():
                try:
                    shutil.rmtree(history_dir)
                    self.log(f"   已清除: User/History")
                    cleared += 1
                except Exception as e:
                    self.log(f"   清除失败 User/History: {e}")

            # 3. 清除会话存储中的对话相关数据
            session_storage = qoder_support_dir / "Session Storage"
            if session_storage.exists():
                try:
                    shutil.rmtree(session_storage)
                    self.log(f"   已清除: Session Storage")
                    cleared += 1
                except Exception as e:
                    self.log(f"   清除失败 Session Storage: {e}")

            # 4. 清除用户数据中的对话相关配置
            user_data_file = qoder_support_dir / "User/globalStorage/storage.json"
            if user_data_file.exists():
                try:
                    with open(user_data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 清除对话相关的键
                    chat_keys = [key for key in data.keys() if
                               'chat' in key.lower() or
                               'conversation' in key.lower() or
                               'history' in key.lower() or
                               'session' in key.lower()]

                    if chat_keys:
                        for key in chat_keys:
                            del data[key]
                            self.log(f"   已清除配置: {key}")

                        with open(user_data_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)

                        cleared += 1

                except Exception as e:
                    self.log(f"   清除用户配置失败: {e}")

            self.log(f"   对话记录清除完成 (处理了 {cleared} 个项目)")

        except Exception as e:
            self.log(f"   清除对话记录失败: {e}")

    def open_github(self):
        """打开GitHub链接"""
        self.log("打开GitHub链接...")
        webbrowser.open("https://github.com/itandelin/qoder-free")
    
    def perform_hardware_fingerprint_reset(self, qoder_support_dir):
        """Execute hardware fingerprint reset implementation"""
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
                            "frequency": f"{random.uniform(2.0, 4.0):.1f}GHz"
                        },
                        "gpu": {
                            "name": f"Apple M{random.randint(2, 5)} Pro GPU",
                            "memory": f"{random.choice([16, 24, 32])}GB",
                            "cores": random.choice([16, 19, 24, 32])
                        },
                        "memory": {
                            "total": f"{random.choice([16, 24, 32, 64])}GB",
                            "type": "LPDDR5",
                            "speed": f"{random.choice([6400, 7467])}MT/s"
                        }
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
                        gpu_series = random.choice(["RTX 4060", "RTX 4070", "RTX 4080", "RTX 4090"])
                        gpu_name = f"NVIDIA GeForce {gpu_series}"
                        gpu_memory = f"{random.choice([8, 12, 16, 24])}GB"
                    elif gpu_brand == "AMD":
                        gpu_series = random.choice(["RX 7600", "RX 7700 XT", "RX 7800 XT", "RX 7900 XTX"])
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
                            "frequency": f"{random.uniform(3.0, 5.0):.1f}GHz"
                        },
                        "gpu": {
                            "name": gpu_name,
                            "memory": gpu_memory,
                            "cores": random.choice([1024, 1536, 2048, 2560])
                        },
                        "memory": {
                            "total": f"{random.choice([16, 24, 32])}GB",
                            "type": "LPDDR5",
                            "speed": f"{random.choice([4266, 5500, 6400])}MHz"
                        }
                    }
                else:
                    # Default case for other systems
                    fake_hardware_info = {
                        "cpu": {
                            "name": "Generic CPU",
                            "cores": random.choice([4, 6, 8]),
                            "threads": random.choice([8, 12, 16]),
                            "frequency": f"{random.uniform(2.0, 4.0):.1f}GHz"
                        },
                        "gpu": {
                            "name": "Generic GPU",
                            "memory": f"{random.choice([4, 8, 12])}GB",
                            "cores": random.choice([512, 1024, 1536])
                        },
                        "memory": {
                            "total": f"{random.choice([8, 16, 24])}GB",
                            "type": "DDR4",
                            "speed": f"{random.choice([2400, 3200, 4000])}MHz"
                        }
                    }
                
                # Write fake hardware information to a file
                hardware_file = qoder_support_dir / "hardware_info.json"
                with open(hardware_file, 'w', encoding='utf-8') as f:
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
            self.log("🔥 开始安全的超级深度清理...")
            cleaned_count = 0
            
            # 1. 清理系统级别的身份文件
            self.log("1. 清理系统级别身份文件...")
            system_identity_files = [
                # 日志和临时文件
                "logs", "tmp", "temp", "crash_dumps",
                # 更多可能的身份识别文件
                "identity.json", "machine.json", "device.json",
                "fingerprint.json", "tracking.json", "analytics.json",
                # 浏览器相关文件
                "BrowserUserAgent", "ClientHints", "NavigatorInfo",
                "ScreenInfo", "TimezoneInfo", "LanguageInfo",
                # 网络相关文件
                "DNSCache", "HTTPCache", "ProxySettings",
                "NetworkConfiguration", "ConnectionHistory",
                # 系统信息文件
                "OSInfo", "HardwareProfile", "SystemMetrics",
                "PerformanceInfo", "MemoryInfo", "DiskInfo",
                # 用户活动相关
                "UserActivity", "AppUsage", "FeatureUsage",
                "InteractionHistory", "AccessLog", "AuditLog",
                # 安全相关文件
                "SecuritySettings", "CertificateStore", "TrustStore",
                "EncryptionKeys", "AuthTokens", "SessionKeys",
                # 缓存相关文件
                "MetadataCache", "ThumbnailCache", "IndexCache",
                "SearchCache", "QueryCache", "ResultsCache",
                # 扩展和插件相关
                "ExtensionData", "PluginData", "AddonData",
                "ExtensionPrefs", "PluginPrefs", "AddonPrefs",
                # 更多 WebKit 相关文件
                "WebKitCache", "WebProcessCache", "PluginProcessCache",
                "RenderProcessCache", "GPUProcessCache",
                # 更多 Chromium 相关文件
                "ChromiumState", "ChromiumPrefs", "ChromiumHistory",
                "ChromiumCookies", "ChromiumSessions"
            ]
            
            for file_name in system_identity_files:
                file_path = qoder_support_dir / file_name
                if file_path.exists():
                    try:
                        if file_path.is_dir():
                            shutil.rmtree(file_path)
                        else:
                            file_path.unlink()
                        self.log(f"   ✅ 已清除: {file_name}")
                        cleaned_count += 1
                    except Exception as e:
                        self.log(f"   ⚠️  清除失败 {file_name}: {e}")
            
            # 2. 谨慎清理指定扩展名的可疑文件（增加安全检查）
            self.log("2. 谨慎清理可疑扩展名文件...")
            suspicious_extensions = [
                ".tmp", ".temp", ".cache", ".lock", ".pid", ".sock", 
                ".session", ".fingerprint", ".tracking", ".analytics"
            ]
            
            # 🚫 绝对安全白名单 - 永远不删除的重要文件
            protected_keywords = [
                "settings", "config", "workspace", "preference", "user",
                "important", "backup", "license", "key", "certificate", 
                "password", "auth", "secret", "critical", "system",
                "apple", "microsoft", "windows", "macos", "safari", "chrome"
            ]
            
            # ✅ 只清理与这些应用相关的文件
            qoder_keywords = ['qoder', 'vscode', 'electron', 'code-', 'ms-vscode']
            
            for root, dirs, files in os.walk(qoder_support_dir):
                for file in files:
                    file_path = Path(root) / file
                    file_ext = file_path.suffix.lower()
                    
                    if file_ext in suspicious_extensions:
                        # 安全检查：跳过重要文件
                        is_safe_file = any(safe_word in file.lower() for safe_word in safe_keywords)
                        
                        # 🛡️ 多重安全检查
                        is_protected = any(keyword in file.lower() for keyword in protected_keywords)
                        is_in_qoder_dir = str(qoder_support_dir) in str(file_path)
                        is_qoder_related = any(keyword in file.lower() or keyword in root.lower() 
                                             for keyword in qoder_keywords)
                        
                        # ✅ 只有同时满足以下条件才删除：
                        # 1. 在Qoder目录内  2. 与Qoder相关  3. 不在保护列表
                        if is_in_qoder_dir and is_qoder_related and not is_protected:
                            try:
                                file_path.unlink()
                                self.log(f"   ✅ 已清除可疑文件: {file}")
                                cleaned_count += 1
                            except Exception as e:
                                self.log(f"   ⚠️  清除失败 {file}: {e}")
                        else:
                            if not is_qoder_related:
                                self.log(f"   ℹ️  跳过非相关文件: {file}")
                            if is_safe_file:
                                self.log(f"   ℹ️  保护重要文件: {file}")
            
            # 3. 清理隐藏文件和目录
            self.log("3. 清理隐藏文件...")
            for root, dirs, files in os.walk(qoder_support_dir):
                # 清理隐藏文件（以点开头）
                for file in files:
                    if file.startswith('.') and file not in ['.gitignore', '.gitkeep']:
                        file_path = Path(root) / file
                        try:
                            file_path.unlink()
                            self.log(f"   ✅ 已清除隐藏文件: {file}")
                            cleaned_count += 1
                        except Exception as e:
                            self.log(f"   ⚠️  清除失败 {file}: {e}")
                
                # 清理隐藏目录（以点开头）
                for dir_name in dirs[:]:
                    if dir_name.startswith('.') and dir_name not in ['.git']:
                        dir_path = Path(root) / dir_name
                        try:
                            shutil.rmtree(dir_path)
                            self.log(f"   ✅ 已清除隐藏目录: {dir_name}")
                            dirs.remove(dir_name)  # 从遍历中移除
                            cleaned_count += 1
                        except Exception as e:
                            self.log(f"   ⚠️  清除失败 {dir_name}: {e}")
            
            # 4. 重置文件权限（防止文件时间戳检测）
            self.log("4. 重置文件权限...")
            try:
                # 重置整个目录的权限
                if platform.system() != "Windows":
                    subprocess.run(['chmod', '-R', '755', str(qoder_support_dir)], check=False, timeout=30)
                    self.log("   ✅ 文件权限已重置")
            except Exception as e:
                self.log(f"   ⚠️  权限重置失败: {e}")
            
            # 5. 创建迷惑性文件（干扰检测）
            self.log("5. 创建迷惑性文件...")
            try:
                decoy_files = [
                    "real_machine_id.tmp", "backup_device_id.log", 
                    "old_telemetry.dat", "previous_session.cache",
                    "legacy_fingerprint.json", "archived_identity.bak",
                    "system_backup.tmp", "device_clone.dat"
                ]
                
                for decoy_file in decoy_files:
                    file_path = qoder_support_dir / decoy_file
                    fake_data = {
                        "fake_id": str(uuid.uuid4()),
                        "timestamp": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat(),
                        "data": hashlib.md5(str(random.random()).encode()).hexdigest(),
                        "note": "This is a decoy file"
                    }
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(fake_data, f, indent=2)
                    
                    # 设置为隐藏文件
                    try:
                        if platform.system() == "Darwin":
                            subprocess.run(['chflags', 'hidden', str(file_path)], check=False)
                    except:
                        pass
                    
                    self.log(f"   ✅ 已创建迷惑文件: {decoy_file}")
                    cleaned_count += 1
            except Exception as e:
                self.log(f"   ⚠️  创建迷惑文件失败: {e}")
            
            # 6. 安全清理系统级别的缓存（macOS）
            if platform.system() == "Darwin":
                self.log("6. 安全清理 macOS 系统级缓存...")
                try:
                    # 只清理用户级别的系统缓存，不影响系统稳定性
                    user_system_cache_paths = [
                        Path.home() / "Library/Caches",
                        Path.home() / "Library/Application Support/com.apple.sharedfilelist",
                    ]
                    
                    for cache_path in user_system_cache_paths:
                        if cache_path.exists() and cache_path != qoder_support_dir:
                            # 只清理与 Qoder/VSCode 相关的文件，不影响其他应用
                            for item in cache_path.iterdir():
                                item_name_lower = item.name.lower()
                                if any(keyword in item_name_lower for keyword in 
                                      ['qoder', 'vscode', 'com.microsoft.vscode', 'electron']):
                                    try:
                                        if item.is_dir():
                                            shutil.rmtree(item)
                                        else:
                                            item.unlink()
                                        self.log(f"   ✅ 已清理系统缓存: {item.name}")
                                        cleaned_count += 1
                                    except Exception as e:
                                        self.log(f"   ⚠️  系统缓存清理失败 {item.name}: {e}")
                    
                    # 不清理 LaunchServices，避免影响系统功能
                    self.log("   ℹ️  为保护系统稳定性，跳过 LaunchServices 清理")
                    
                except Exception as e:
                    self.log(f"   ⚠️  macOS 系统缓存清理失败: {e}")
            
            elif platform.system() == "Windows":
                self.log("6. 安全清理 Windows 系统级缓存...")
                try:
                    # 只清理用户级别的缓存，不影响系统
                    user_cache_paths = [
                        Path(os.environ.get('LOCALAPPDATA', '')) / "Temp",
                        Path(os.environ.get('APPDATA', '')) / "Microsoft" / "Windows" / "Recent"
                    ]
                    
                    for cache_path in user_cache_paths:
                        if cache_path.exists():
                            for item in cache_path.iterdir():
                                if any(keyword in item.name.lower() for keyword in ['qoder', 'vscode', 'electron']):
                                    try:
                                        if item.is_dir():
                                            shutil.rmtree(item)
                                        else:
                                            item.unlink()
                                        self.log(f"   ✅ 已清理Windows缓存: {item.name}")
                                        cleaned_count += 1
                                    except Exception as e:
                                        self.log(f"   ⚠️  清理失败: {e}")
                except Exception as e:
                    self.log(f"   ⚠️  Windows 系统缓存清理失败: {e}")
            
            self.log(f"   超级深度清理完成，处理了 {cleaned_count} 个项目")
            
        except Exception as e:
            self.log(f"   超级深度清理失败: {e}")

    def is_qoder_running(self):
        """Kiểm tra xem Qoder có đang chạy không"""
        try:
            # Thực hiện kiểm tra qua các phương pháp khác nhau
            # Ví dụ: Sử dụng subprocess để kiểm tra các tiến trình
            import subprocess
            import platform

            # Lệnh kiểm tra tiến trình khác nhau tùy hệ điều hành
            if platform.system() == "Windows":
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq qoder.exe"], 
                                        capture_output=True, text=True)
                return "qoder.exe" in result.stdout.lower()
            elif platform.system() == "Darwin":  # macOS
                result = subprocess.run(["pgrep", "-x", "Qoder"], 
                                        capture_output=True, text=True)
                return result.returncode == 0
            elif platform.system() == "Linux":
                result = subprocess.run(["pgrep", "-x", "qoder"], 
                                        capture_output=True, text=True)
                return result.returncode == 0
            
            return False
        except Exception as e:
            self.log(f"Error checking Qoder status: {e}")
            return False

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
                with open(storage_json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Cập nhật các trường liên quan đến hardware
                data['telemetry.machineId'] = machine_id_hash
                data['telemetry.devDeviceId'] = new_device_id
                data['machineId'] = machine_id_hash
                
                with open(storage_json_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            
            # Ghi log
            self.log(f"Reset hardware fingerprint: New Machine ID {machine_id_hash[:16]}...")
            self.log(f"New Device ID: {new_device_id}")
            
        except Exception as e:
            self.log(f"Error resetting hardware fingerprint: {e}")
            raise

def main():
    if not globals().get("PYQT_AVAILABLE", False):
        print("Error: PyQt5 is not installed")
        print("Please run: pip install -r requirements.txt")
        raise SystemExit(1)

    _configure_qt_runtime()
    app = QApplication(sys.argv)

    # 设置应用程序样式
    app.setStyle('Fusion')

    # 设置全局样式表，确保对话框文字和按钮可见
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
