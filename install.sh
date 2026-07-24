#!/usr/bin/env bash
set -euo pipefail

APP_NAME="hlsget"
INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_NAME"
VENV="$INSTALL_ROOT/venv"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 was not found. Install it with: sudo apt install python3 python3-venv" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Error: FFmpeg was not found. Install it with: sudo apt install ffmpeg" >&2
  exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "Error: Python's venv module is unavailable. Install it with: sudo apt install python3-venv" >&2
  exit 1
fi

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install "$PROJECT_DIR"
ln -sfn "$VENV/bin/hlsget" "$BIN_DIR/hlsget"

echo
echo "hlsget was installed at: $BIN_DIR/hlsget"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "Add ~/.local/bin to PATH, then restart your terminal:"
  echo '  echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
  echo '  source ~/.bashrc'
fi
echo "Check the installation with: hlsget --help"
