#!/usr/bin/env bash
# POSIX launcher for the StepFun image CLI.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python -m stepfun_image.cli "$@"
