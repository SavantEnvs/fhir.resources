#!/usr/bin/env bash
#
# mayhem/build.sh — build the fhir.resources atheris fuzz harness (Python).
#
# Runs inside the commit image (mayhem/Dockerfile) as `mayhem` in /mayhem. The org base image
# (ghcr.io/mayhemheroes/base) exports the build contract (CC, SANITIZER_FLAGS, DEBUG_FLAGS, SRC, …)
# and ships python3 + pip + clang.
#
# fhir.resources is fuzzed with Google's atheris (coverage-guided Python fuzzer). atheris emulates
# the libFuzzer CLI, so the harness is a python script. Mayhem, however, requires the target `cmd`
# to be an ELF (it rejects script/wrapper targets), so we build a thin ELF LAUNCHER that execs
# `python3 <harness>.py`, forwarding all libFuzzer args. exec() replaces the process image, so the
# running process IS the atheris/libFuzzer harness — transparent to Mayhem.
#
# Air-gapped (SPEC §6.5): the first (online) run bakes a wheelhouse; the offline PATCH re-run installs
# from it with `--no-index`, so it never reaches PyPI.
set -euo pipefail

# clang rejects SOURCE_DATE_EPOCH='' (empty) — must be unset or a valid integer.
[ -n "${SOURCE_DATE_EPOCH:-}" ] || unset SOURCE_DATE_EPOCH

# Build knobs from the ENVIRONMENT (overridable) with sane defaults. SANITIZER_FLAGS is referenced
# for contract parity; it does not apply to the fuzzed code here — atheris instruments the *Python*
# bytecode at runtime (no compiled project to sanitize). DEBUG_FLAGS carries DWARF (< 4) onto the
# ELF launcher so Mayhem's triage can read it; clang-19's plain -g emits DWARF-5, hence -gdwarf-3.
: "${SANITIZER_FLAGS=-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer}"
: "${DEBUG_FLAGS:=-g -gdwarf-3}"
: "${CC:=clang}"
: "${MAYHEM_JOBS:=$(nproc)}"
export SANITIZER_FLAGS DEBUG_FLAGS CC MAYHEM_JOBS

cd "$SRC"
HARNESS_DIR="$SRC/mayhem"
WHEELHOUSE="$HARNESS_DIR/wheelhouse"
PIP="python3 -m pip"

# 1) Python deps — air-gapped via a baked wheelhouse. First (online) run builds the project wheel +
#    downloads every dependency (incl. atheris) into the wheelhouse; the offline re-run reuses it.
mkdir -p "$WHEELHOUSE"
if [ ! -f "$WHEELHOUSE/.populated" ]; then
  $PIP wheel --wheel-dir "$WHEELHOUSE" "$SRC" atheris
  touch "$WHEELHOUSE/.populated"
fi
# Install offline from the wheelhouse (idempotent: a satisfied requirement is a no-op, no network).
$PIP install --no-index --find-links "$WHEELHOUSE" --user --break-system-packages \
  "fhir.resources" atheris

# 2) Build the single-token ELF launcher that drives the atheris harness (the Mayhem target).
#    DEBUG_FLAGS (-gdwarf-3) keeps DWARF < 4 on the ELF so Mayhem triage can read it.
$CC $DEBUG_FLAGS -gdwarf-3 -O1 \
    -DSCRIPT_PATH="\"$HARNESS_DIR/fuzz_resource_creation.py\"" \
    "$HARNESS_DIR/fuzz_launch.c" -o "$HARNESS_DIR/fuzz_resource_creation"

# 3) Build the ELF launcher for the functional self-test (test.sh runs this — see selftest_launch.c
#    for why the assertion path is routed through a project ELF rather than python3 directly).
$CC -O1 \
    -DSELFTEST_PATH="\"$HARNESS_DIR/selftest.py\"" \
    "$HARNESS_DIR/selftest_launch.c" -o "$HARNESS_DIR/fhir_selftest"

# 4) Fail the build early if the harnessed API drifted (atheris + the package must import cleanly).
python3 -c "import atheris, fhir.resources, fhir_core; from fhir.resources import get_fhir_model_class"

echo ">> build.sh done: $HARNESS_DIR/fuzz_resource_creation (Mayhem target) + $HARNESS_DIR/fhir_selftest"
