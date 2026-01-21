# Promptheus Makefile
# Background process management for the Promptheus application

.PHONY: help install setup start stop restart status logs logs-follow logs-debug start-debug debug clean clean-all autostart-macos autostart-linux info test test-cov lint lint-fix

PYTHON := python3
VENV_DIR := .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
PID_FILE := .promptheus.pid
LOG_FILE := promptheus.log
ERROR_LOG := promptheus-error.log
DEBUG_LOG := promptheus-debug.log

help: ## Show this help message
	@echo "Promptheus - Background Service Management"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Process Management:"
	@echo "  make start       - Start service in background"
	@echo "  make stop        - Stop background service"
	@echo "  make restart     - Restart background service"
	@echo "  make status      - Check service status"
	@echo "  make logs        - Show service logs"
	@echo ""
	@echo "Debug Mode:"
	@echo "  make debug       - Run in foreground with debug logging"
	@echo "  make start-debug - Start in background with debug logging"
	@echo "  make logs-debug  - Show debug logs"

install: setup ## Install dependencies and setup virtual environment

setup: ## Setup virtual environment and install dependencies
	@echo "Setting up Promptheus..."
	@echo "Setting up dependencies..."
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	@echo "Installing dependencies..."
	@$(VENV_PIP) install --upgrade pip
	@if [ "$$(uname)" = "Darwin" ]; then \
		echo "Detected macOS - installing with macOS extras..."; \
		$(VENV_PIP) install -e ".[macos]"; \
	elif [ "$$(uname)" = "Linux" ]; then \
		echo "Detected Linux - installing with Linux extras..."; \
		$(VENV_PIP) install -e ".[linux]"; \
		which apt > /dev/null 2>&1 && dpkg -l libxcb-cursor0 > /dev/null 2>&1 || echo "⚠️  Ubuntu/Debian: run 'sudo apt install libxcb-cursor0'"; \
	else \
		echo "Detected Windows - installing base dependencies..."; \
		$(VENV_PIP) install -e .; \
	fi
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
	@echo "🚀 Starting Promptheus in background..."
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
	@echo "📊 Promptheus Service Status"
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

start-debug: ## Start the service in debug mode (background)
	@if [ -f "$(PID_FILE)" ] && kill -0 `cat $(PID_FILE)` 2>/dev/null; then \
		echo "❌ Service is already running (PID: `cat $(PID_FILE)`)"; \
		exit 1; \
	fi
	@echo "🚀 Starting Promptheus in DEBUG mode..."
	@nohup $(VENV_PYTHON) main.py --debug > $(LOG_FILE) 2> $(ERROR_LOG) & echo $$! > $(PID_FILE)
	@sleep 2
	@if [ -f "$(PID_FILE)" ] && kill -0 `cat $(PID_FILE)` 2>/dev/null; then \
		echo "✅ Service started in DEBUG mode (PID: `cat $(PID_FILE)`)"; \
		echo "📋 Debug logs: $(DEBUG_LOG)"; \
		echo "📋 Use 'make logs-debug' to view debug output"; \
	else \
		echo "❌ Failed to start service"; \
		if [ -f "$(ERROR_LOG)" ]; then \
			echo "Error log:"; \
			tail -10 $(ERROR_LOG); \
		fi; \
		exit 1; \
	fi

debug: ## Run in foreground with debug logging (Ctrl+C to stop)
	@echo "🔍 Starting Promptheus in DEBUG mode (foreground)..."
	@echo "📋 Debug logs will be saved to: $(DEBUG_LOG)"
	@echo "Press Ctrl+C to stop"
	@echo ""
	@$(VENV_PYTHON) main.py --debug

logs-debug: ## Show debug logs
	@echo "🔍 Debug Logs (last 100 lines)"
	@echo "=============================="
	@if [ -f "$(DEBUG_LOG)" ]; then \
		tail -100 $(DEBUG_LOG); \
	else \
		echo "No debug log file found. Run 'make debug' or 'make start-debug' first."; \
	fi

