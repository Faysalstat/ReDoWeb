"""Logo / hero uploaded at submission: upload validation + re-encoding
(services/brand_assets_service.py), the multipart submit route's guards,
and how the uploads reach the blueprint and the generator prompt."""

import json
import types
import uuid
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.ai import site_generator
from app.ai.blueprint_extraction import extract_scraped_json
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.main import app
from app.rate_limit import limiter
from app.routers import projects as projects_router
from app.schemas.crawl import CrawlRequest
from app.services import brand_assets_service
from app.services.brand_assets_service import BrandAssetError, process_image_bytes

MB = 1024 * 1024


def _image_bytes(fmt: str, size=(64, 32), mode="RGB", **save_kwargs) -> bytes:
    out = BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else None).save(out, fmt, **save_kwargs)
    return out.getvalue()


def _process(data: bytes, role="logo", max_bytes=5 * MB, max_side=1024):
    return process_image_bytes(data, role, max_bytes=max_bytes, max_side=max_side)


# --- process_image_bytes ------------------------------------------------------


@pytest.mark.parametrize("fmt,ext", [("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")])
def test_accepts_png_jpeg_webp_and_names_file_by_detected_format(fmt, ext):
    result = _process(_image_bytes(fmt))
    assert result.ext == ext
    assert result.filename == f"brand-logo.{ext}"
    assert result.relative_path == f"brand_assets/brand-logo.{ext}"
    assert Image.open(BytesIO(result.data)).format == fmt


def test_extension_follows_content_not_client_filename():
    # A PNG the browser labelled "photo.jpg" is still stored as .png -- the
    # client filename never reaches this function at all.
    assert _process(_image_bytes("PNG"), role="hero").filename == "brand-hero.png"


def test_rejects_svg():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    with pytest.raises(BrandAssetError, match="PNG, JPG or WEBP"):
        _process(svg)


def test_rejects_non_image_bytes_and_gif():
    with pytest.raises(BrandAssetError):
        _process(b"just some text pretending to be a png")
    with pytest.raises(BrandAssetError, match="PNG, JPG or WEBP"):
        _process(_image_bytes("GIF", mode="RGB"))


def test_rejects_empty_and_oversized():
    with pytest.raises(BrandAssetError, match="empty"):
        _process(b"")
    with pytest.raises(BrandAssetError, match="larger than 1 MB"):
        _process(b"x" * (MB + 1), max_bytes=MB)


def test_rejects_huge_pixel_dimensions(monkeypatch):
    monkeypatch.setattr(brand_assets_service, "MAX_PIXELS", 100)
    with pytest.raises(BrandAssetError, match="dimensions"):
        _process(_image_bytes("PNG", size=(20, 20)))


def test_strips_exif_and_downscales():
    exif = Image.Exif()
    exif[0x010F] = "SecretCameraMaker"  # Make
    data = _image_bytes("JPEG", size=(4000, 1000), exif=exif.tobytes())
    assert Image.open(BytesIO(data)).getexif().get(0x010F) == "SecretCameraMaker"

    result = _process(data, role="hero", max_side=2560)
    out = Image.open(BytesIO(result.data))
    assert len(out.getexif()) == 0
    assert out.size == (2560, 640)


def test_png_with_transparency_stays_png():
    result = _process(_image_bytes("PNG", mode="RGBA"))
    assert Image.open(BytesIO(result.data)).mode == "RGBA"


def test_missing_roles():
    assert brand_assets_service.missing_roles(False, False, later=False) == ["logo", "hero"]
    assert brand_assets_service.missing_roles(True, False, later=False) == ["hero"]
    assert brand_assets_service.missing_roles(False, False, later=True) == []
    assert brand_assets_service.missing_roles(True, True, later=False) == []


def test_save_and_find_replace_earlier_upload(tmp_path):
    first = _process(_image_bytes("PNG"))
    second = _process(_image_bytes("JPEG"))
    assert brand_assets_service.save(tmp_path, first) == "brand_assets/brand-logo.png"
    assert brand_assets_service.save(tmp_path, second) == "brand_assets/brand-logo.jpg"
    assert sorted(p.name for p in (tmp_path / "brand_assets").iterdir()) == ["brand-logo.jpg"]
    assert brand_assets_service.find(tmp_path, "logo") == "brand_assets/brand-logo.jpg"
    assert brand_assets_service.find(tmp_path, "hero") is None


