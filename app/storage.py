"""Image storage on Cloudinary.

The app server's own disk is not durable — Render wipes it on every deploy and
whenever the free instance sleeps — so uploaded images live on Cloudinary and
the database stores their absolute CDN URL.

Everything Cloudinary-specific is confined to this module: swapping providers
means rewriting this file and nothing else.
"""

import logging
from urllib.parse import urlsplit

import cloudinary
import cloudinary.uploader

from .config import settings

logger = logging.getLogger("glamira.storage")

# Folders inside the Cloudinary media library.
PARLOR_FOLDER = "glamira/parlors"
AVATAR_FOLDER = "glamira/avatars"


class StorageError(Exception):
    """Raised when an image can't be stored or removed."""


def is_configured() -> bool:
    return bool(settings.cloudinary_url)


def _configure() -> None:
    """Point the SDK at the account in CLOUDINARY_URL.

    Parsed explicitly rather than letting the SDK read the environment, so the
    value always comes from settings (and therefore from .env in development).
    """
    parts = urlsplit(settings.cloudinary_url or "")
    cloudinary.config(
        cloud_name=parts.hostname,
        api_key=parts.username,
        api_secret=parts.password,
        secure=True,
    )


def _public_id(folder: str, owner_id: str) -> str:
    """One image per owner, at a stable id.

    Re-uploading overwrites in place, so old files can't pile up orphaned, and
    removal doesn't need the previous URL to work out what to delete.
    """
    return f"{folder}/{owner_id}"


def upload_image(contents: bytes, *, folder: str, owner_id: str) -> str:
    """Store `contents` and return its absolute CDN URL."""
    if not is_configured():
        raise StorageError("Image storage is not configured on the server.")
    _configure()

    try:
        result = cloudinary.uploader.upload(
            contents,
            public_id=_public_id(folder, owner_id),
            resource_type="image",
            overwrite=True,
            # Drop the old file from the CDN edges, otherwise a replaced image
            # can keep serving until the cached copy expires.
            invalidate=True,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean 502 upstream
        logger.exception("Cloudinary upload failed for %s", owner_id)
        raise StorageError("Could not store the image. Please try again.") from exc

    # secure_url carries a /v<version>/ segment, so the URL changes on every
    # upload and clients never show a stale picture from cache.
    url = result.get("secure_url")
    if not url:
        raise StorageError("Image storage returned no URL.")
    return url


def delete_image(*, folder: str, owner_id: str) -> None:
    """Best-effort removal. Never raises: the database row is the source of
    truth, and a leftover file is harmless compared with a failed request."""
    if not is_configured():
        return
    _configure()
    try:
        cloudinary.uploader.destroy(
            _public_id(folder, owner_id),
            resource_type="image",
            invalidate=True,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Cloudinary delete failed for %s", owner_id)
