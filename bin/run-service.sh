#!/bin/bash
. "$(dirname "$0")/common.sh"
cd "$CURRENT"
case "${1:-}" in
  server)
    export OMB_DUCKDB_DIR="$CURRENT/dist-native/duckdb/$TARGET"
    exec node dist-server/openmausbot.js serve --port "$OMB_PORT" --data-dir "$OMB_DATA_DIR" --no-pair
    ;;
  edge) exec "$RUNTIME/caddy/caddy" run --config "$STATE_DIR/Caddyfile" --adapter caddyfile ;;
  *) echo 'usage: run-service.sh server|edge' >&2; exit 2 ;;
esac
