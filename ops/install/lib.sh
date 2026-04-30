#!/usr/bin/env bash

set -euo pipefail

log_info() {
  printf '%s\n' "$*"
}

log_warn() {
  printf 'Warning: %s\n' "$*" >&2
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

ensure_root() {
  [[ "${EUID}" -eq 0 ]] || die "This script must be run with sudo or as root."
}

run_cmd() {
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

install_asset() {
  local src=$1
  local dest=$2
  local mode=$3
  local owner=$4
  local group=$5

  [[ -f "$src" ]] || die "Missing installer asset: $src"
  run_cmd install -D -m "$mode" -o "$owner" -g "$group" "$src" "$dest"
}

write_text_file() {
  local dest=$1
  local mode=$2
  local owner=$3
  local group=$4
  local tmp
  tmp=$(mktemp)
  cat >"$tmp"
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    printf '[dry-run] write %s (%s %s:%s)\n' "$dest" "$mode" "$owner" "$group"
    rm -f "$tmp"
    return 0
  fi
  install -D -m "$mode" -o "$owner" -g "$group" "$tmp" "$dest"
  rm -f "$tmp"
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

detect_polkit_group() {
  if getent group polkitd >/dev/null 2>&1; then
    printf 'polkitd\n'
    return 0
  fi
  printf 'root\n'
}

run_as_service_user() {
  local user=$1
  shift
  if command_exists runuser; then
    runuser -u "$user" -- "$@"
    return $?
  fi
  if command_exists su; then
    su -s /bin/sh "$user" -c "$(printf '%q ' "$@")"
    return $?
  fi
  die "Neither runuser nor su is available for service-user validation."
}

systemctl_reload_polkit() {
  if command_exists systemctl && systemctl list-unit-files polkit.service >/dev/null 2>&1; then
    run_cmd systemctl reload polkit.service
    return 0
  fi
  log_warn "polkit.service was not reloaded automatically; verify the installed rule manually if needed."
}

add_operator_to_group() {
  local operator_user=$1
  [[ -n "$operator_user" ]] || return 0
  [[ "$operator_user" != "root" ]] || return 0
  if id -nG "$operator_user" | tr ' ' '\n' | grep -Fxq market-recorder; then
    return 0
  fi
  run_cmd usermod -a -G market-recorder "$operator_user"
}