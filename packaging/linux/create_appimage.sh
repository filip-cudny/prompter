#!/bin/bash
# Create AppImage from PyInstaller build

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist"
PYINSTALLER_BUILD="$DIST_DIR/promptheus"
APPDIR="$DIST_DIR/Promptheus.AppDir"
APPIMAGETOOL="$SCRIPT_DIR/appimagetool-x86_64.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

if [ ! -d "$PYINSTALLER_BUILD" ]; then
    echo "Error: PyInstaller build not found at $PYINSTALLER_BUILD"
    echo "Run 'make build-linux' first."
    exit 1
fi

echo "Creating AppDir structure..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/promptheus"

echo "Copying PyInstaller output..."
cp -r "$PYINSTALLER_BUILD"/* "$APPDIR/usr/share/promptheus/"

echo "Creating symlink to executable..."
ln -sf "../share/promptheus/promptheus" "$APPDIR/usr/bin/promptheus"

echo "Creating AppRun..."
cat > "$APPDIR/AppRun" << 'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
exec "$HERE/usr/share/promptheus/promptheus" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "Copying desktop file..."
cp "$SCRIPT_DIR/promptheus.desktop" "$APPDIR/promptheus.desktop"

echo "Copying icon..."
cp "$PROJECT_ROOT/icon.svg" "$APPDIR/promptheus.svg"

if [ ! -f "$APPIMAGETOOL" ]; then
    echo "Downloading appimagetool..."
    curl -L -o "$APPIMAGETOOL" "$APPIMAGETOOL_URL"
    chmod +x "$APPIMAGETOOL"
fi

echo "Creating AppImage..."
ARCH=x86_64 "$APPIMAGETOOL" "$APPDIR" "$DIST_DIR/Promptheus-x86_64.AppImage"

echo ""
echo "AppImage created: $DIST_DIR/Promptheus-x86_64.AppImage"
echo "To run: chmod +x $DIST_DIR/Promptheus-x86_64.AppImage && $DIST_DIR/Promptheus-x86_64.AppImage"