# --- multipart route guards (fail before any DB work) ------------------------


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(limiter, "enabled", False)
    db = MagicMock()

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: types.SimpleNamespace(id=uuid.uuid4(), is_admin=False)
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


URL = "/api/v1/projects/with-brand-assets"
FORM = {"url": "https://example.com", "tos_accepted": "true"}


def test_route_requires_both_files_without_later_box(client):
    http, db = client
    files = {"logo": ("logo.png", _image_bytes("PNG"), "image/png")}
    res = http.post(URL, data={**FORM, "brand_assets_later": "false"}, files=files)
    assert res.status_code == 422
    assert "a hero image" in res.json()["detail"]
    db.add.assert_not_called()


def test_route_rejects_svg_upload(client):
    http, db = client
    files = {
        "logo": ("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "image/svg+xml"),
        "hero": ("hero.png", _image_bytes("PNG"), "image/png"),
    }
    res = http.post(URL, data=FORM, files=files)
    assert res.status_code == 422
    assert res.json()["detail"].startswith("Logo:")
    db.add.assert_not_called()


def test_route_rejects_invalid_url(client):
    http, db = client
    res = http.post(URL, data={"url": "not a url", "tos_accepted": "true", "brand_assets_later": "true"})
    assert res.status_code == 422
    db.add.assert_not_called()


def test_route_rejects_oversized_body_before_reading(client, monkeypatch):
    monkeypatch.setenv("REDOWEBS_BRAND_ASSET_MAX_BYTES", "1000")
    projects_router.get_settings.cache_clear()
    http, db = client
    files = {"logo": ("logo.png", b"x" * (3 * MB), "image/png")}
    res = http.post(URL, data={**FORM, "brand_assets_later": "true"}, files=files)
    assert res.status_code == 413
    db.add.assert_not_called()


# --- _create_project's before_commit hook -----------------------------------


@pytest.fixture
def create_env(monkeypatch, tmp_path):
    monkeypatch.setenv("REDOWEBS_STORAGE_ROOT", str(tmp_path))
    projects_router.get_settings.cache_clear()
    monkeypatch.setattr(projects_router.storage_capacity_service, "check_free_disk_space", lambda: None)
    monkeypatch.setattr(
        projects_router.wallet_service, "get_or_create_wallet", lambda db, uid: types.SimpleNamespace(balance=10)
    )
    monkeypatch.setattr(projects_router.tier_service, "get_enabled_tiers", lambda: [])
    enqueued = []
    monkeypatch.setattr(projects_router, "enqueue", lambda db, name, payload: enqueued.append(name))

    db = MagicMock()
    added = []
    db.add.side_effect = added.append

    def _flush():
        for obj in added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    db.flush.side_effect = _flush
    request = types.SimpleNamespace(client=types.SimpleNamespace(host="127.0.0.1"), headers={})
    user = types.SimpleNamespace(id=uuid.uuid4())
    return types.SimpleNamespace(db=db, request=request, user=user, enqueued=enqueued, root=tmp_path, added=added)


def test_before_commit_failure_rolls_back_and_removes_files(create_env):
    image = _process(_image_bytes("PNG"))

    def _attach(project):
        brand_assets_service.save(create_env.root / "projects" / str(project.id), image)
        raise OSError("disk full")

    payload = CrawlRequest(url="https://example.com", tos_accepted=True)
    with pytest.raises(OSError):
        projects_router._create_project(create_env.db, create_env.request, create_env.user, payload, _attach)

    create_env.db.rollback.assert_called_once()
    create_env.db.commit.assert_not_called()
    assert create_env.enqueued == []
    assert list((create_env.root / "projects").iterdir()) == []


def test_before_commit_success_commits_then_enqueues(create_env):
    seen = {}

    def _attach(project):
        seen["id"] = project.id
        project.brand_assets_later = True

    payload = CrawlRequest(url="https://example.com", tos_accepted=True)
    res = projects_router._create_project(create_env.db, create_env.request, create_env.user, payload, _attach)
    assert res.project_id == str(seen["id"])
    assert create_env.enqueued == ["run_crawl"]
    create_env.db.rollback.assert_not_called()


# --- extraction + generator ----------------------------------------------------


HOMEPAGE = """<html><head><title>Acme Bakery</title>
<style>body { color: #112233; } a { color: #445566; } .x { background: #778899; }</style></head>
<body><header><img src="/logo.png" alt="Acme logo"></header>
<h1>Fresh bread daily</h1><p>Baked every morning.</p><img src="/hero.jpg" alt="bread">
<h2>About us</h2><p>We bake.</p></body></html>"""


def _make_crawled_project(root: Path) -> Path:
    (root / "snapshot" / "pages").mkdir(parents=True)
    (root / "snapshot" / "assets").mkdir(parents=True)
    (root / "snapshot" / "pages" / "index.html").write_text(HOMEPAGE, encoding="utf-8")
    (root / "snapshot" / "assets" / "aaaa1111-logo.png").write_bytes(_image_bytes("PNG"))
    (root / "snapshot" / "assets" / "bbbb2222-hero.jpg").write_bytes(_image_bytes("JPEG"))
    metadata = {
        "source_url": "https://acme.example/",
        "pages": [{"url": "https://acme.example/", "storage_path": "snapshot/pages/index.html"}],
        "assets": [
            {
                "original_url": "https://acme.example/logo.png",
                "storage_path": "snapshot/assets/aaaa1111-logo.png",
                "asset_type": "image",
            },
            {
                "original_url": "https://acme.example/hero.jpg",
                "storage_path": "snapshot/assets/bbbb2222-hero.jpg",
                "asset_type": "image",
            },
        ],
    }
    (root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return root


def test_extraction_uses_crawled_images_without_uploads(tmp_path):
    doc = extract_scraped_json(_make_crawled_project(tmp_path))
    assert doc.meta.logo == "snapshot/assets/aaaa1111-logo.png"
    assert doc.pages[0].sections.hero.background_image != "brand_assets/brand-hero.jpg"


def test_extraction_prefers_uploaded_logo_and_hero(tmp_path):
    root = _make_crawled_project(tmp_path)
    brand_assets_service.save(root, _process(_image_bytes("PNG"), role="logo"))
    brand_assets_service.save(root, _process(_image_bytes("JPEG"), role="hero"))
    doc = extract_scraped_json(root)
    assert doc.meta.logo == "brand_assets/brand-logo.png"
    assert doc.pages[0].sections.hero.background_image == "brand_assets/brand-hero.jpg"


def test_extraction_logo_only_upload_keeps_crawled_hero(tmp_path):
    root = _make_crawled_project(tmp_path)
    baseline_hero = extract_scraped_json(root).pages[0].sections.hero.background_image
    brand_assets_service.save(root, _process(_image_bytes("PNG"), role="logo"))
    doc = extract_scraped_json(root)
    assert doc.meta.logo == "brand_assets/brand-logo.png"
    assert doc.pages[0].sections.hero.background_image == baseline_hero


def test_copy_images_includes_brand_assets(tmp_path):
    root = _make_crawled_project(tmp_path / "project")
    brand_assets_service.save(root, _process(_image_bytes("PNG"), role="logo"))
    out = tmp_path / "out"
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    names = site_generator._copy_images(root, out, metadata["assets"])
    assert "brand-logo.png" in names
    assert (out / "images" / "brand-logo.png").is_file()


def test_prompt_names_brand_images_only_when_uploaded(tmp_path):
    root = _make_crawled_project(tmp_path)
    assert site_generator._brand_images_block(root) == ""
    assert site_generator._build_user_message("design", ["a.png"], "") == site_generator._build_user_message(
        "design", ["a.png"]
    )

    brand_assets_service.save(root, _process(_image_bytes("JPEG"), role="hero"))
    block = site_generator._brand_images_block(root)
    assert "Hero image: images/brand-hero.jpg" in block
    assert "Logo:" not in block
    assert site_generator._brand_images_block(root, include_hero=False) == ""
    assert block in site_generator._build_user_message("design", ["brand-hero.jpg"], block)
