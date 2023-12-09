#!/usr/bin/bash

# https://stackoverflow.com/a/246128
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

pushd $SCRIPT_DIR

systemctl --user link ./systemd/ferris-elf-bot.service
systemctl --user link ./systemd/ferris-elf-fetch.service
systemctl --user link ./systemd/ferris-elf-update.service
systemctl --user link ./systemd/ferris-elf-fetch.timer
systemctl --user link ./systemd/ferris-elf-update.timer

popd
