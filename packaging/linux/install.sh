#!/bin/bash
# Install Promptheus on Linux (system-wide or user installation)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist/promptheus"

usage() {
    echo "Usage: $0 [--system|--user]"
    echo ""
    echo "Options:"
    echo "  --system    Install system-wide (requires sudo)"
    echo "  --user      Install for current user only (default)"
    echo "  --uninstall Remove installation"
    echo ""
    exit 1
}

install_user() {
    echo "Installing Promptheus for current user..."

    local BIN_DIR="$HOME/.local/bin"
    local APP_DIR="$HOME/.local/share/promptheus"
    local ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
    local DESKTOP_DIR="$HOME/.local/share/applications"
    local AUTOSTART_DIR="$HOME/.config/autostart"

    mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR" "$DESKTOP_DIR" "$AUTOSTART_DIR"

    if [ ! -d "$DIST_DIR" ]; then
        echo "Error: Build not found at $DIST_DIR"
        echo "Run 'make build-linux' first."
        exit 1
    fi

    echo "Copying application files..."
    cp -r "$DIST_DIR"/* "$APP_DIR/"

    echo "Creating launcher script..."
    cat > "$BIN_DIR/promptheus" << 'EOF'
#!/bin/bash
exec "$HOME/.local/share/promptheus/promptheus" "$@"
EOF
    chmod +x "$BIN_DIR/promptheus"

    echo "Installing icon..."
    cp "$PROJECT_ROOT/icon.svg" "$ICON_DIR/promptheus.svg"

    echo "Installing desktop entry..."
    sed "s|Exec=promptheus|Exec=$BIN_DIR/promptheus|g" \
        "$SCRIPT_DIR/promptheus.desktop" > "$DESKTOP_DIR/promptheus.desktop"

    echo "Installing autostart entry..."
    sed "s|Exec=promptheus|Exec=$BIN_DIR/promptheus|g" \
        "$SCRIPT_DIR/promptheus-autostart.desktop" > "$AUTOSTART_DIR/promptheus.desktop"

    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

    echo ""
    echo "Installation complete!"
    echo "  - Application: $APP_DIR"
    echo "  - Launcher: $BIN_DIR/promptheus"
    echo ""
    echo "Make sure $BIN_DIR is in your PATH."
    echo "Run 'promptheus' to start the application."
}

install_system() {
    echo "Installing Promptheus system-wide..."

    local BIN_DIR="/usr/local/bin"
    local APP_DIR="/opt/promptheus"
    local ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
    local DESKTOP_DIR="/usr/share/applications"

    if [ ! -d "$DIST_DIR" ]; then
        echo "Error: Build not found at $DIST_DIR"
        echo "Run 'make build-linux' first."
        exit 1
    fi

    echo "Copying application files..."
    sudo mkdir -p "$APP_DIR"
    sudo cp -r "$DIST_DIR"/* "$APP_DIR/"

    echo "Creating launcher script..."
    sudo tee "$BIN_DIR/promptheus" > /dev/null << 'EOF'
#!/bin/bash
exec /opt/promptheus/promptheus "$@"
EOF
    sudo chmod +x "$BIN_DIR/promptheus"

    echo "Installing icon..."
    sudo mkdir -p "$ICON_DIR"
    sudo cp "$PROJECT_ROOT/icon.svg" "$ICON_DIR/promptheus.svg"

    echo "Installing desktop entry..."
    sudo cp "$SCRIPT_DIR/promptheus.desktop" "$DESKTOP_DIR/"

    sudo gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    sudo update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

    echo ""
    echo "Installation complete!"
    echo "  - Application: $APP_DIR"
    echo "  - Launcher: $BIN_DIR/promptheus"
    echo ""
    echo "Run 'promptheus' to start the application."
}

uninstall() {
    echo "Uninstalling Promptheus..."

    rm -f "$HOME/.local/bin/promptheus"
    rm -rf "$HOME/.local/share/promptheus"
    rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/promptheus.svg"
    rm -f "$HOME/.local/share/applications/promptheus.desktop"
    rm -f "$HOME/.config/autostart/promptheus.desktop"

    if [ -f "/usr/local/bin/promptheus" ]; then
        sudo rm -f "/usr/local/bin/promptheus"
        sudo rm -rf "/opt/promptheus"
        sudo rm -f "/usr/share/icons/hicolor/scalable/apps/promptheus.svg"
        sudo rm -f "/usr/share/applications/promptheus.desktop"
    fi

    echo "Uninstallation complete."
}

case "${1:-}" in
    --system)
        install_system
        ;;
    --user|"")
        install_user
        ;;
    --uninstall)
        uninstall
        ;;
    *)
        usage
        ;;
esac
