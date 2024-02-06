import os.path

from dynaconf import Dynaconf, Validator

CONF_DIR = os.path.join(os.path.expanduser("~"), ".config", "ferris-elf")

settings = Dynaconf(
    envvar_prefix="FERRIS_ELF",
    merge_enable=True,
    settings_files=[
        "settings.toml",
        ".secrets.toml",
        os.path.join(CONF_DIR, "settings.toml"),
        os.path.join(CONF_DIR, "secrets.toml"),
    ],
    validators=[
        Validator("discord.bot_token", must_exist=True),
        Validator("discord.owner_id", must_exist=True, cast=int),
        Validator("db.filename", must_exist=True),
        Validator("discord.support_info", must_exist=True),
        Validator("discord.rust_version_info", must_exist=True),
        Validator("discord.hw_info", must_exist=True),
        Validator("discord.management_servers", must_exist=True, len_min=1),
        Validator("aoc.inputs_dir", must_exist=True),
        Validator("docker.container_ref", must_exist=True),
        Validator("aoc_auth.tokens", must_exist=True, len_min=1),
    ],
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
