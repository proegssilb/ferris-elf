import os.path

from dynaconf import Dynaconf, Validator

CONF_DIR = os.path.join(os.path.expanduser("~"), ".config", "ferris-elf")

settings = Dynaconf(
    envvar_prefix="FERRIS_ELF",
    settings_files=["settings.toml", ".secrets.toml", os.path.join(CONF_DIR, "settings.toml"), os.path.join("secrets.toml")],
    validators=[Validator("discord.bot_token", must_exist=True)],
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
