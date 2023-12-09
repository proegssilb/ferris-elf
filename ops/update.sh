#!/usr/bin/bash

CURR_REV=$(git rev-parse --verify HEAD)

# TODO: Once config is moved out of the home dir, reset all contents of the repo before pulling.

git pull

NEW_REV=$(git rev-parse --verify HEAD)

if test "$CURR_REV" != "$NEW_REV"; then
    systemctl --user daemon-reload
    systemctl --user restart ferris-elf-bot.service
fi
