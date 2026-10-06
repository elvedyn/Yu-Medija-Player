#!/usr/bin/env bash
# Copy staged Yu Medija Player install into ~/.local (run outside sandbox if needed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/scripts/install_linux.sh"
