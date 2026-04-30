#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

export MARKET_RECORDER_LAYOUT=checkout
export MARKET_RECORDER_REPO_ROOT="${REPO_ROOT}"
unset MARKET_RECORDER_APP_ROOT

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH}"
else
  export PYTHONPATH="${REPO_ROOT}/src"
fi