import pytest

from app.models import PromptTemplate, User
from app.services import prompt_template_service as svc


def _make_admin(db_session):
    admin = User(email="prompt-admin@example.com", is_email_verified=True, is_admin=True)
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def fake_prompts_dir(tmp_path, monkeypatch):
    """Redirects the module's PROMPTS_DIR to an isolated tmp_path so tests
    never touch the real backend/prompts/ directory."""
    monkeypatch.setattr(svc, "PROMPTS_DIR", tmp_path)
    return tmp_path


# -- sanitize_template_name -------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "../../etc/passwd",
        "..\\..\\windows",
        "",
        "   ",
        "a/b",
        "a\\b",
        "..",
        ".",
        "name\x00.txt",
        "a" * 100,
    ],
)
def test_sanitize_template_name_rejects_unsafe_input(raw):
    with pytest.raises(ValueError):
        svc.sanitize_template_name(raw)


@pytest.mark.parametrize("raw", ["business", "modernDark", "vibrant-friendly", "my_template", "name.txt"])
def test_sanitize_template_name_accepts_safe_names(raw):
    result = svc.sanitize_template_name(raw)
    assert result
    assert not result.lower().endswith(".txt")


# -- save_uploaded_template --------------------------------------------------


def test_save_uploaded_template_writes_file_and_row(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)

    row = svc.save_uploaded_template(
        db_session, category="business", raw_name="newstyle", content=b"be bold", admin_id=admin.id
    )
    db_session.commit()

    assert row.filename == "business_newstyle_prompt.txt"
    assert row.category == "business"
    assert row.is_active is True
    assert (fake_prompts_dir / "business_newstyle_prompt.txt").read_bytes() == b"be bold"


def test_save_uploaded_template_rejects_traversal_category_and_name(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)

    with pytest.raises(ValueError):
        svc.save_uploaded_template(
            db_session, category="../../etc", raw_name="passwd", content=b"x", admin_id=admin.id
        )
    with pytest.raises(ValueError):
        svc.save_uploaded_template(
            db_session, category="business", raw_name="../../etc/passwd", content=b"x", admin_id=admin.id
        )
    # Nothing written to disk for either rejected attempt.
    assert list(fake_prompts_dir.glob("*")) == []


def test_save_uploaded_template_rejects_oversized_content(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)
    content = b"x" * (svc.MAX_UPLOAD_BYTES + 1)

    with pytest.raises(ValueError):
        svc.save_uploaded_template(
            db_session, category="business", raw_name="big", content=content, admin_id=admin.id
        )
    assert list(fake_prompts_dir.glob("*")) == []


def test_save_uploaded_template_rejects_non_utf8_content(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)

    with pytest.raises(ValueError):
        svc.save_uploaded_template(
            db_session, category="business", raw_name="binary", content=b"\xff\xfe\x00\x01", admin_id=admin.id
        )
    assert list(fake_prompts_dir.glob("*")) == []


def test_save_uploaded_template_refuses_overwrite(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)
    svc.save_uploaded_template(
        db_session, category="business", raw_name="dup", content=b"first", admin_id=admin.id
    )
    db_session.commit()

    with pytest.raises(FileExistsError):
        svc.save_uploaded_template(
            db_session, category="business", raw_name="dup", content=b"second", admin_id=admin.id
        )
    assert (fake_prompts_dir / "business_dup_prompt.txt").read_bytes() == b"first"


# -- get_all_templates_for_admin_view / set_active / delete_template -------


def test_get_all_templates_merges_untracked_disk_files(db_session, fake_prompts_dir):
    (fake_prompts_dir / "business_legacy_prompt.txt").write_text("legacy", encoding="utf-8")

    rows = svc.get_all_templates_for_admin_view(db_session)

    assert len(rows) == 1
    assert rows[0].filename == "business_legacy_prompt.txt"
    assert rows[0].category == "business"
    assert rows[0].is_active is True
    assert rows[0].uploaded_by_admin_id is None


def test_set_active_creates_row_for_untracked_legacy_file(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)
    (fake_prompts_dir / "service_legacy_prompt.txt").write_text("legacy", encoding="utf-8")

    row = svc.set_active(db_session, "service_legacy_prompt.txt", False, admin.id)
    db_session.commit()

    assert row.is_active is False
    fetched = db_session.query(PromptTemplate).filter(PromptTemplate.filename == "service_legacy_prompt.txt").one()
    assert fetched.is_active is False
    assert fetched.uploaded_by_admin_id == admin.id


def test_set_active_raises_for_nonexistent_file(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)

    with pytest.raises(ValueError):
        svc.set_active(db_session, "does_not_exist_prompt.txt", False, admin.id)


def test_delete_template_removes_file_and_row(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)
    svc.save_uploaded_template(
        db_session, category="business", raw_name="todelete", content=b"x", admin_id=admin.id
    )
    db_session.commit()

    svc.delete_template(db_session, "business_todelete_prompt.txt")
    db_session.commit()

    assert not (fake_prompts_dir / "business_todelete_prompt.txt").exists()
    assert db_session.query(PromptTemplate).filter(PromptTemplate.filename == "business_todelete_prompt.txt").count() == 0


def test_delete_template_rejects_traversal_filename(db_session, fake_prompts_dir):
    with pytest.raises(ValueError):
        svc.delete_template(db_session, "../../etc/passwd")


# -- get_active_template_filenames ------------------------------------------


def test_get_active_template_filenames_defaults_untracked_to_active(db_session, fake_prompts_dir):
    (fake_prompts_dir / "business_a_prompt.txt").write_text("a", encoding="utf-8")
    (fake_prompts_dir / "business_b_prompt.txt").write_text("b", encoding="utf-8")

    result = svc.get_active_template_filenames(db_session)

    assert set(result) == {"business_a_prompt.txt", "business_b_prompt.txt"}


def test_get_active_template_filenames_excludes_disabled(db_session, fake_prompts_dir):
    admin = _make_admin(db_session)
    (fake_prompts_dir / "business_a_prompt.txt").write_text("a", encoding="utf-8")
    (fake_prompts_dir / "business_b_prompt.txt").write_text("b", encoding="utf-8")
    svc.set_active(db_session, "business_b_prompt.txt", False, admin.id)
    db_session.commit()

    result = svc.get_active_template_filenames(db_session)

    assert result == ["business_a_prompt.txt"]
