"""Logo / hero image the user uploads at submission.

The files live at projects/{id}/brand_assets/brand-{logo|hero}.{ext}. The
pipeline finds them on disk, so the extractor and generator stay DB-free:
blueprint_extraction.extract_scraped_json prefers them over its own
logo/hero picks, and site_generator copies them into images/ and names them
in the prompt.

Every upload is re-encoded, never stored as received:
- only PNG / JPEG / WEBP are accepted, judged from what Pillow detects (never
  the filename or content-type);
- SVG is rejected on purpose, because /preview serves files from the app's own
  origin and an SVG can carry script;
- EXIF (incl. GPS) is dropped and the orientation is applied;
- images are downscaled to brand_{logo,hero}_max_side_px;
- the stored filename is always built here, never taken from the client (this
  repo has had path-traversal bugs in file-writing code before).
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

BRAND_ASSETS_DIR = "brand_assets"
ROLES = ("logo", "hero")
_EXT_BY_FORMAT = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}
# Far above any real logo/hero, far below what a decompression bomb needs.
MAX_PIXELS = 40_000_000


class BrandAssetError(ValueError):
    """The upload can't be used; the message is safe to show the user."""


@dataclass(frozen=True)
class ProcessedImage:
    role: str
    data: bytes
    ext: str

    @property
    def filename(self) -> str:
        return f"brand-{self.role}.{self.ext}"

    @property
    def relative_path(self) -> str:
        return f"{BRAND_ASSETS_DIR}/{self.filename}"


def _label(role: str) -> str:
    return "Logo" if role == "logo" else "Hero image"


def process_image_bytes(data: bytes, role: str, *, max_bytes: int, max_side: int) -> ProcessedImage:
    """Validates and re-encodes one upload. Raises BrandAssetError."""
    if role not in ROLES:
        raise ValueError(f"Unknown brand asset role {role!r}")
    label = _label(role)
    if not data:
        raise BrandAssetError(f"{label}: the file is empty.")
    if len(data) > max_bytes:
        raise BrandAssetError(f"{label}: the file is larger than {max_bytes // (1024 * 1024)} MB.")

    try:
        with Image.open(BytesIO(data)) as source:
            fmt = source.format
            ext = _EXT_BY_FORMAT.get(fmt or "")
            if ext is None:
                raise BrandAssetError(f"{label}: please upload a PNG, JPG or WEBP image.")
            width, height = source.size
            if width * height > MAX_PIXELS:
                raise BrandAssetError(f"{label}: the image dimensions are too large.")
            source.load()
            image = ImageOps.exif_transpose(source)
    except BrandAssetError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise BrandAssetError(f"{label}: please upload a PNG, JPG or WEBP image.") from exc

    if max(image.size) > max_side:
        image.thumbnail((max_side, max_side), Image.LANCZOS)

    icc_profile = image.info.get("icc_profile")
    # Nothing from the original metadata is carried over except the colour
    # profile -- this is what drops EXIF/GPS and PNG text chunks.
    image.info = {}
    out = BytesIO()
    if fmt == "JPEG":
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        image.save(out, "JPEG", quality=88, optimize=True, exif=b"", icc_profile=icc_profile)
    elif fmt == "PNG":
        image.save(out, "PNG", optimize=True, icc_profile=icc_profile)
    else:
        image.save(out, "WEBP", quality=88, exif=b"", icc_profile=icc_profile)
    return ProcessedImage(role=role, data=out.getvalue(), ext=ext)


def missing_roles(logo_present: bool, hero_present: bool, later: bool) -> list[str]:
    """Roles the user still has to upload. Without the "I'll change them
    later" box both are required; with it, each one is optional."""
    if later:
        return []
    return [role for role, present in (("logo", logo_present), ("hero", hero_present)) if not present]


def save(project_root: Path, image: ProcessedImage) -> str:
    """Writes the processed image and returns its project-root-relative path.
    Any earlier upload for the same role (other extension) is removed."""
    target_dir = project_root / BRAND_ASSETS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    for old in target_dir.glob(f"brand-{image.role}.*"):
        old.unlink()
    (target_dir / image.filename).write_bytes(image.data)
    return image.relative_path


def find(project_root: Path, role: str) -> str | None:
    """Project-root-relative path of the uploaded file for `role`, or None."""
    target_dir = project_root / BRAND_ASSETS_DIR
    if not target_dir.is_dir():
        return None
    for ext in _EXT_BY_FORMAT.values():
        candidate = target_dir / f"brand-{role}.{ext}"
        if candidate.is_file():
            return f"{BRAND_ASSETS_DIR}/{candidate.name}"
    return None
