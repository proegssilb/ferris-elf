import logging
import functools
import asyncio

import docker

from config import settings

doc = docker.from_env()

logger = logging.getLogger(__name__)

async def run_cmd(cmd: str, env: dict[str, str], vols: dict[str, dict[str, str]]) -> str:
    """
    Thin wrapper to simplify the Docker interface & provide secure defaults.
    """
    loop = asyncio.get_event_loop()
    raw_out = await loop.run_in_executor(
        None,
        functools.partial(
            doc.containers.run,
            settings.docker.container_ref,
            cmd,
            environment=env,
            remove=True,
            stdout=True,
            stderr=True,
            mem_limit="8g",
            network_mode="none",
            volumes=vols,
        ),
    )
    out: str = raw_out.decode("utf-8")
    return out


def get_remote_tags(image_ref: str):
    """Use the OCI Distribution API to get a list of tags for an image."""
    raise NotImplementedError()

def get_remote_manifest(image_ref: str, tag: str):
    """Retrieve the manifest for a specific tag of an image."""
    raise NotImplementedError()

def get_labels(image_manifest: str):
    """Given a manifest, extract the labels from it."""
    raise NotImplementedError
