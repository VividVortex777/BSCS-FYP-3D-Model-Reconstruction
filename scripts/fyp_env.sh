#!/bin/bash
# Shared environment for every FYP shell script. Source it, do not execute it:
#
#   source "$(dirname "${BASH_SOURCE[0]}")/fyp_env.sh"          # from scripts/
#   source "$(dirname "${BASH_SOURCE[0]}")/scripts/fyp_env.sh"  # from repo root
#
# FYP_ROOT  project root. Defaults to the clone this file lives in, so the
#           repository works from any location and for any user.
# FYP_PY    Python interpreter that has torch/FastAPI/OpenCV (backend, MiDaS,
#           reconstruction). First match wins: explicit FYP_PY, the project
#           venv, the legacy conda env, then the system python3.
#
# Both can be overridden by exporting them before running a script.

if [ -z "${FYP_ROOT:-}" ]; then
    FYP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
export FYP_ROOT

if [ -z "${FYP_PY:-}" ]; then
    for _fyp_cand in "$FYP_ROOT/venv/bin/python" \
                     "$HOME/miniconda3/envs/fyp/bin/python"; do
        if [ -x "$_fyp_cand" ]; then
            FYP_PY="$_fyp_cand"
            break
        fi
    done
    unset _fyp_cand
    FYP_PY="${FYP_PY:-$(command -v python3)}"
fi
export FYP_PY
