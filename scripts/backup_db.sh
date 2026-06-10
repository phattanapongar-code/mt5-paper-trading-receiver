#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
ts=$(date +%Y%m%d_%H%M%S)
cp data/receiver.sqlite3 "backups/receiver_${ts}.sqlite3"
echo "backup: backups/receiver_${ts}.sqlite3"
