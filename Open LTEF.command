#!/bin/zsh
cd "$(dirname "$0")" || exit 1
python3 -m ltef.webapp --open
