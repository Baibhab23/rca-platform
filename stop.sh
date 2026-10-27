#!/usr/bin/env bash
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDS_FILE="$PROJECT_ROOT/.pids"

if [[ ! -f "$PIDS_FILE" ]]; then
  echo "No running services found (.pids file missing)."
  exit 0
fi

echo "Stopping RCA platform services..."
while IFS= read -r pid; do
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" && echo "  Stopped PID $pid"
  fi
done < "$PIDS_FILE"

rm -f "$PIDS_FILE"
echo "Done."
