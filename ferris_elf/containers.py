import asyncio
import logging
import functools
from typing import Any, Optional, TypeAlias, NamedTuple
import urllib.parse

import docker
import aiohttp as ah
from database import Database, ContainerTag

from config import settings

doc = docker.from_env()

logger = logging.getLogger(__name__)

VolumeDetails: TypeAlias = dict[str, str]
VolumesInfo: TypeAlias = dict[str, VolumeDetails]


async def run_cmd(image: str, cmd: str, env: dict[str, str], vols: VolumesInfo) -> str:
    """
    Thin wrapper to simplify the Docker interface & provide secure defaults.
    """
    loop = asyncio.get_event_loop()
    raw_out = await loop.run_in_executor(
        None,
        functools.partial(
            doc.containers.run,
            image,
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


async def bg_update() -> None:
    """
    Background update task. Run periodically, or metadata about tags in the DB won't be correct.
    Definitely run on startup; startup is when the bench format change will first be noticed.
    """
    logger.info("Starting background update.")
    image = settings.docker.container_ref

    async with ah.ClientSession() as session:
        # TODO: get_remote_tags is supposed to be paginated...
        tags = set(await get_remote_tags(session, image))
        new_versions: set[str] = set()
        with Database() as db:
            new_versions = db.pick_new_container_versions(tags)
        for ver in new_versions:
            logger.info("Loading container version: %s", ver)
            rust_ver = await get_rust_version(image, ver)

            # Version processing
            bench_format = "1"
            _stamp = None
            if "latest" == ver:
                continue
            if "." in ver:
                bench_format, _stamp = ver.split(".")
            else:
                _stamp = ver

            # Save to DB
            with Database() as db:
                # TODO: Figure out something to do with the bench_dir
                db.insert_container_version(rust_ver.ver, ContainerTag(ver), bytes())

    logger.info("Background check finished.")


# --- Utils ---


class RustVersion(NamedTuple):
    ver: str
    hash: str
    date: str


async def get_rust_version(image: str, tag: str) -> RustVersion:
    cmd = "rustc --version"
    out = await run_cmd(image, cmd, {}, {})
    _, ver, git_hash, dstamp = out.split(" ")
    git_hash = git_hash.strip("()")
    dstamp = dstamp.strip("()")
    return RustVersion(ver, git_hash, dstamp)


API_URLs = {
    "ghcr.io": "https://ghcr.io/v2",
    "docker.io": "https://registry.hub.docker.com/v2",
}

AUTH_TOKENS: dict[str, str] = {}


async def docker_hub_auth(session: ah.ClientSession, api_base: str, _repo: str) -> str:
    """Returns a Bearer Token you can use with further Docker Hub API requests."""
    auth_url = "/".join([api_base, "users/login"])
    headers = {"Accept": "application/json"}
    auth_body = {"username": "ferris-elf", "password": settings.docker_auth.token}
    async with session.post(
        auth_url, json=auth_body, raise_for_status=True, headers=headers
    ) as response:
        token = await response.text()
        return "Bearer " + token


async def ghcr_auth_handler(session: ah.ClientSession, _api_base: str, repo: str) -> str:
    logging.info("Asked for github token for repo: %s", repo)
    scope = ":".join(["repo", repo, "pull"])
    url = "https://ghcr.io/token?" + urllib.parse.urlencode({"scope": scope})
    async with session.get(url, raise_for_status=True) as response:
        body = await response.json()
        token: str = body["token"]
        return "Bearer " + token


async def default_auth_handler(_session: ah.ClientSession, _api_base: str, _repo: str) -> str:
    token: str = settings.docker_auth.token
    return "Bearer " + token


async def auth(session: ah.ClientSession, api_base: str, repo: str) -> str:
    if api_base in API_URLs:
        # Callers are expected to delete items from AUTH_TOKENS when they get a 403.
        return AUTH_TOKENS[api_base]

    auth_handlers = {
        "https://registry.hub.docker.com/v2": docker_hub_auth,
        "https://ghcr.io/v2": ghcr_auth_handler,
    }

    handler = auth_handlers.get(api_base, default_auth_handler)

    token = await handler(session, api_base, repo)
    AUTH_TOKENS[api_base] = token
    return token


def _parse_image_ref(image_ref: str) -> urllib.parse.ParseResult:
    user_url = urllib.parse.urlparse(image_ref)

    # The built-in urllib.parse seems to not understand no-scheme URLs.
    if not user_url.scheme:
        user_url = urllib.parse.urlparse("https://" + image_ref)

    return user_url


def _get_api_base(image_ref: str) -> str:
    user_url = _parse_image_ref(image_ref)

    # TODO: Find a way to do this that doesn't rely on lookup tables
    api_base = API_URLs.get(user_url.netloc, None)
    if api_base is None:
        raise ValueError(f"Registry not supported: {image_ref}")

    return api_base


async def get_remote_tags(
    session: ah.ClientSession, image_ref: str, auth_token: Optional[str] = None
) -> list[str]:
    """Use the OCI Distribution API to get a list of tags for an image."""

    user_url = _parse_image_ref(image_ref)
    api_base = _get_api_base(image_ref)
    repo = user_url.path.strip("/")

    target_url = "/".join([api_base, user_url.path, "tags/list"])

    auth_token = auth_token or await auth(session, api_base, repo)
    headers = {
        "Authorization": auth_token,
        "Accept": "application/vnd.docker.distribution.manifest.v2+json",
    }

    async with session.get(target_url, headers=headers, raise_for_status=True) as response:
        # FIXME: We should be expecting at least 404 & 403 here.
        # TODO: This is actually a paginated API. Need `async yield` + multiple requests.
        # Yeah, the typechecker has no way of confirming what's up.
        # The remote API could change at any time. Such is life.
        rv: list[str] = (await response.json())["tags"]
        return rv


async def get_remote_manifest(
    session: ah.ClientSession, image_ref: str, tag: str, auth_token: Optional[str] = None
) -> dict[str, Any]:
    """Retrieve the manifest for a specific tag of an image."""

    user_url = _parse_image_ref(image_ref)
    api_base = _get_api_base(image_ref)
    repo = user_url.path.strip("/")

    target_url = "/".join([api_base, user_url.path, "manifests", tag])

    auth_token = auth_token or await auth(session, api_base, repo)
    headers = {
        "Authorization": auth_token,
        "Accept": "application/vnd.docker.distribution.manifest.v2+json",
    }

    async with session.get(target_url, headers=headers, raise_for_status=True) as response:
        # FIXME: We should be expecting at least 403.
        rv: dict[str, Any] = await response.json()
        return rv


def get_digest_blob_hash(manifest: dict[str, Any]) -> Optional[str]:
    """Get the digest's hash from a manifest. The hash can then be used to get the digest blob."""
    rv: Optional[str] = manifest.get("config", {}).get("digest", None)
    return rv


async def get_remote_blob(
    session: ah.ClientSession, image_ref: str, blob_hash: str, auth_token: Optional[str] = None
) -> dict[str, Any]:
    """Given a blob's hash, retrieve the contents of that blob."""
    user_url = _parse_image_ref(image_ref)
    api_base = _get_api_base(image_ref)
    repo = user_url.path.strip("/")

    target_url = "/".join([api_base, user_url.path, "blobs", blob_hash])

    auth_token = auth_token or await auth(session, api_base, repo)
    headers = {
        "Authorization": auth_token,
        "Accept": "application/vnd.docker.distribution.manifest.v2+json",
    }

    async with session.get(target_url, headers=headers, raise_for_status=True) as response:
        # FIXME: We should be expecting at least 403.
        rv: dict[str, Any] = await response.json()
        return rv


def get_labels(digest_blob: dict[str, Any]) -> dict[str, str]:
    """Given a digest blob, extract the labels from it."""
    rv: dict[str, str] = digest_blob.get("config", {}).get("Labels")
    return rv