clean: ## Clean up generated files
	@echo "🧹 Cleaning up..."
	@rm -f $(PID_FILE) $(LOG_FILE) $(ERROR_LOG) $(DEBUG_LOG)
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
	@echo '<?xml version="1.0" encoding="UTF-8"?>' > ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '<plist version="1.0">' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '<dict>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <key>Label</key>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <string>com.promptheus.service</string>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <key>ProgramArguments</key>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <array>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '        <string>$(PWD)/$(VENV_PYTHON)</string>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '        <string>$(PWD)/main.py</string>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    </array>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <key>WorkingDirectory</key>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <string>$(PWD)</string>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <key>RunAtLoad</key>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <true/>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <key>KeepAlive</key>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <true/>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <key>StandardOutPath</key>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <string>$(PWD)/promptheus-daemon.log</string>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <key>StandardErrorPath</key>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '    <string>$(PWD)/promptheus-daemon-error.log</string>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '</dict>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo '</plist>' >> ~/Library/LaunchAgents/com.promptheus.service.plist
	@echo "✅ LaunchAgent created"
	@echo "To enable: launchctl load ~/Library/LaunchAgents/com.promptheus.service.plist"
	@echo "To disable: launchctl unload ~/Library/LaunchAgents/com.promptheus.service.plist"

autostart-linux: ## Setup Linux systemd service for autostart
	@echo "🐧 Setting up Linux systemd service..."
	@mkdir -p ~/.config/systemd/user
	@echo '[Unit]' > ~/.config/systemd/user/promptheus.service
	@echo 'Description=Promptheus Background Service' >> ~/.config/systemd/user/promptheus.service
	@echo 'After=graphical-session.target' >> ~/.config/systemd/user/promptheus.service
	@echo 'PartOf=graphical-session.target' >> ~/.config/systemd/user/promptheus.service
	@echo '' >> ~/.config/systemd/user/promptheus.service
	@echo '[Service]' >> ~/.config/systemd/user/promptheus.service
	@echo 'Type=simple' >> ~/.config/systemd/user/promptheus.service
	@echo 'ExecStart=$(PWD)/$(VENV_PYTHON) $(PWD)/main.py' >> ~/.config/systemd/user/promptheus.service
	@echo 'WorkingDirectory=$(PWD)' >> ~/.config/systemd/user/promptheus.service
	@echo 'Restart=always' >> ~/.config/systemd/user/promptheus.service
	@echo 'RestartSec=5' >> ~/.config/systemd/user/promptheus.service
	@echo 'Environment=DISPLAY=$(DISPLAY)' >> ~/.config/systemd/user/promptheus.service
	@echo 'Environment=XAUTHORITY=$(XAUTHORITY)' >> ~/.config/systemd/user/promptheus.service
	@echo 'Environment=XDG_RUNTIME_DIR=$(XDG_RUNTIME_DIR)' >> ~/.config/systemd/user/promptheus.service
	@echo '' >> ~/.config/systemd/user/promptheus.service
	@echo '[Install]' >> ~/.config/systemd/user/promptheus.service
	@echo 'WantedBy=graphical-session.target' >> ~/.config/systemd/user/promptheus.service
	@systemctl --user daemon-reload
	@echo "✅ Systemd service created"
	@echo "To enable: systemctl --user enable promptheus.service"
	@echo "To start: systemctl --user start promptheus.service"
	@echo "To check status: systemctl --user status promptheus.service"

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

test: ## Run tests with pytest
	@$(VENV_PYTHON) -m pytest

test-cov: ## Run tests with coverage report
	@$(VENV_PYTHON) -m pytest --cov --cov-report=term-missing --cov-report=html
	@echo "✅ Coverage report generated in htmlcov/"

lint: ## Check code with ruff
	@$(VENV_PYTHON) -m ruff check .
	@$(VENV_PYTHON) -m ruff format --check .

lint-fix: ## Fix code issues with ruff
	@$(VENV_PYTHON) -m ruff check --fix .
	@$(VENV_PYTHON) -m ruff format .
	@echo "✅ Code formatted"

# Default target
all: help
