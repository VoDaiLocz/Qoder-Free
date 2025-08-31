# Contributing to Qoder Reset Tool

Thank you for your interest in contributing to Qoder Reset Tool! We welcome contributions from the community and are pleased to have you join us.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Community](#community)

## 🤝 Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

### Our Standards

- **Be respectful**: Treat everyone with respect and kindness
- **Be inclusive**: Welcome newcomers and help them get started
- **Be collaborative**: Work together towards common goals
- **Be constructive**: Provide helpful feedback and suggestions

## 🚀 Getting Started

### Prerequisites

- Python 3.7 or higher
- Git
- Basic knowledge of PyQt5 and Python development
- Familiarity with privacy and security concepts

### First Contribution

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/Qoder-Free.git
   cd Qoder-Free
   ```
3. **Create a branch** for your contribution:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## 🛠️ Development Setup

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install pytest pytest-qt black flake8 mypy
```

### 2. Running the Application

```bash
# Run the main application
python qoder_reset_gui.py

# Run with debug mode (if implemented)
python qoder_reset_gui.py --debug
```

### 3. Project Structure

```
Qoder-Free/
├── qoder_reset_gui.py      # Main application file
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies (if created)
├── tests/                  # Test files (if created)
├── docs/                   # Documentation (if created)
├── .github/                # GitHub workflows and templates
├── LICENSE                 # MIT License
├── README.md               # Project documentation
├── CHANGELOG.md            # Version history
├── CONTRIBUTING.md         # This file
└── .gitignore             # Git ignore rules
```

## 🎯 How to Contribute

### Types of Contributions

We welcome several types of contributions:

#### 🐛 Bug Reports
- Use the GitHub issue tracker
- Include detailed steps to reproduce
- Provide system information (OS, Python version, etc.)
- Include error messages and logs

#### ✨ Feature Requests
- Check existing issues first
- Clearly describe the feature and its benefits
- Consider implementation complexity
- Discuss with maintainers before starting work

#### 🔧 Code Contributions
- Bug fixes
- New features
- Performance improvements
- Code refactoring
- Documentation improvements

#### 🌍 Translations
- Add new language support
- Improve existing translations
- Update translation files

#### 📚 Documentation
- Improve README
- Add code comments
- Create tutorials
- Update API documentation

### Issue Guidelines

When creating an issue, please:

1. **Search existing issues** first
2. **Use clear, descriptive titles**
3. **Provide detailed descriptions**
4. **Include relevant labels**
5. **Add screenshots** if applicable

### Feature Request Template

```markdown
**Feature Description**
A clear description of the feature you'd like to see.

**Use Case**
Explain why this feature would be useful.

**Proposed Implementation**
If you have ideas about how to implement this feature.

**Additional Context**
Any other context or screenshots about the feature request.
```

### Bug Report Template

```markdown
**Bug Description**
A clear description of what the bug is.

**Steps to Reproduce**
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g. Windows 10, macOS 12.0, Ubuntu 20.04]
- Python Version: [e.g. 3.9.7]
- PyQt5 Version: [e.g. 5.15.7]
- Application Version: [e.g. 1.0.0]

**Additional Context**
Add any other context about the problem here.
```

## 🔄 Pull Request Process

### Before Submitting

1. **Test your changes** thoroughly
2. **Update documentation** if needed
3. **Add tests** for new features
4. **Follow coding standards**
5. **Update CHANGELOG.md**

### Pull Request Steps

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. **Make your changes** with clear, logical commits:
   ```bash
   git add .
   git commit -m "Add amazing feature: detailed description"
   ```

3. **Push to your fork**:
   ```bash
   git push origin feature/amazing-feature
   ```

4. **Create a Pull Request** on GitHub

### Pull Request Template

```markdown
## Description
Brief description of changes made.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] I have tested these changes locally
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes

## Checklist
- [ ] My code follows the project's coding standards
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have updated the CHANGELOG.md file
```

## 📝 Coding Standards

### Python Style Guide

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some modifications:

- **Line Length**: 88 characters (Black formatter default)
- **Indentation**: 4 spaces
- **Quotes**: Double quotes for strings
- **Imports**: Organized and grouped

### Code Formatting

We use [Black](https://black.readthedocs.io/) for code formatting:

```bash
# Format all Python files
black .

# Check formatting without making changes
black --check .
```

### Linting

We use [flake8](https://flake8.pycqa.org/) for linting:

```bash
# Run linter
flake8 .
```

### Type Hints

We encourage the use of type hints:

```python
def reset_machine_id(self, preserve_data: bool = True) -> bool:
    """Reset machine ID with optional data preservation."""
    pass
```

## 🧪 Testing Guidelines

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=qoder_reset_gui

# Run specific test file
pytest tests/test_gui.py
```

### Writing Tests

- Write tests for new features
- Maintain or improve test coverage
- Use descriptive test names
- Include both positive and negative test cases

### Test Structure

```python
import pytest
from PyQt5.QtWidgets import QApplication
from qoder_reset_gui import QoderResetGUI

class TestQoderResetGUI:
    def test_initialization(self, qtbot):
        """Test GUI initialization."""
        app = QoderResetGUI()
        qtbot.addWidget(app)
        assert app.current_language == 'en'
    
    def test_language_change(self, qtbot):
        """Test language switching functionality."""
        app = QoderResetGUI()
        qtbot.addWidget(app)
        app.change_language('Vietnamese')
        assert app.current_language == 'vi'
```

## 📖 Documentation

### Code Documentation

- Use clear, descriptive docstrings
- Document complex algorithms
- Include type hints
- Add inline comments for tricky code

### Documentation Style

```python
def perform_reset(self, reset_type: str, preserve_chat: bool = True) -> bool:
    """
    Perform application reset operation.
    
    Args:
        reset_type: Type of reset to perform ('machine_id', 'telemetry', 'deep')
        preserve_chat: Whether to preserve chat history
        
    Returns:
        bool: True if reset was successful, False otherwise
        
    Raises:
        ResetError: If reset operation fails
        PermissionError: If insufficient permissions
    """
    pass
```

## 🌟 Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and community discussions
- **Pull Requests**: Code review and collaboration

### Getting Help

- Check existing documentation first
- Search closed issues for similar problems
- Ask questions in GitHub Discussions
- Be patient and respectful when asking for help

### Recognition

Contributors will be recognized in:
- README.md contributors section
- CHANGELOG.md for significant contributions
- GitHub contributors page

## 📄 License

By contributing to Qoder Reset Tool, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to Qoder Reset Tool! Your efforts help make this project better for everyone. 🎉