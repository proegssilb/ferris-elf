
from dynaconf import Dynaconf, Validator

settings = Dynaconf(
    envvar_prefix="FERRIS_ELF",
    settings_files=['settings.toml', '.secrets.toml'],
    validators=[
        Validator("discord.bot_token",must_exist=True)
    ]
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
