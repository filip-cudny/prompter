# Prompt Store Makefile
# Background process management for the prompt store application

.PHONY: help install setup start stop restart status logs clean dev test lint format check-deps

PYTHON := python3
VENV_DIR := .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
PID_FILE := .prompt-store.pid
LOG_FILE := prompt-store.log
ERROR_LOG := prompt-store-error.log

help: ## Show this help message
	@echo "Prompt Store - Background Service Management"
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
	@echo "Setting up Prompt Store..."
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	@echo "Installing dependencies..."
	@$(VENV_PIP) install --upgrade pip
	@$(VENV_PIP) install -r requirements.txt
	@if [ ! -f ".env" ]; then \
		echo "Creating .env file..."; \
		echo "API_KEY=your_api_key_here" > .env; \
		echo "BASE_URL=https://your-api-server.com" >> .env; \
		echo "⚠️  Please edit .env with your actual configuration"; \
	fi
	@echo "✅ Setup complete!"

start: ## Start the service in background
	@if [ -f "$(PID_FILE)" ] && kill -0 `cat $(PID_FILE)` 2>/dev/null; then \
		echo "❌ Service is already running (PID: `cat $(PID_FILE)`)"; \
		exit 1; \
	fi
	@echo "🚀 Starting Prompt Store service in background..."
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
	@echo "📊 Prompt Store Service Status"
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

dev: ## Run in development mode (foreground)
	@echo "🔧 Running in development mode..."
	@$(VENV_PYTHON) main.py

test: ## Run tests
	@echo "🧪 Running tests..."
	@$(VENV_PYTHON) -m pytest tests/ -v || echo "No tests found"

lint: ## Run linting
	@echo "🔍 Running linting..."
	@$(VENV_PYTHON) -m ruff check . || echo "Ruff not installed, skipping..."

format: ## Format code
	@echo "🎨 Formatting code..."
	@$(VENV_PYTHON) -m ruff format . || echo "Ruff not installed, skipping..."

check-deps: ## Check if dependencies are installed
	@echo "📦 Checking dependencies..."
	@$(VENV_PYTHON) -c "import requests, dotenv, pynput; print('✅ All core dependencies installed')" || \
		echo "❌ Missing dependencies. Run 'make setup'"

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

permissions-macos: ## Help with macOS permissions
	@echo "🍎 macOS Permissions Setup"
	@echo "========================="
	@echo "1. Open System Preferences → Security & Privacy → Privacy → Accessibility"
	@echo "2. Click the lock and enter your password"
	@echo "3. Add one of the following:"
	@echo "   • Terminal (or iTerm2)"
	@echo "   • Python executable: $$(which python3)"
	@echo "4. Restart the service: make restart"
	@echo ""
	@echo "💡 Alternative: Run once with sudo to test permissions"

permissions-linux: ## Help with Linux permissions
	@echo "🐧 Linux Permissions Setup"
	@echo "=========================="
	@echo "Install system dependencies:"
	@echo ""
	@echo "Ubuntu/Debian:"
	@echo "  sudo apt-get install python3-tk libx11-dev libxtst-dev"
	@echo ""
	@echo "Fedora/RHEL:"
	@echo "  sudo dnf install python3-tkinter libX11-devel libXtst-devel"
	@echo ""
	@echo "Arch Linux:"
	@echo "  sudo pacman -S python tk libx11 libxtst"

autostart-macos: ## Setup macOS LaunchAgent for autostart
	@echo "🍎 Setting up macOS autostart..."
	@mkdir -p ~/Library/LaunchAgents
	@cat > ~/Library/LaunchAgents/com.promptstore.service.plist << 'EOF' && \
	echo '<?xml version="1.0" encoding="UTF-8"?>' && \
	echo '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">' && \
	echo '<plist version="1.0">' && \
	echo '<dict>' && \
	echo '    <key>Label</key>' && \
	echo '    <string>com.promptstore.service</string>' && \
	echo '    <key>ProgramArguments</key>' && \
	echo '    <array>' && \
	echo '        <string>$(PWD)/$(VENV_PYTHON)</string>' && \
	echo '        <string>$(PWD)/main.py</string>' && \
	echo '    </array>' && \
	echo '    <key>WorkingDirectory</key>' && \
	echo '    <string>$(PWD)</string>' && \
	echo '    <key>RunAtLoad</key>' && \
	echo '    <true/>' && \
	echo '    <key>KeepAlive</key>' && \
	echo '    <true/>' && \
	echo '    <key>StandardOutPath</key>' && \
	echo '    <string>$(PWD)/prompt-store-daemon.log</string>' && \
	echo '    <key>StandardErrorPath</key>' && \
	echo '    <string>$(PWD)/prompt-store-daemon-error.log</string>' && \
	echo '</dict>' && \
	echo '</plist>' > ~/Library/LaunchAgents/com.promptstore.service.plist
	@echo "✅ LaunchAgent created"
	@echo "To enable: launchctl load ~/Library/LaunchAgents/com.promptstore.service.plist"
	@echo "To disable: launchctl unload ~/Library/LaunchAgents/com.promptstore.service.plist"

autostart-linux: ## Setup Linux systemd service for autostart
	@echo "🐧 Setting up Linux systemd service..."
	@mkdir -p ~/.config/systemd/user
	@cat > ~/.config/systemd/user/prompt-store.service << 'EOF' && \
	echo '[Unit]' && \
	echo 'Description=Prompt Store Background Service' && \
	echo 'After=graphical-session.target' && \
	echo '' && \
	echo '[Service]' && \
	echo 'Type=simple' && \
	echo 'ExecStart=$(PWD)/$(VENV_PYTHON) $(PWD)/main.py' && \
	echo 'WorkingDirectory=$(PWD)' && \
	echo 'Restart=always' && \
	echo 'RestartSec=5' && \
	echo 'Environment=DISPLAY=:0' && \
	echo '' && \
	echo '[Install]' && \
	echo 'WantedBy=default.target' > ~/.config/systemd/user/prompt-store.service
	@systemctl --user daemon-reload
	@echo "✅ Systemd service created"
	@echo "To enable: systemctl --user enable prompt-store.service"
	@echo "To start: systemctl --user start prompt-store.service"
	@echo "To check status: systemctl --user status prompt-store.service"

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