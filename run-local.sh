#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SECRETS_DIR=${SECRETS_DIR:-"$SCRIPT_DIR/../company-secrets/${SERVER_DEPLOYMENT:-dev}"}

load_env_file() {
    file_path=$1
    if [ -f "$file_path" ]; then
        set -a
        . "$file_path"
        set +a
    fi
}

if [ ! -d "$SECRETS_DIR" ]; then
    echo "Secrets directory not found: $SECRETS_DIR" >&2
    exit 1
fi

load_env_file "$SECRETS_DIR/common.env"
load_env_file "$SECRETS_DIR/storage.env"
load_env_file "$SECRETS_DIR/ai-rag-service-manager.env"

if [ -z "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "$SECRETS_DIR/edward-creds.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$SECRETS_DIR/edward-creds.json"
fi

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec uv run python -m app.main