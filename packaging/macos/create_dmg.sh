#!/bin/bash
# Create macOS DMG installer for Promptheus

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist"
APP_PATH="$DIST_DIR/Promptheus.app"
DMG_NAME="Promptheus-Installer"
DMG_PATH="$DIST_DIR/$DMG_NAME.dmg"
VOLUME_NAME="Promptheus"

create_basic_dmg() {
    TEMP_DMG="$DIST_DIR/temp_$DMG_NAME.dmg"
    MOUNT_DIR="/Volumes/$VOLUME_NAME"

    if [[ -d "$MOUNT_DIR" ]]; then
        hdiutil detach "$MOUNT_DIR" -quiet || true
    fi

    hdiutil create -srcfolder "$APP_PATH" -volname "$VOLUME_NAME" -fs HFS+ \
        -fsargs "-c c=64,a=16,e=16" -format UDRW -size 200m "$TEMP_DMG"

    DEVICE=$(hdiutil attach -readwrite -noverify -noautoopen "$TEMP_DMG" | \
        grep -E '^/dev/' | sed 1q | awk '{print $1}')

    sleep 2

    ln -s /Applications "$MOUNT_DIR/Applications"

    sync
    hdiutil detach "$DEVICE"

    hdiutil convert "$TEMP_DMG" -format UDZO -imagekey zlib-level=9 -o "$DMG_PATH"
    rm -f "$TEMP_DMG"
}

if [[ ! -d "$APP_PATH" ]]; then
    echo "❌ App bundle not found: $APP_PATH"
    echo "   Run 'make build-macos' first"
    exit 1
fi

rm -f "$DMG_PATH"

if command -v create-dmg &> /dev/null; then
    echo "📦 Creating DMG with create-dmg (pretty installer)..."

    create-dmg \
        --volname "$VOLUME_NAME" \
        --volicon "$SCRIPT_DIR/Promptheus.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "Promptheus.app" 150 190 \
        --hide-extension "Promptheus.app" \
        --app-drop-link 450 190 \
        --no-internet-enable \
        "$DMG_PATH" \
        "$APP_PATH" \
    || {
        echo "⚠️  create-dmg failed, falling back to hdiutil..."
        create_basic_dmg
    }
else
    echo "📦 Creating DMG with hdiutil (basic installer)..."
    echo "   Tip: Install create-dmg for a prettier DMG: brew install create-dmg"
    create_basic_dmg
fi

if [[ -f "$DMG_PATH" ]]; then
    echo "✅ DMG created: $DMG_PATH"
    ls -lh "$DMG_PATH"
else
    echo "❌ Failed to create DMG"
    exit 1
fi
