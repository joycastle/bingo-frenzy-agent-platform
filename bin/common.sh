#!/bin/bash
set -euo pipefail
BFA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$BFA_ROOT/versions.env"
if [[ -f "$BFA_ROOT/config.env" ]]; then . "$BFA_ROOT/config.env"; fi
: "${RELEASES_DIR:=$HOME/Work/mausbot-releases}"
: "${STATE_DIR:=$HOME/.local/share/bingo-frenzy-agent-platform}"
: "${OMB_DATA_DIR:=$HOME/.openmausbot}"
: "${WEB_BIND:=127.0.0.1}"
: "${WEB_PORT:=18799}"
: "${OMB_PORT:=8799}"
: "${OMB_WEBHOOK_PORT:=8800}"
: "${OMB_PUBLIC_URL:=http://localhost:$WEB_PORT}"
case "$(uname -s)/$(uname -m)" in
  Darwin/arm64) TARGET=darwin-arm64; CADDY_TARGET=mac_arm64 ;;
  Darwin/x86_64) TARGET=darwin-x64; CADDY_TARGET=mac_amd64 ;;
  *) echo '当前原生部署脚本支持 macOS；Linux 使用上游 Dockerfile。' >&2; exit 1 ;;
esac
RUNTIME="$STATE_DIR/runtime"
NODE_DIR="$RUNTIME/node-v$NODE_VERSION-$TARGET"
CURRENT="$STATE_DIR/current"
SOURCE="$RELEASES_DIR/$MAUS_COMMIT"
export PATH="$NODE_DIR/bin:$RUNTIME/pnpm/node_modules/.bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export OMB_DATA_DIR OMB_PORT OMB_WEBHOOK_PORT OMB_PUBLIC_URL
export WEB_PORT WEB_BIND STATE_DIR RELEASES_DIR BFA_ROOT NODE_DIR CURRENT SOURCE
export ELECTRON_SKIP_BINARY_DOWNLOAD=1
umask 077
