#!/usr/bin/bash

CURR_REV=$(git rev-parse --verify HEAD)
REMOTE_REV=$(git rev-parse --verify HEAD@{u})    # https://stackoverflow.com/a/46516201/1819694

if test "$CURR_REV" != "$REMOTE_REV"; then
    systemctl --user stop ferris-elf-bot.service
    # TODO: Discard all changes to the repo
    git pull
    systemctl --user daemon-reload
    systemctl --user start ferris-elf-bot.service
fi
