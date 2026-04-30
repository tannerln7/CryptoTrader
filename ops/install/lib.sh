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

apt_update_once() {
  if [[ "${APT_UPDATED:-0}" == "1" ]]; then
    return 0
  fi
  run_cmd apt-get update
  APT_UPDATED=1
}

ensure_apt_packages() {
  local missing=()
  local package
  for package in "$@"; do
    if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -Fq 'install ok installed'; then
      missing+=("$package")
    fi
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    return 0
  fi

  if ! command_exists apt-get; then
    die "Missing required packages (${missing[*]}), and apt-get is unavailable on this host."
  fi

  apt_update_once
  run_cmd apt-get install -y "${missing[@]}"
}

ensure_python3_with_venv() {
  if ! command_exists python3; then
    ensure_apt_packages python3
  fi

  local probe_dir
  probe_dir=$(mktemp -d)
  if ! python3 -m venv "${probe_dir}/venv" >/dev/null 2>&1; then
    ensure_apt_packages python3-venv
    rm -rf "${probe_dir}"
    probe_dir=$(mktemp -d)
    python3 -m venv "${probe_dir}/venv" >/dev/null 2>&1 || die "python3 -m venv failed even after installing python3-venv."
  fi
  rm -rf "${probe_dir}"
}

install_preserving_existing() {
  local src=$1
  local dest=$2
  local mode=$3
  local owner=$4
  local group=$5

  [[ -f "$src" ]] || die "Missing generated installer asset: $src"

  if [[ ! -f "$dest" ]]; then
    run_cmd install -D -m "$mode" -o "$owner" -g "$group" "$src" "$dest"
    return 0
  fi

  if cmp -s "$src" "$dest"; then
    return 0
  fi

  run_cmd install -D -m "$mode" -o "$owner" -g "$group" "$src" "${dest}.new"
  log_warn "Preserved existing $dest and wrote updated defaults to ${dest}.new"
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