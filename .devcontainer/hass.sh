#!/usr/bin/env bash

# The repo root must be importable so Home Assistant's loader can discover the
# custom_components package (it does `import custom_components`).
export PYTHONPATH="${PYTHONPATH}:${PWD}"

hass -c .devcontainer/config --debug
