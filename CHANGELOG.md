# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release preparation
- Professional documentation
- GitHub Actions workflow

## [1.0.0] - 2024-08-31

### Added
- **Core Features**
  - One-click reset functionality for Qoder application data
  - Machine ID reset with UUID generation
  - Telemetry data cleanup and privacy protection
  - Deep identity cleanup with comprehensive file removal
  - Hardware fingerprint reset for advanced anti-detection

- **Multi-Language Support**
  - English (en) - Full support
  - Vietnamese (vi) - Tiếng Việt
  - Chinese (zh) - 中文
  - Russian (ru) - Русский
  - Portuguese Brazilian (pt-br) - Português

- **Cross-Platform Compatibility**
  - Windows 10/11 support with process detection
  - macOS support (Intel & Apple Silicon)
  - Linux support with GUI compatibility

- **User Interface**
  - Modern PyQt5-based GUI with professional styling
  - Intuitive button layout with color-coded operations
  - Real-time operation logging with timestamps
  - Language selector with instant UI updates
  - Preserve chat history option

- **Safety Features**
  - Automatic Qoder process detection
  - Confirmation dialogs for destructive operations
  - Selective cleanup options
  - Operation status reporting
  - Error handling and logging

- **Advanced Privacy Tools**
  - System-level cache cleanup
  - Identity file removal (cookies, sessions, certificates)
  - Hardware information spoofing
  - Decoy file creation for detection interference
  - Secure file deletion with verification

- **Developer Features**
  - Comprehensive logging system
  - Cross-platform path handling
  - Modular code structure
  - Exception handling throughout

### Technical Details
- **Dependencies**: PyQt5 5.15.7, requests 2.28.2, pathlib 1.0.1
- **Python Version**: 3.7+ required
- **Architecture**: Single-file application with embedded resources
- **File Operations**: Safe deletion with backup preservation options
- **Process Management**: Cross-platform process detection and termination

### Security
- **Privacy Protection**: No data collection or external communication
- **Safe Operations**: Verification before destructive actions
- **Backup Options**: Selective preservation of user data
- **Anti-Detection**: Advanced fingerprinting countermeasures

## [0.9.0] - 2024-08-30

### Added
- Initial development version
- Basic GUI framework
- Core reset functionality
- Multi-language foundation

### Changed
- Improved error handling
- Enhanced UI responsiveness
- Better cross-platform support

### Fixed
- Path resolution issues on different platforms
- Unicode handling in file operations
- Memory leaks in GUI components

## [0.1.0] - 2024-08-01

### Added
- Project initialization
- Basic concept and architecture
- Initial code structure

---

## Release Notes

### Version 1.0.0 Highlights
This is the first stable release of Qoder Reset Tool, featuring a complete privacy management solution for Qoder application users. The tool provides comprehensive identity reset capabilities while maintaining user data safety.

**Key Improvements:**
- Professional-grade GUI with multi-language support
- Advanced privacy protection features
- Cross-platform compatibility
- Comprehensive logging and error handling
- Safe operation modes with user confirmation

**Breaking Changes:**
- None (initial stable release)

**Migration Guide:**
- No migration needed for new installations
- For beta users: Please backup important data before upgrading

**Known Issues:**
- Some antivirus software may flag the executable (false positive)
- macOS users may need to allow the app in Security & Privacy settings
- Linux users require GUI libraries (usually pre-installed)

**Future Roadmap:**
- Plugin system for extended functionality
- Automated backup and restore features
- Advanced scheduling options
- Integration with other privacy tools

---

For more information about releases, visit our [GitHub Releases](https://github.com/locfaker/Qoder-Free/releases) page.