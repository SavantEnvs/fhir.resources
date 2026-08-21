# syntax=docker/dockerfile:1.7
#
# Commit-image Dockerfile for fhir.resources (Python / atheris), built ON TOP of the org base
# image (ghcr.io/savantenvs/base) which provides debian + clang/llvm + python3 + pip + the
# non-root identities + the build-contract ENV. mayhem/build.sh installs the package + atheris
# from a baked wheelhouse (air-gapped) and compiles the thin ELF launcher targets.
#
# Build (from the repo root):
#   DOCKER_BUILDKIT=1 docker build -f mayhem/Dockerfile \
#       --build-arg COMMIT=$(git rev-parse HEAD) -t fhir-resources-commit:test .

FROM ghcr.io/savantenvs/base:20260621

ARG COMMIT
ARG REPO_URL
# SOURCE_DATE_EPOCH stays an ARG (available to build.sh); never baked as ENV — an empty value
# breaks clang. build.sh unsets it when empty.
ARG SOURCE_DATE_EPOCH
# Sanitizer override knob (undefaulted so the base ENV flows through unless overridden).
ARG SANITIZER_FLAGS
# Build parallelism (optional; build.sh falls back to nproc).
ARG MAYHEM_JOBS=

# Source enters from the build CONTEXT (the CI checkout): the FULL repo (incl. .git history) is
# copied to /mayhem as `mayhem`; build.sh builds in place and installs python deps to ~/.local.
USER mayhem
WORKDIR /mayhem
COPY --chown=2000:2000 . /mayhem

RUN bash mayhem/build.sh

# Run the functional self-test at build time — a failing suite fails the image build.
RUN if [ -f mayhem/test.sh ]; then bash mayhem/test.sh; else echo "no mayhem/test.sh"; fi

LABEL org.opencontainers.image.source="${REPO_URL}" \
      org.opencontainers.image.revision="${COMMIT}" \
      rlenv.tier="commit" \
      rlenv.source_date_epoch="${SOURCE_DATE_EPOCH}" \
      rlenv.user="mayhem"

USER mayhem
WORKDIR /mayhem
