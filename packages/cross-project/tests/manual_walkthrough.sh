#!/usr/bin/env bash
set -euo pipefail

package_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT

mkdir -p "$fixture/projects/alpha"
cli=(python3 -B "$package_dir/scripts/cross_project.py")

"${cli[@]}" bom-dia --root "$fixture"
"${cli[@]}" hq-init --root "$fixture" --dry-run \
  --front alpha --name "Alpha" --path projects/alpha \
  --role "Produces the shared component" --next "Build the first slice"
test ! -e "$fixture/harness.config.json"
"${cli[@]}" hq-init --root "$fixture" \
  --front alpha --name "Alpha" --path projects/alpha \
  --role "Produces the shared component" --next "Build the first slice"
"${cli[@]}" hq-sync --root "$fixture"
"${cli[@]}" digere --root "$fixture" --front alpha --scope coordination
"${cli[@]}" registra --root "$fixture" --front alpha \
  --state active --next "Validate the first slice"
"${cli[@]}" encerra --root "$fixture" --front alpha \
  --role "Produces the shared component" --state ready \
  --next "Hand off the component" --summary "First slice validated" \
  --reflect-when "The shared interface changes"
"${cli[@]}" bom-dia --root "$fixture" --front alpha
"${cli[@]}" hq-sync --root "$fixture"

python3 - "$fixture/harness.config.json" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
front = state["fronts"]["alpha"]
assert front["coordinationPending"] is False
assert front["next"] == "Hand off the component"
print("manual walkthrough: PASS")
PY
