#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SOURCE_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

# shellcheck source=ops/install/lib.sh
. "${SCRIPT_DIR}/lib.sh"

ensure_root

INSTANCE=production
ENABLE=0
DRY_RUN=0
APP_ROOT=/opt/CryptoTrader
CONFIG_ROOT=/etc/CryptoTrader
WRAPPER_DEST=/usr/local/bin/market-recorder
UNIT_DEST=/etc/systemd/system/market-recorder@.service
SYSUSERS_DEST=/etc/sysusers.d/market-recorder.conf
POLKIT_DEST=/etc/polkit-1/rules.d/49-market-recorder.rules
POLKIT_GROUP=$(detect_polkit_group)
OPERATOR_USER=${SUDO_USER:-}
ENV_DEST=
CONFIG_DEST=
SOURCES_DEST=
STAGE_ROOT=
TMP_RUNTIME_CONFIG=
TMP_SOURCES_CONFIG=
TMP_ENV_FILE=

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

  Install the production market-recorder layout under /opt/CryptoTrader and
    provision /etc/CryptoTrader, /var/lib/market-recorder, and /run/market-recorder
    for the selected instance.

    --enable enables the unit for future boots. It does not start the service.
EOF
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

ENV_DEST="${CONFIG_ROOT}/${INSTANCE}.env"
CONFIG_DEST="${CONFIG_ROOT}/${INSTANCE}.yaml"
SOURCES_DEST="${CONFIG_ROOT}/${INSTANCE}.sources.yaml"

cleanup() {
  local status=$?
  [[ -n "${STAGE_ROOT}" && -d "${STAGE_ROOT}" ]] && rm -rf "${STAGE_ROOT}"
  [[ -n "${TMP_RUNTIME_CONFIG}" && -f "${TMP_RUNTIME_CONFIG}" ]] && rm -f "${TMP_RUNTIME_CONFIG}"
  [[ -n "${TMP_SOURCES_CONFIG}" && -f "${TMP_SOURCES_CONFIG}" ]] && rm -f "${TMP_SOURCES_CONFIG}"
  [[ -n "${TMP_ENV_FILE}" && -f "${TMP_ENV_FILE}" ]] && rm -f "${TMP_ENV_FILE}"
  return "${status}"
}
trap cleanup EXIT

ensure_python3_with_venv

[[ -f "${SOURCE_ROOT}/config/sources.example.yaml" ]] || die "Missing source config example at ${SOURCE_ROOT}/config/sources.example.yaml"

install_asset "${SOURCE_ROOT}/ops/systemd/market-recorder@.service" "${UNIT_DEST}" 0644 root root
install_asset "${SOURCE_ROOT}/ops/sysusers/market-recorder.conf" "${SYSUSERS_DEST}" 0644 root root
install_asset "${SOURCE_ROOT}/ops/polkit/49-market-recorder.rules" "${POLKIT_DEST}" 0644 root "${POLKIT_GROUP}"

if command_exists systemd-sysusers; then
  run_cmd systemd-sysusers "${SYSUSERS_DEST}"
else
  die "systemd-sysusers is required on this system."
fi

run_cmd install -d -m 0755 -o root -g root /opt
run_cmd install -d -m 0750 -o root -g market-recorder "${CONFIG_ROOT}"

add_operator_to_group "${OPERATOR_USER}"

STAGE_ROOT=$(mktemp -d /opt/CryptoTrader.stage.XXXXXX)
run_cmd install -d -m 0755 -o root -g root "${STAGE_ROOT}"
run_cmd python3 -m venv "${STAGE_ROOT}/.venv"
run_cmd "${STAGE_ROOT}/.venv/bin/python" -m pip install --upgrade pip
run_cmd "${STAGE_ROOT}/.venv/bin/python" -m pip install "${SOURCE_ROOT}"

PACKAGE_VERSION="dry-run"
INSTALLED_AT_UTC="dry-run"
if [[ "${DRY_RUN}" != "1" ]]; then
  PACKAGE_VERSION=$("${STAGE_ROOT}/.venv/bin/python" -c 'import market_recorder; print(market_recorder.__version__)')
  INSTALLED_AT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
fi

write_text_file "${STAGE_ROOT}/install-manifest.json" 0644 root root <<EOF
{
  "app_root": "${APP_ROOT}",
  "installed_at_utc": "${INSTALLED_AT_UTC}",
  "instance": "${INSTANCE}",
  "package_version": "${PACKAGE_VERSION}",
  "source_checkout": "${SOURCE_ROOT}"
}
EOF

if [[ "${DRY_RUN}" == "1" ]]; then
  if [[ -d "${APP_ROOT}" ]]; then
    run_cmd rm -rf "${APP_ROOT}.previous"
    run_cmd mv "${APP_ROOT}" "${APP_ROOT}.previous"
  fi
  run_cmd mv "${STAGE_ROOT}" "${APP_ROOT}"
