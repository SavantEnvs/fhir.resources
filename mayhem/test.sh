#!/usr/bin/env bash
#
# mayhem/test.sh — RUN the fhir.resources functional self-test that mayhem/build.sh produced.
# Behavioral oracle: asserts that fhir.resources parses, validates, rejects bad input, and
# round-trips known resources to specific values. A no-op/exit(0) PATCH FAILS this (the expected
# SELFTEST_PASS marker + values are absent). Emits a CTRF (https://ctrf.io) summary.
set -uo pipefail
[ -n "${SOURCE_DATE_EPOCH:-}" ] || unset SOURCE_DATE_EPOCH
cd "$SRC"

SELFTEST="$SRC/mayhem/fhir_selftest"

emit_ctrf() {
  local tool="$1" passed="$2" failed="$3" skipped="${4:-0}" pending="${5:-0}" other="${6:-0}"
  local tests=$(( passed + failed + skipped + pending + other ))
  cat > "${CTRF_REPORT:-$SRC/ctrf-report.json}" <<JSON
{
  "results": {
    "tool": { "name": "$tool" },
    "summary": {
      "tests": $tests,
      "passed": $passed,
      "failed": $failed,
      "pending": $pending,
      "skipped": $skipped,
      "other": $other
    }
  }
}
JSON
  printf 'CTRF {"results":{"tool":{"name":"%s"},"summary":{"tests":%d,"passed":%d,"failed":%d,"pending":%d,"skipped":%d,"other":%d}}}\n' \
    "$tool" "$tests" "$passed" "$failed" "$pending" "$skipped" "$other"
  [ "$failed" -eq 0 ]
}

if [ ! -x "$SELFTEST" ]; then
  echo "FAIL: $SELFTEST missing — mayhem/build.sh did not build the self-test" >&2
  emit_ctrf "fhir-selftest" 0 1
  exit 1
fi

# The self-test asserts behavior internally and prints a marker carrying the asserted values ONLY
# when every assertion holds; any failure (or a neutered binary) yields no marker.
out="$("$SELFTEST" 2>&1)"; rc=$?
echo "$out"

passed=0; failed=0
if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -q 'SELFTEST_PASS patient_gender=male org_name=Acme'; then
  passed=1
else
  failed=1
  echo "FAIL: fhir.resources self-test did not assert the expected behavior (rc=$rc)" >&2
fi

emit_ctrf "fhir-selftest" "$passed" "$failed"
