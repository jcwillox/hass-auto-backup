#!/usr/bin/env bash

export PYTHONPATH="${PYTHONPATH}:${PWD}/custom_components"

hass -c .devcontainer/config --debug
