# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

```bash
# Setup and installation
make install          # Install dependencies and setup virtual environment
make setup             # Same as install

# Service management
make start             # Start service in background
make stop              # Stop background service  
make restart           # Restart background service
make status            # Check service status

# Monitoring and debugging
make logs              # Show service logs (last 50 lines)
make logs-follow       # Follow logs in real-time
make clean             # Clean up generated files (logs, PID files)
make clean-all         # Remove virtual environment entirely

# Platform-specific autostart
make autostart-macos   # Setup macOS LaunchAgent
make autostart-linux   # Setup Linux systemd service
```

## Architecture Overview

### Core Application Structure

**Main Entry Point**: `main.py` - Initializes the PromtheusApp and handles macOS dock hiding via LSUIElement

**Core Modules**:
- `app/application.py` - Main PySide6 application class (PromtheusApp)
- `core/` - Core business logic and interfaces
  - `services.py` - Service layer implementations
  - `models.py` - Data models and structures  
  - `openai_service.py` - OpenAI API integration
  - `context_manager.py` - Context data management
  - `placeholder_service.py` - Template variable handling
- `modules/` - Utility modules
  - `utils/` - System utilities (clipboard, notifications, keymap, config)
  - `speech/` - Speech-to-text functionality

### Configuration System

**Settings Location**: `settings/settings.json` (copied from `settings_example/` on first install)

**Key Configuration Sections**:
- `models` - AI model configurations with API keys, temperatures, base URLs
- `default_model` - Currently selected model
- `speech_to_text_model` - Dedicated STT model configuration  
- `keymaps` - OS-specific keyboard shortcuts with context matching
- `prompts` - Prompt definitions with template variables and external file references

**Template Variables**:
- `{{clipboard}}` - Current clipboard content
- `{{context}}` - Managed context data
- External prompt files via `"file": "prompts/filename.md"`

### Key Features

**Global Hotkeys**: Cross-platform keyboard shortcuts using pynput, with OS-specific context matching in keymaps

**Context Management**: Persistent context that can be set, appended to, or cleared across prompt executions

**Speech Integration**: OpenAI Whisper-based speech-to-text with two modes:
- Alternative input mode (hold Shift when selecting prompt)
- Standalone dictation tool

**Background Service**: Runs as daemon process with PID file management and comprehensive logging

## Code Style

**Do NOT use comments to explain what code does.** Code must be meaningful and self-explanatory. Use clear variable names, well-named functions, and logical structure instead of comments. If code needs a comment to be understood, refactor it to be clearer.

## Development Notes

- **GUI Framework**: PySide6-based system tray application
- **Cross-Platform**: macOS, Linux, Windows support with platform-specific integrations
- **API Integration**: OpenAI-compatible endpoints for both chat and transcription
- **Service Architecture**: Background daemon with proper process management
- **Template System**: Flexible prompt templating with variable substitution and file inclusion
- **Always use `uv`** for Python commands (e.g., `uv run python`, `uv pip install`, `uv run pytest`)

## Environment Setup

Requires `.env` file with API keys (created automatically on first install):
```
OPENAI_API_KEY=your_api_key_here
```

Virtual environment automatically created in `.venv/` directory.