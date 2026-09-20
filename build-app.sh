#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Build Study Buddy.app — double-clickable Mac app for Finder / Dock.
#  The bundle is generated (not committed): run this after pulling.
#  No downloads: uses built-in sips/iconutil + repo sources only.
# ─────────────────────────────────────────────────────────────
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$ROOT/Study Buddy.app"
ICON_SRC="$ROOT/frontend/public/icon-512.png"

echo "Building Study Buddy.app..."

# ── 0. Window shell present (small pip install, never gigabytes) ───
if ! "$ROOT/.venv/bin/python" -c "import webview.platforms.cocoa" 2>/dev/null; then
  echo "  Installing window shell (one time)..."
  "$ROOT/.venv/bin/pip" install -q pywebview || {
    echo "  ❌ pip install pywebview failed — check network, then re-run."
    exit 1
  }
fi

# ── 1. Fresh bundle skeleton ─────────────────────────────────
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# ── 2. Icon (iconset → .icns with built-in tools) ────────────
if [[ -f "$ICON_SRC" ]]; then
  ICONSET="$(mktemp -d)/StudyBuddy.iconset"
  mkdir -p "$ICONSET"
  sips -z 16 16     "$ICON_SRC" --out "$ICONSET/icon_16x16.png" >/dev/null
  sips -z 32 32     "$ICON_SRC" --out "$ICONSET/icon_16x16@2x.png" >/dev/null
  sips -z 32 32     "$ICON_SRC" --out "$ICONSET/icon_32x32.png" >/dev/null
  sips -z 64 64     "$ICON_SRC" --out "$ICONSET/icon_32x32@2x.png" >/dev/null
  sips -z 128 128   "$ICON_SRC" --out "$ICONSET/icon_128x128.png" >/dev/null
  sips -z 256 256   "$ICON_SRC" --out "$ICONSET/icon_128x128@2x.png" >/dev/null
  sips -z 256 256   "$ICON_SRC" --out "$ICONSET/icon_256x256.png" >/dev/null
  sips -z 512 512   "$ICON_SRC" --out "$ICONSET/icon_256x256@2x.png" >/dev/null
  sips -z 512 512   "$ICON_SRC" --out "$ICONSET/icon_512x512.png" >/dev/null
  cp "$ICON_SRC" "$ICONSET/icon_512x512@2x.png"
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/StudyBuddy.icns"
  rm -rf "$(dirname "$ICONSET")"
  ICON_KEY="  <key>CFBundleIconFile</key>
  <string>StudyBuddy</string>"
  echo "  icon: Study Buddy.icns"
else
  ICON_KEY=""
  echo "  (no icon source — skipping, app still works)"
fi

# ── 3. Info.plist ────────────────────────────────────────────
cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Study Buddy</string>
  <key>CFBundleDisplayName</key>
  <string>Study Buddy — AI Study Assistant</string>
  <key>CFBundleIdentifier</key>
  <string>com.studybuddy.app</string>
  <key>CFBundleVersion</key>
  <string>2.5.0</string>
  <key>CFBundleShortVersionString</key>
  <string>2.5</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>StudyBuddy</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>LSRequiresNativeExecution</key>
  <true/>
  <key>LSUIElement</key>
  <false/>
$ICON_KEY
</dict>
</plist>
EOF

# ── 4. Launcher: native window, no Terminal ───────────────────
# Finder runs this with no console — stdout goes to Console.app, so keep it
# quiet. The window (aria_window.py) shows all errors itself.
cat > "$APP/Contents/MacOS/StudyBuddy" <<'EOF'
#!/bin/bash
# GUI apps don't inherit the shell PATH (no /usr/local/bin, no Homebrew) —
# extend it so child processes (ollama/npm fallbacks) resolve.
export PATH="/opt/homebrew/bin:/usr/local/bin:/opt/local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
# arch -arm64: never run translated — the venv's compiled wheels are
# arm64-only and die under Rosetta (proven via aria-server.log).
exec arch -arm64 "$ROOT/.venv/bin/python" "$ROOT/backend/aria_window.py"
EOF
chmod +x "$APP/Contents/MacOS/StudyBuddy"

# ── 5. Freshness check ───────────────────────────────────────
plutil -lint "$APP/Contents/Info.plist"
echo ""
echo "Done: $APP"
echo "  → Drag it to the Dock, then double-click to run Study Buddy."
echo "  → Needs Ollama + models (run ./start-app.sh once if the app says so)."
