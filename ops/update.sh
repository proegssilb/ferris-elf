#!/usr/bin/bash
# This script runs periodically on a timer to check for 
# any updates to the upstream git repository

git fetch

CURR_REV=$(git rev-parse --verify HEAD)
REMOTE_REV=$(git rev-parse --verify HEAD@{u})    # https://stackoverflow.com/a/46516201/1819694

# Contents inside of this block are run when the remote git repo has changed
if test "$CURR_REV" != "$REMOTE_REV"; then
    systemctl --user stop ferris-elf-bot.service
    # TODO: Discard all changes to the repo
    git pull
    poetry run python dbmate.py up
    systemctl --user daemon-reload
    systemctl --user start ferris-elf-bot.service
fi
