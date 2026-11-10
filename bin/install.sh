#!/bin/bash
. "$(dirname "$0")/common.sh"
mkdir -p "$RUNTIME/downloads" "$RELEASES_DIR" "$STATE_DIR/logs"
download() { curl --fail --location --retry 3 --connect-timeout 20 --max-time 600 "$1" --output "$2"; }
if [[ ! -x "$NODE_DIR/bin/node" ]]; then
  file="node-v$NODE_VERSION-$TARGET.tar.gz"
  download "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt" "$RUNTIME/downloads/node-checksums.txt"
  download "https://nodejs.org/dist/v$NODE_VERSION/$file" "$RUNTIME/downloads/$file"
  sum=$(awk -v file="$file" '$2 == file { print $1 }' "$RUNTIME/downloads/node-checksums.txt")
  [[ "$sum" =~ ^[a-f0-9]{64}$ ]]
  printf '%s  %s\n' "$sum" "$RUNTIME/downloads/$file" | shasum -a 256 -c -
  tar -xzf "$RUNTIME/downloads/$file" -C "$RUNTIME"
fi
[[ "$(node --version)" == "v$NODE_VERSION" ]]
if [[ ! -f "$RUNTIME/pnpm/node_modules/pnpm/bin/pnpm.cjs" ]]; then
  npm install --prefix "$RUNTIME/pnpm" "pnpm@$PNPM_VERSION" --no-audit --no-fund
fi
[[ "$(pnpm --version)" == "$PNPM_VERSION" ]]
if [[ ! -x "$RUNTIME/caddy/caddy" ]]; then
  file="caddy_${CADDY_VERSION}_${CADDY_TARGET}.tar.gz"
  release="https://github.com/caddyserver/caddy/releases/download/v$CADDY_VERSION"
  download "$release/caddy_${CADDY_VERSION}_checksums.txt" "$RUNTIME/downloads/caddy-checksums.txt"
  download "$release/$file" "$RUNTIME/downloads/$file"
  sum=$(awk -v file="$file" '$2 == file { print $1 }' "$RUNTIME/downloads/caddy-checksums.txt")
  [[ "$sum" =~ ^[a-f0-9]{64}$ ]]
  printf '%s  %s\n' "$sum" "$RUNTIME/downloads/$file" | shasum -a 256 -c -
  mkdir -p "$RUNTIME/caddy"
  tar -xzf "$RUNTIME/downloads/$file" -C "$RUNTIME/caddy"
fi
if [[ ! -d "$SOURCE/.git" ]]; then
  git init "$SOURCE"
  git -C "$SOURCE" remote add origin "$MAUS_REPO"
fi
if ! git -C "$SOURCE" cat-file -e "$MAUS_COMMIT^{commit}" 2>/dev/null; then
  git -C "$SOURCE" fetch --depth 1 origin "$MAUS_COMMIT"
fi
grep -qxF '/.omb-verified' "$SOURCE/.git/info/exclude" || printf '\n/.omb-verified\n' >> "$SOURCE/.git/info/exclude"
[[ -z "$(git -C "$SOURCE" status --porcelain)" ]]
git -C "$SOURCE" checkout --detach "$MAUS_COMMIT"
cd "$SOURCE"
pnpm install --frozen-lockfile
pnpm build:server
pnpm exec vite build
OPENMAUSBOT_CUA_ARCHES="$(node -p 'process.arch')" OPENMAUSBOT_CUA_ARCHES_PARTIAL=1 node scripts/prepare-duckdb.mjs
node scripts/smoke-packaged-server.mjs
python3 "$BFA_ROOT/bin/verify.py" "$SOURCE" "$STATE_DIR/logs"
printf '%s\n' "$MAUS_COMMIT" > "$SOURCE/.omb-verified"
python3 - <<'PY'
import os
from pathlib import Path
current = Path(os.environ['CURRENT'])
pending = current.with_name('current.next')
if pending.is_symlink(): pending.unlink()
pending.symlink_to(os.environ['SOURCE'], target_is_directory=True)
os.replace(pending, current)
PY
printf '构建及隔离验证通过：%s\n' "$MAUS_COMMIT"
