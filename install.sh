#!/usr/bin/env bash
set -euo pipefail

APP_NAME="hlsget"
INSTALL_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/$APP_NAME"
VENV="$INSTALL_ROOT/venv"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Ошибка: не найден python3. Установите: sudo apt install python3 python3-venv" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Ошибка: не найден FFmpeg. Установите: sudo apt install ffmpeg" >&2
  exit 1
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
  echo "Ошибка: модуль venv недоступен. Установите: sudo apt install python3-venv" >&2
  exit 1
fi

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install "$PROJECT_DIR"
ln -sfn "$VENV/bin/hlsget" "$BIN_DIR/hlsget"

echo
echo "hlsget установлен: $BIN_DIR/hlsget"
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
  echo "Добавьте ~/.local/bin в PATH и перезапустите терминал:"
  echo '  echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc'
  echo '  source ~/.bashrc'
fi
echo "Проверка: hlsget --help"
