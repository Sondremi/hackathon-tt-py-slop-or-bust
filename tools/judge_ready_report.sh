#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TESTS_JSON="$ROOT_DIR/evaluate/scoring/results/tests_latest.json"
QUALITY_JSON="$ROOT_DIR/evaluate/scoring/results/latest.json"
CHECKS_JSON="$ROOT_DIR/evaluate/checks/results/latest.json"

echo "=== Judge Ready Report ==="
echo "Repository: $(basename "$ROOT_DIR")"
echo "Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo

if [[ -f "$TESTS_JSON" ]]; then
  /usr/bin/env python3 - <<'PY'
import json
from pathlib import Path
p = Path("evaluate/scoring/results/tests_latest.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("Tests")
print(f"  Passed: {d.get('n_passed', 0)}/{d.get('n_total', 0)}")
print(f"  Weighted test score: {d.get('percentage', 0.0)}/100")
PY
else
  echo "Tests"
  echo "  No tests_latest.json found. Run: make evaluate_tt_ghostfolio"
fi

echo
if [[ -f "$QUALITY_JSON" ]]; then
  /usr/bin/env python3 - <<'PY'
import json
from pathlib import Path
p = Path("evaluate/scoring/results/latest.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("Code Quality")
print(f"  Weighted quality score: {d.get('weighted_score', 0.0)}/100")
print(f"  Weighted grade: {d.get('weighted_grade', 'N/A')}")
t = d.get("translated_code", {})
print(f"  Translated health: {t.get('health_score', 0)}/100")
print(f"  Translated complexity score: {t.get('complexity_score', 0)}/100")
print(f"  Translated average complexity: {t.get('average_complexity', 0)}")
PY
else
  echo "Code Quality"
  echo "  No latest.json found. Run: make evaluate_tt_ghostfolio"
fi

echo
if [[ -f "$CHECKS_JSON" ]]; then
  /usr/bin/env python3 - <<'PY'
import json
from pathlib import Path
p = Path("evaluate/checks/results/latest.json")
d = json.loads(p.read_text(encoding="utf-8"))
print("Rule Compliance")
print(f"  Legal: {d.get('legal', False)}")
print(f"  Failures: {d.get('failures', 'N/A')}")
PY
else
  echo "Rule Compliance"
  echo "  No checks results found. Run: make detect_rule_breaches"
fi

echo
echo "Recent commits"
git -C "$ROOT_DIR" log --oneline -n 6

echo
echo "Judge talking points"
echo "  1. Explain wrapper/implementation split and why wrapper remains unchanged."
echo "  2. Walk through activity replay (BUY/SELL/short/dividend/fees)."
echo "  3. Show deterministic validation loop: translate -> tests -> quality -> rule checks."
echo "  4. Highlight trade-offs: correctness and explainability over generic TS transpilation."
