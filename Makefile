# Prompter Makefile
# Background process management for the Prompter application

.PHONY: help install setup start stop restart status logs clean dev test lint format check-deps

PYTHON := python3
VENV_DIR := .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
PID_FILE := .prompter.pid
LOG_FILE := prompter.log
ERROR_LOG := prompter-error.log

help: ## Show this help message
	@echo "Prompter - Background Service Management"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Process Management:"
	@echo "  make start     - Start service in background"
	@echo "  make stop      - Stop background service"
	@echo "  make restart   - Restart background service"
	@echo "  make status    - Check service status"
	@echo "  make logs      - Show service logs"

install: setup ## Install dependencies and setup virtual environment

setup: ## Setup virtual environment and install dependencies
	@echo "Setting up Prompter..."
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		echo "Checking macOS prerequisites..."; \
		if ! command -v brew >/dev/null 2>&1; then \
			echo "❌ Homebrew is required on macOS. Please install it first: https://brew.sh/"; \
			exit 1; \
		fi; \
		if ! brew list portaudio >/dev/null 2>&1; then \
			echo "⚠️  portaudio is required for speech-to-text functionality."; \
			echo "Installing portaudio via Homebrew..."; \
			brew install portaudio; \
		fi; \
	elif [ "$$(uname -s)" = "Linux" ]; then \
		echo "Checking Linux prerequisites..."; \
		if ! dpkg -l | grep -q portaudio19-dev; then \
			echo "⚠️  portaudio19-dev is required for speech-to-text functionality."; \
			echo "Please install it with: sudo apt install portaudio19-dev"; \
			echo "Note: You may need to run this command manually with sudo privileges."; \
		fi; \
	fi
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	@echo "Installing dependencies..."
	@$(VENV_PIP) install --upgrade pip
	@$(VENV_PIP) install -r requirements.txt
	@if [ ! -f ".env" ]; then \
		echo "Creating .env file..."; \
		echo "OPENAI_API_KEY=your_api_key_here" > .env; \
		echo "⚠️  Please edit .env with your actual configuration"; \
	fi
	@if [ ! -d "settings" ]; then \
		echo "Creating settings directory..."; \
		cp -r settings_example settings; \
		echo "✅ Settings directory created from settings_example"; \
	fi
	@echo "✅ Setup complete!"

start: ## Start the service in background
	@if [ -f "$(PID_FILE)" ] && kill -0 `cat $(PID_FILE)` 2>/dev/null; then \
		echo "❌ Service is already running (PID: `cat $(PID_FILE)`)"; \
		exit 1; \
	fi
	@echo "🚀 Starting Prompter in background..."
	@nohup $(VENV_PYTHON) main.py > $(LOG_FILE) 2> $(ERROR_LOG) & echo $$! > $(PID_FILE)
	@sleep 2
	@if [ -f "$(PID_FILE)" ] && kill -0 `cat $(PID_FILE)` 2>/dev/null; then \
		echo "✅ Service started successfully (PID: `cat $(PID_FILE)`)"; \
		echo "📋 Use 'make logs' to view output"; \
		echo "🔧 Use 'make status' to check status"; \
	else \
		echo "❌ Failed to start service"; \
		if [ -f "$(ERROR_LOG)" ]; then \
			echo "Error log:"; \
			tail -10 $(ERROR_LOG); \
		fi; \
		exit 1; \
	fi

stop: ## Stop the background service
	@if [ ! -f "$(PID_FILE)" ]; then \
		echo "❌ PID file not found. Service may not be running."; \
		exit 1; \
	fi
	@PID=`cat $(PID_FILE)`; \
	if kill -0 $$PID 2>/dev/null; then \
		echo "🛑 Stopping service (PID: $$PID)..."; \
		kill $$PID; \
		sleep 2; \
		if kill -0 $$PID 2>/dev/null; then \
			echo "⚠️  Process still running, forcing termination..."; \
			kill -9 $$PID; \
		fi; \
		rm -f $(PID_FILE); \
		echo "✅ Service stopped"; \
	else \
		echo "❌ Process not running"; \
		rm -f $(PID_FILE); \
	fi

restart: stop start ## Restart the background service

status: ## Check service status
	@echo "📊 Prompter Service Status"
	@echo "=============================="
	@if [ -f "$(PID_FILE)" ]; then \
		PID=`cat $(PID_FILE)`; \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Status: ✅ Running"; \
			echo "PID: $$PID"; \
			echo "Uptime: $$(ps -o etime= -p $$PID | tr -d ' ')"; \
			echo "Memory: $$(ps -o rss= -p $$PID | tr -d ' ') KB"; \
		else \
			echo "Status: ❌ Not running (stale PID file)"; \
			rm -f $(PID_FILE); \
		fi; \
	else \
		echo "Status: ❌ Not running"; \
	fi
	@echo ""
	@if [ -f "$(LOG_FILE)" ]; then \
		echo "Log file: $(LOG_FILE) ($$(wc -l < $(LOG_FILE)) lines)"; \
	fi
	@if [ -f "$(ERROR_LOG)" ]; then \
		echo "Error log: $(ERROR_LOG) ($$(wc -l < $(ERROR_LOG)) lines)"; \
	fi

