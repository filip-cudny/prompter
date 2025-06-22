
#!/bin/bash

# Prompt Store Setup Script
# Usage: ./setup.sh

set -e

echo "🚀 Setting up Prompt Store Background Service..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo "❌ Python $PYTHON_VERSION found, but Python $REQUIRED_VERSION or higher is required."
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"

# Check for externally managed environment
if ! check_external_management; then
    echo "⚠️  Detected externally managed Python environment (PEP 668)"
    echo "This is common with Homebrew Python on macOS or system Python on some Linux distributions."
    echo ""
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
if [ ! -d ".venv" ]; then
    # Try creating virtual environment with different approaches
    if python3 -m venv .venv 2>/dev/null; then
        echo "✅ Virtual environment created successfully"
    else
        echo "❌ Failed to create virtual environment with standard method"
        echo "Trying alternative approach..."

        # Try with --system-site-packages as fallback
        if python3 -m venv --system-site-packages .venv 2>/dev/null; then
            echo "✅ Virtual environment created with --system-site-packages"
        else
            echo "❌ Failed to create virtual environment"
            echo ""
            echo "🔧 Manual alternatives:"
            echo "1. Use pipx (recommended for applications):"
            echo "   brew install pipx  # on macOS"
            echo "   pipx install -e ."
            echo ""
            echo "2. Use conda/miniconda:"
            echo "   conda create -n prompt-store python=3.8+"
            echo "   conda activate prompt-store"
            echo ""
            echo "3. Override externally managed restriction (not recommended):"
            echo "   pip install --break-system-packages -r requirements.txt"
            exit 1
        fi
    fi
else
    echo "ℹ️  Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip in the virtual environment
echo "⬆️  Upgrading pip..."
if ! pip install --upgrade pip; then
    echo "⚠️  Pip upgrade failed, continuing with existing version..."
fi

# Install dependencies
echo "📥 Installing dependencies..."
if pip install -r requirements.txt; then
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Failed to install dependencies"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "1. Make sure you're in the virtual environment:"
    echo "   source .venv/bin/activate"
    echo ""
    echo "2. Try installing dependencies manually:"
    echo "   pip install requests python-dotenv pynput"
    echo ""
    echo "3. On macOS, you might need:"
    echo "   pip install 'pyobjc-framework-Cocoa>=9.0'"
    echo ""
    echo "4. On Linux, you might need:"
    echo "   pip install 'python-xlib>=0.33'"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️  Creating configuration file..."
    cat > .env << 'EOF'
# Prompt Store Configuration
# Copy this file and update with your actual values

# Required settings
API_KEY=your_api_key_here
BASE_URL=https://your-api-server.com

EOF
    echo "✅ Configuration file created at .env"
    echo "⚠️  Please edit .env with your actual API key and base URL"
else
    echo "ℹ️  Configuration file .env already exists"
fi

# Platform-specific setup
echo "🖥️  Checking platform-specific requirements..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 macOS detected"
    echo ""
    echo "📋 macOS Setup Checklist:"
    echo "1. ✅ Virtual environment created"
    echo "2. ⚠️  Grant accessibility permissions (required for global hotkeys):"
    echo "   • Go to System Preferences → Security & Privacy → Privacy → Accessibility"
    echo "   • Click the lock and enter your password"
    echo "   • Add Terminal (or iTerm2) to the list"
    echo "   • Alternatively, add Python executable: $(which python3)"
    echo "3. 🔄 Restart the application after granting permissions"
    echo ""
    echo "💡 If you encounter permission issues, try:"
    echo "   • Running from Terminal that has accessibility permissions"
    echo "   • Using sudo temporarily to test: sudo python3 main.py"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🐧 Linux detected"
    echo ""
    echo "📋 Linux Setup Checklist:"
    echo "1. ✅ Virtual environment created"
    echo "2. 📦 Install system dependencies (if not already installed):"
    echo ""
    echo "   Ubuntu/Debian:"
    echo "   sudo apt-get update"
    echo "   sudo apt-get install python3-tk libx11-dev libxtst-dev"
    echo ""
    echo "   Fedora/RHEL:"
    echo "   sudo dnf install python3-tkinter libX11-devel libXtst-devel"
    echo ""
    echo "   Arch Linux:"
    echo "   sudo pacman -S python tk libx11 libxtst"
    echo ""
    echo "3. 🔑 For global hotkeys, you may need to run with appropriate permissions"
    echo "   or ensure your user has access to input devices"
    echo ""
    echo "💡 If hotkeys don't work:"
    echo "   • Try running with: sudo python3 main.py (temporarily)"
    echo "   • Check if you're using Wayland (may have limitations)"
    echo "   • Consider switching to X11 session if on Wayland"
fi

echo ""
echo "🎉 Setup complete!"
