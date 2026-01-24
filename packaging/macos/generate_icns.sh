#!/bin/bash
# Generate macOS ICNS icon from SVG source

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SOURCE_SVG="$PROJECT_ROOT/icon.svg"
OUTPUT_ICNS="$SCRIPT_DIR/Promptheus.icns"
ICONSET_DIR="$SCRIPT_DIR/Promptheus.iconset"

if [[ ! -f "$SOURCE_SVG" ]]; then
    echo "❌ Source SVG not found: $SOURCE_SVG"
    exit 1
fi

if ! command -v rsvg-convert &> /dev/null; then
    echo "📦 Installing librsvg via Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo "❌ Homebrew not found. Please install Homebrew first:"
        echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        exit 1
    fi
    brew install librsvg
fi

echo "🎨 Generating ICNS from $SOURCE_SVG..."

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

SIZES=(16 32 64 128 256 512)
for size in "${SIZES[@]}"; do
    echo "  → Generating ${size}x${size}..."
    rsvg-convert -w "$size" -h "$size" "$SOURCE_SVG" -o "$ICONSET_DIR/icon_${size}x${size}.png"

    double=$((size * 2))
    echo "  → Generating ${size}x${size}@2x (${double}x${double})..."
    rsvg-convert -w "$double" -h "$double" "$SOURCE_SVG" -o "$ICONSET_DIR/icon_${size}x${size}@2x.png"
done

echo "  → Generating 512x512@2x (1024x1024)..."
rsvg-convert -w 1024 -h 1024 "$SOURCE_SVG" -o "$ICONSET_DIR/icon_512x512@2x.png"

echo "🔧 Creating ICNS file..."
iconutil -c icns "$ICONSET_DIR" -o "$OUTPUT_ICNS"

rm -rf "$ICONSET_DIR"

if [[ -f "$OUTPUT_ICNS" ]]; then
    echo "✅ ICNS created: $OUTPUT_ICNS"
    ls -lh "$OUTPUT_ICNS"
else
    echo "❌ Failed to create ICNS"
    exit 1
fi