else
  [[ ! -d "${APP_ROOT}.previous" ]] || rm -rf "${APP_ROOT}.previous"
  if [[ -d "${APP_ROOT}" ]]; then
    mv "${APP_ROOT}" "${APP_ROOT}.previous"
  fi
  mv "${STAGE_ROOT}" "${APP_ROOT}"
  STAGE_ROOT=
  [[ ! -d "${APP_ROOT}.previous" ]] || rm -rf "${APP_ROOT}.previous"
fi

write_text_file "${WRAPPER_DEST}" 0755 root root <<EOF
#!/usr/bin/env bash
set -euo pipefail
export MARKET_RECORDER_LAYOUT=installed
export MARKET_RECORDER_APP_ROOT=${APP_ROOT}
exec ${APP_ROOT}/.venv/bin/python -m market_recorder.cli "\$@"
EOF

TMP_RUNTIME_CONFIG=$(mktemp)
cat >"${TMP_RUNTIME_CONFIG}" <<EOF
runtime:
  environment: production
  timezone: UTC
  data_root: /var/lib/market-recorder/${INSTANCE}
  sources_config: ${SOURCES_DEST}

logging:
  level: INFO
  structured: false

storage:
  format: jsonl.zst
  compression_level: 3
  rotation:
    default:
      max_age_seconds: 3600
      max_bytes: 536870912
    classes:
      high_frequency:
        max_age_seconds: 3600
        max_bytes: 536870912
      medium_frequency:
        max_age_seconds: 21600
        max_bytes: 268435456
      low_frequency:
        max_age_seconds: 86400
        max_bytes: 134217728
      snapshots:
        max_age_seconds: 86400
        max_bytes: 268435456
    stream_classes:
      aster:
        aggTrade: high_frequency
        bookTicker: high_frequency
        markPrice@1s: medium_frequency
        forceOrder: low_frequency
        kline_1m: medium_frequency
        kline_5m: medium_frequency
        kline_15m: medium_frequency
        depth20@100ms: high_frequency
        depth@100ms: high_frequency
        depth_snapshot_1000: snapshots
      pyth:
        price_stream: high_frequency
      tradingview:
        alert: low_frequency
    manual_rotation:
      enabled: false
      require_reason: true
      min_age_seconds: 300
      min_bytes: 1048576
      cooldown_seconds: 300

validation:
  enable_sample_checks: true
EOF
install_preserving_existing "${TMP_RUNTIME_CONFIG}" "${CONFIG_DEST}" 0640 root market-recorder

TMP_SOURCES_CONFIG=$(mktemp)
cp "${SOURCE_ROOT}/config/sources.example.yaml" "${TMP_SOURCES_CONFIG}"
install_preserving_existing "${TMP_SOURCES_CONFIG}" "${SOURCES_DEST}" 0640 root market-recorder

TMP_ENV_FILE=$(mktemp)
cat >"${TMP_ENV_FILE}" <<EOF
MARKET_RECORDER_CONFIG=${CONFIG_DEST}
# Optional overrides.
# MARKET_RECORDER_LOG_LEVEL=INFO
# MARKET_RECORDER_HEALTH_INTERVAL_SECONDS=10
EOF
install_preserving_existing "${TMP_ENV_FILE}" "${ENV_DEST}" 0640 root market-recorder

run_cmd systemctl daemon-reload
systemctl_reload_polkit

if [[ "${DRY_RUN}" != "1" ]]; then
  if ! run_as_service_user market-recorder test -x "${APP_ROOT}"; then
    die "The market-recorder service user cannot access ${APP_ROOT}. Fix the install directory permissions, then rerun install."
  fi
  if ! run_as_service_user market-recorder test -x "${APP_ROOT}/.venv/bin/python"; then
    die "The market-recorder service user cannot execute ${APP_ROOT}/.venv/bin/python. Fix the installed app permissions, then rerun install."
  fi
  if ! run_as_service_user market-recorder test -r "${CONFIG_DEST}"; then
    die "The market-recorder service user cannot read ${CONFIG_DEST}. Fix the installed config permissions, then rerun install."
  fi
  if ! run_as_service_user market-recorder test -r "${SOURCES_DEST}"; then
    die "The market-recorder service user cannot read ${SOURCES_DEST}. Fix the installed config permissions, then rerun install."
  fi
  "${WRAPPER_DEST}" --instance "${INSTANCE}" validate-config --config "${CONFIG_DEST}"
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
log_info "  1. Review ${CONFIG_DEST}, ${SOURCES_DEST}, and ${ENV_DEST}."
log_info "  2. Refresh group membership with 'newgrp market-recorder' or log out and back in."
log_info "  3. Optionally rerun install.sh with --enable to enable boot-time startup."
log_info "  4. Run market-recorder start, status, health, and stop as an unprivileged operator."