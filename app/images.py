"""Image type detection for uploads.

Sniffs magic bytes rather than trusting the multipart part's Content-Type
header: HTTP clients frequently send ``application/octet-stream`` for an
uploaded file (Dio, the Flutter client, does unless told otherwise), and a
header the client sets is a claim about the file, not evidence of what it is.
"""

# Extensions this module can recognise, for callers to restrict against.
PNG = ".png"
JPEG = ".jpg"
WEBP = ".webp"


def detect_image_extension(contents: bytes) -> str | None:
    """Return the file extension for known image bytes, else None."""
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if contents.startswith(b"\xff\xd8\xff"):
        return JPEG
    # WEBP is a RIFF container: "RIFF" <4-byte size> "WEBP".
    if contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return WEBP
    return None
