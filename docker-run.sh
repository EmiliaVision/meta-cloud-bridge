#!/bin/sh
set -eu

cd /opt/meta-cloud-bridge

RUN_UID="${UID:-1337}"
RUN_GID="${GID:-1337}"

# Disable the default file logger when the generated config still points at the
# read-only application directory. This replaces the old yq dependency with the
# PyYAML dependency already installed by the project.
disable_default_file_logging() {
    config_path="/data/config.yaml"
    [ -f "$config_path" ] || return 0

    python - "$config_path" <<'PY'
from pathlib import Path
import sys

import yaml

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text()) or {}
logging = data.get("logging") or {}
handlers = logging.get("handlers") or {}
file_handler = handlers.get("file") or {}

if file_handler.get("filename") not in {"./whatsapp-cloud.log", "./meta-cloud-bridge.log"}:
    raise SystemExit(0)

root = logging.get("root") or {}
root_handlers = root.get("handlers")
if isinstance(root_handlers, list):
    root["handlers"] = [handler for handler in root_handlers if handler != "file"]

handlers.pop("file", None)
path.write_text(yaml.safe_dump(data, sort_keys=False))
PY
}

fixperms() {
    chown -R "$RUN_UID:$RUN_GID" /data
    disable_default_file_logging || true
}

if [ ! -f /data/config.yaml ]; then
    cp example-config.yaml /data/config.yaml
    echo "Didn't find a config file."
    echo "Copied default config file to /data/config.yaml"
    echo "Modify that config file to your liking."
    echo "Start the container again after that to generate the registration file."
    fixperms
    exit 0
fi

if [ ! -f /data/registration.yaml ]; then
    meta-cloud-bridge -g -c /data/config.yaml -r /data/registration.yaml
    echo "Didn't find a registration file."
    echo "Generated one for you."
    echo "Copy that over to your homeserver appservice directory."
    fixperms
    exit 0
fi

if [ "${1:-}" = "dev" ]; then
    uv sync --frozen --dev
    exec watchmedo auto-restart -R -p="*.py" -d="." /opt/meta-cloud-bridge/docker-run.sh
fi

fixperms
exec gosu "$RUN_UID:$RUN_GID" meta-cloud-bridge -c /data/config.yaml
