#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/hlsget"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
rm -f "$BIN_DIR/hlsget"
rm -rf "$INSTALL_ROOT"
echo "hlsget удалён."