logs: ## Show service logs
	@echo "📋 Service Logs (last 50 lines)"
	@echo "==============================="
	@if [ -f "$(LOG_FILE)" ]; then \
		tail -50 $(LOG_FILE); \
	else \
		echo "No log file found"; \
	fi
	@echo ""
	@echo "🚨 Error Logs (last 20 lines)"
	@echo "============================="
	@if [ -f "$(ERROR_LOG)" ]; then \
		tail -20 $(ERROR_LOG); \
	else \
		echo "No error log found"; \
	fi

logs-follow: ## Follow service logs in real-time
	@echo "📋 Following service logs (Ctrl+C to stop)..."
	@if [ -f "$(LOG_FILE)" ]; then \
		tail -f $(LOG_FILE); \
	else \
		echo "No log file found. Start the service first."; \
	fi


clean: ## Clean up generated files
	@echo "🧹 Cleaning up..."
	@rm -f $(PID_FILE) $(LOG_FILE) $(ERROR_LOG)
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"

clean-all: clean ## Clean everything including virtual environment
	@echo "🧹 Deep cleaning..."
	@rm -rf $(VENV_DIR)
	@echo "✅ Deep cleanup complete"

autostart-macos: ## Setup macOS LaunchAgent for autostart
	@echo "🍎 Setting up macOS autostart..."
	@mkdir -p ~/Library/LaunchAgents
	@echo '<?xml version="1.0" encoding="UTF-8"?>' > ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '<plist version="1.0">' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '<dict>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <key>Label</key>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <string>com.prompter.service</string>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <key>ProgramArguments</key>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <array>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '        <string>$(PWD)/$(VENV_PYTHON)</string>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '        <string>$(PWD)/main.py</string>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    </array>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <key>WorkingDirectory</key>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <string>$(PWD)</string>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <key>RunAtLoad</key>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <true/>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <key>KeepAlive</key>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <true/>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <key>StandardOutPath</key>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <string>$(PWD)/prompter-daemon.log</string>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <key>StandardErrorPath</key>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '    <string>$(PWD)/prompter-daemon-error.log</string>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '</dict>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo '</plist>' >> ~/Library/LaunchAgents/com.prompter.service.plist
	@echo "✅ LaunchAgent created"
	@echo "To enable: launchctl load ~/Library/LaunchAgents/com.prompter.service.plist"
	@echo "To disable: launchctl unload ~/Library/LaunchAgents/com.prompter.service.plist"

autostart-linux: ## Setup Linux systemd service for autostart
	@echo "🐧 Setting up Linux systemd service..."
	@mkdir -p ~/.config/systemd/user
	@echo '[Unit]' > ~/.config/systemd/user/prompter.service
	@echo 'Description=Prompter Background Service' >> ~/.config/systemd/user/prompter.service
	@echo 'After=graphical-session.target' >> ~/.config/systemd/user/prompter.service
	@echo '' >> ~/.config/systemd/user/prompter.service
	@echo '[Service]' >> ~/.config/systemd/user/prompter.service
	@echo 'Type=simple' >> ~/.config/systemd/user/prompter.service
	@echo 'ExecStart=$(PWD)/$(VENV_PYTHON) $(PWD)/main.py' >> ~/.config/systemd/user/prompter.service
	@echo 'WorkingDirectory=$(PWD)' >> ~/.config/systemd/user/prompter.service
	@echo 'Restart=always' >> ~/.config/systemd/user/prompter.service
	@echo 'RestartSec=5' >> ~/.config/systemd/user/prompter.service
	@echo 'Environment=DISPLAY=:0' >> ~/.config/systemd/user/prompter.service
	@echo '' >> ~/.config/systemd/user/prompter.service
	@echo '[Install]' >> ~/.config/systemd/user/prompter.service
	@echo 'WantedBy=default.target' >> ~/.config/systemd/user/prompter.service
	@systemctl --user daemon-reload
	@echo "✅ Systemd service created"
	@echo "To enable: systemctl --user enable prompter.service"
	@echo "To start: systemctl --user start prompter.service"
	@echo "To check status: systemctl --user status prompter.service"

info: ## Show system information
	@echo "ℹ️  System Information"
	@echo "===================="
	@echo "OS: $$(uname -s)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Virtual env: $(VENV_DIR)"
	@echo "Working dir: $(PWD)"
	@echo "PID file: $(PID_FILE)"
	@echo "Log file: $(LOG_FILE)"
	@echo "Error log: $(ERROR_LOG)"

# Default target
all: help
