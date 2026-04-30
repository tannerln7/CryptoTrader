#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

# shellcheck source=ops/install/lib.sh
. "${SCRIPT_DIR}/lib.sh"

ensure_root

INSTANCE=main
PURGE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      INSTANCE=${2:?--instance requires a value}
      shift 2
      ;;
    --purge)
      PURGE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: sudo ./ops/install/uninstall.sh [--instance NAME] [--purge] [--dry-run]

Disable and remove the installed market recorder instance environment file and,
when no instances remain, remove the shared service and polkit assets.
EOF
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

ENV_DEST="/etc/market-recorder/${INSTANCE}.env"
UNIT_DEST="/etc/systemd/system/market-recorder@.service"
SYSUSERS_DEST="/etc/sysusers.d/market-recorder.conf"
POLKIT_DEST="/etc/polkit-1/rules.d/49-market-recorder.rules"
STATE_DIR="/var/lib/market-recorder/${INSTANCE}"

if command_exists systemctl; then
  run_cmd systemctl disable --now "market-recorder@${INSTANCE}.service"
fi

if [[ -f "${ENV_DEST}" ]]; then
  run_cmd rm -f "${ENV_DEST}"
fi

remaining_env_count=0
if [[ -d /etc/market-recorder ]]; then
  remaining_env_count=$(find /etc/market-recorder -maxdepth 1 -type f -name '*.env' | wc -l | tr -d ' ')
fi

if [[ "${remaining_env_count}" == "0" ]]; then
  [[ ! -f "${UNIT_DEST}" ]] || run_cmd rm -f "${UNIT_DEST}"
  [[ ! -f "${SYSUSERS_DEST}" ]] || run_cmd rm -f "${SYSUSERS_DEST}"
  [[ ! -f "${POLKIT_DEST}" ]] || run_cmd rm -f "${POLKIT_DEST}"
  run_cmd systemctl daemon-reload
  systemctl_reload_polkit
fi

if [[ "${PURGE}" == "1" ]]; then
  [[ ! -d "${STATE_DIR}" ]] || run_cmd rm -rf "${STATE_DIR}"
fi

log_info "Removed market-recorder install assets for instance ${INSTANCE}."
if [[ "${PURGE}" != "1" ]]; then
  log_info "State data under ${STATE_DIR} was preserved."
fi