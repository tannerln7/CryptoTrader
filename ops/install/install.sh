#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

# shellcheck source=ops/install/lib.sh
. "${SCRIPT_DIR}/lib.sh"

ensure_root

INSTANCE=main
ENABLE=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)
      INSTANCE=${2:?--instance requires a value}
      shift 2
      ;;
    --enable)
      ENABLE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: sudo ./ops/install/install.sh [--instance NAME] [--enable] [--dry-run]

Install the systemd service template, polkit rule, sysusers asset, and default
    instance environment file for the market recorder.

    --enable enables the unit for future boots. It does not start the service.
EOF
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
INSTANCE_CONFIG_PATH="${REPO_ROOT}/data/systemd/${INSTANCE}/config.yaml"
CONFIG_PATH="${REPO_ROOT}/config/config.example.yaml"
ENV_DEST="/etc/market-recorder/${INSTANCE}.env"
UNIT_DEST="/etc/systemd/system/market-recorder@.service"
SYSUSERS_DEST="/etc/sysusers.d/market-recorder.conf"
POLKIT_DEST="/etc/polkit-1/rules.d/49-market-recorder.rules"
POLKIT_GROUP=$(detect_polkit_group)
OPERATOR_USER=${SUDO_USER:-}

[[ -x "${PYTHON_BIN}" ]] || die "Missing virtualenv interpreter at ${PYTHON_BIN}"
if [[ -f "${INSTANCE_CONFIG_PATH}" ]]; then
  CONFIG_PATH="${INSTANCE_CONFIG_PATH}"
fi
[[ -f "${CONFIG_PATH}" ]] || die "Missing installer config at ${CONFIG_PATH}"

install_asset "${REPO_ROOT}/ops/systemd/market-recorder@.service" "${UNIT_DEST}" 0644 root root
install_asset "${REPO_ROOT}/ops/sysusers/market-recorder.conf" "${SYSUSERS_DEST}" 0644 root root
install_asset "${REPO_ROOT}/ops/polkit/49-market-recorder.rules" "${POLKIT_DEST}" 0644 root "${POLKIT_GROUP}"

if command_exists systemd-sysusers; then
  run_cmd systemd-sysusers "${SYSUSERS_DEST}"
else
  die "systemd-sysusers is required on this system."
fi

run_cmd install -d -m 0750 -o root -g market-recorder /etc/market-recorder

add_operator_to_group "${OPERATOR_USER}"

if [[ ! -f "${ENV_DEST}" ]]; then
  write_text_file "${ENV_DEST}" 0640 root market-recorder <<EOF
MARKET_RECORDER_REPO_ROOT=${REPO_ROOT}
MARKET_RECORDER_PYTHON=${PYTHON_BIN}
MARKET_RECORDER_CONFIG=${CONFIG_PATH}
# Optional overrides.
# MARKET_RECORDER_LOG_LEVEL=INFO
# MARKET_RECORDER_HEALTH_INTERVAL_SECONDS=10
EOF
else
  log_info "Keeping existing instance env file at ${ENV_DEST}"
fi

run_cmd systemctl daemon-reload
systemctl_reload_polkit

if [[ "${DRY_RUN}" != "1" ]]; then
  if ! run_as_service_user market-recorder test -x "${REPO_ROOT}"; then
    die "The market-recorder service user cannot access ${REPO_ROOT}. Move the repo to a service-readable location or grant ACL access, then rerun install."
  fi
  if ! run_as_service_user market-recorder test -r "${CONFIG_PATH}"; then
    die "The market-recorder service user cannot read ${CONFIG_PATH}. Move the repo to a service-readable location or grant ACL access, then rerun install."
  fi
  if ! run_as_service_user market-recorder test -x "${PYTHON_BIN}"; then
    die "The market-recorder service user cannot execute ${PYTHON_BIN}. Move the repo to a service-readable location or grant ACL access, then rerun install."
  fi
fi

if [[ "${ENABLE}" == "1" ]]; then
  run_cmd systemctl enable "market-recorder@${INSTANCE}.service"
  log_info "Enabled market-recorder@${INSTANCE}.service for future boots. It was not started."
fi

log_info "Installed market-recorder assets for instance ${INSTANCE}."
log_info "Polkit rule installed as root:${POLKIT_GROUP} at ${POLKIT_DEST}."
if [[ -n "${OPERATOR_USER}" && "${OPERATOR_USER}" != "root" ]]; then
  log_info "Added ${OPERATOR_USER} to the market-recorder group if needed. Refresh the group with 'newgrp market-recorder' or log out and back in."
fi
log_info "Next steps:"
log_info "  1. Create or edit the runtime config and update ${ENV_DEST}."
log_info "  2. Verify service-user access to the repo root, Python, and runtime config."
log_info "  3. Refresh group membership with 'newgrp market-recorder' or log out and back in."
log_info "  4. Optionally rerun install.sh with --enable to enable boot-time startup."
log_info "  5. Run market-recorder start, status, health, and stop as an unprivileged operator."