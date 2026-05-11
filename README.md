# Qoder Reset Tool 🔒

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](https://github.com/VoDaiLocz/Qoder-Free/releases/tag/v1.1.0)
[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](https://github.com/locfaker/Qoder-Free)

A comprehensive privacy management application designed to help users reset and clean Qoder application data with enhanced security features. Built with PyQt5, this cross-platform tool provides powerful options to manage digital identity and privacy.

## ✨ Features

### 🚀 Core Functionality
- **One-Click Reset**: Quickly reset all Qoder application configurations
- **Machine ID Reset**: Generate new unique machine identifiers
- **Telemetry Data Cleanup**: Remove tracking and analytics data
- **Deep Identity Cleanup**: Comprehensive removal of identity-related files
- **Hardware Fingerprint Reset**: Advanced anti-detection capabilities

### 🌍 Multi-Language Support
- 🇺🇸 **English** - Full support
- 🇻🇳 **Vietnamese** - Tiếng Việt
- 🇨🇳 **Chinese** - 中文
- 🇷🇺 **Russian** - Русский

### 🖥️ Cross-Platform Compatibility
- **Windows** 10/11 (x64)
- **macOS** 10.14+ (Intel & Apple Silicon)
- **Linux** (Ubuntu 18.04+, Debian 10+, CentOS 7+)

### 🔐 Privacy & Security
- **Safe Data Handling**: Preserves essential user data while cleaning identity traces
- **Selective Cleanup**: Option to preserve chat history
- **Advanced Fingerprinting**: Hardware-level identity reset
- **Secure File Operations**: Safe deletion with verification

## 📋 System Requirements

### Minimum Requirements
- **Python**: 3.7 or higher
- **RAM**: 512 MB
- **Storage**: 100 MB free space
- **OS**: Windows 10, macOS 10.14, or Linux with GUI support

### Dependencies
- `PyQt5 >= 5.15.0` - GUI framework
- `requests >= 2.25.0` - HTTP library
- `pathlib` - Path manipulation (built-in for Python 3.4+)

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/locfaker/Qoder-Free.git
cd Qoder-Free
```

### 2. Install Dependencies
```bash
# Using pip
pip install -r requirements.txt

# Or using conda
conda install --file requirements.txt
```

### 3. Run the Application

#### Windows
```bash
# Double-click or run in terminal
start_gui.bat
```

#### macOS/Linux
```bash
# Make executable and run
chmod +x qoder_reset_gui.py
python qoder_reset_gui.py
```

## 📖 Usage Guide

### Basic Operations

1. **Launch the Application**
   - Run the appropriate startup script for your platform
   - Select your preferred language from the dropdown

2. **One-Click Reset** (Recommended)
   - Click "One-Click Configuration" for automatic reset
   - Choose whether to preserve chat history
   - Confirm the operation

3. **Advanced Operations**
   - **Close Qoder**: Safely terminate Qoder processes
   - **Reset Machine ID**: Generate new machine identifier
   - **Reset Telemetry**: Clear tracking data
   - **Deep Identity Clean**: Comprehensive privacy cleanup

### Safety Features

- **Process Detection**: Automatically detects running Qoder instances
- **Backup Preservation**: Option to keep important user data
- **Operation Logging**: Detailed logs of all operations
- **Rollback Support**: Safe operations with verification

## 🛠️ Development

### Project Structure
```
Qoder-Free/
├── qoder_reset_gui.py      # Main application file
├── requirements.txt        # Python dependencies
├── start_gui.bat          # Windows launcher
├── LICENSE                # MIT License
├── README.md              # This file
└── .gitignore            # Git ignore rules
```

### Building from Source

1. **Clone and Setup**
   ```bash
   git clone https://github.com/locfaker/Qoder-Free.git
   cd Qoder-Free
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run in Development Mode**
   ```bash
   python qoder_reset_gui.py
   ```

3. **Create Executable** (Optional)
   ```bash
   pip install pyinstaller
   pyinstaller --onefile --windowed --collect-all PyQt5 qoder_reset_gui.py
   ```

## 🤝 Contributing

We welcome contributions! Please follow these steps:

### Quick Contribution Steps
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed
- Ensure cross-platform compatibility

## 🐛 Troubleshooting

### Common Issues

**Issue**: "PyQt5 not found"
```bash
# Solution
pip install --upgrade PyQt5
```

**Issue**: "No Qt platform plugin could be initialized"
- **Run from source (recommended for debugging):** start with `python qoder_reset_gui.py` (Windows: set `QODER_CONSOLE=1` before running `start_gui.bat`).
- **Reset broken Qt env vars:** set `QODER_QT_RESET_ENV=1` and retry.
- **Headless Linux:** set `QODER_QT_QPA_PLATFORM=offscreen`.
- **Get detailed logs:** set `QT_DEBUG_PLUGINS=1` (Windows: set `QODER_DEBUG=1` before running `start_gui.bat`).
- **Linux missing system libs:** install `libxkbcommon-x11-0` and the common `libxcb-*` packages (see `.github/workflows/ci.yml` for the exact list used in CI).

**Issue**: "Permission denied"
```bash
# On macOS/Linux
chmod +x qoder_reset_gui.py
sudo python qoder_reset_gui.py
```

**Issue**: "Qoder not detected"
- Ensure Qoder is properly installed
- Check if Qoder is running in the background
- Verify application data directory exists

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🚨 Disclaimer

This tool is designed for privacy enhancement and educational purposes. Users are responsible for:
- Complying with all applicable terms of service
- Using the tool responsibly and ethically
- Understanding the implications of data reset operations

**Use at your own risk. Always backup important data before using this tool.**

## 📧 Support

- **Issues**: [GitHub Issues](https://github.com/locfaker/Qoder-Free/issues)
- **Discussions**: [GitHub Discussions](https://github.com/locfaker/Qoder-Free/discussions)
- **Email**: Contact the maintainer through GitHub

## 🌟 Acknowledgments

- Built with [PyQt5](https://pypi.org/project/PyQt5/)
- Inspired by privacy-focused development practices
- Thanks to all contributors and users

---

**Privacy Matters** 🛡️ | **Made with ❤️ for the community**
