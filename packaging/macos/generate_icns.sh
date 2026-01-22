#!/bin/bash
# Generate macOS .icns file from icon.svg

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SVG_FILE="$PROJECT_ROOT/icon.svg"
OUTPUT_ICNS="$SCRIPT_DIR/Promptheus.icns"
ICONSET_DIR="$SCRIPT_DIR/Promptheus.iconset"

if [ ! -f "$SVG_FILE" ]; then
    echo "Error: icon.svg not found at $SVG_FILE"
    exit 1
fi

if ! command -v rsvg-convert &> /dev/null && ! command -v convert &> /dev/null; then
    echo "Error: Neither rsvg-convert nor ImageMagick convert found."
    echo "Install with: brew install librsvg (recommended) or brew install imagemagick"
    exit 1
fi

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

convert_svg() {
    local size=$1
    local output=$2

    if command -v rsvg-convert &> /dev/null; then
        rsvg-convert -w "$size" -h "$size" "$SVG_FILE" -o "$output"
    else
        convert -background none -resize "${size}x${size}" "$SVG_FILE" "$output"
    fi
}

echo "Generating icon sizes..."

convert_svg 16 "$ICONSET_DIR/icon_16x16.png"
convert_svg 32 "$ICONSET_DIR/icon_16x16@2x.png"
convert_svg 32 "$ICONSET_DIR/icon_32x32.png"
convert_svg 64 "$ICONSET_DIR/icon_32x32@2x.png"
convert_svg 128 "$ICONSET_DIR/icon_128x128.png"
convert_svg 256 "$ICONSET_DIR/icon_128x128@2x.png"
convert_svg 256 "$ICONSET_DIR/icon_256x256.png"
convert_svg 512 "$ICONSET_DIR/icon_256x256@2x.png"
convert_svg 512 "$ICONSET_DIR/icon_512x512.png"
convert_svg 1024 "$ICONSET_DIR/icon_512x512@2x.png"

echo "Creating .icns file..."
iconutil -c icns "$ICONSET_DIR" -o "$OUTPUT_ICNS"

rm -rf "$ICONSET_DIR"

echo "Generated: $OUTPUT_ICNS"
