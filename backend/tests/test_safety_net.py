"""P0 weakness fixes: pre-restore snapshot + config redaction (hermetic)."""
import io
import json
import zipfile


def test_redaction_strips_secrets():
    import routers.system as sys_mod
    cfg = {"model": "gemma", "api_key": "sk-live-123", "pollinations_token": "tok",
           "student_name": "Amy", "nested_count": 3}
    orig = sys_mod.get_config
    sys_mod.get_config = lambda: dict(cfg)
    try:
        red = sys_mod._redacted_config()
    finally:
        sys_mod.get_config = orig
    assert red["api_key"] == "<redacted>"
    assert red["pollinations_token"] == "<redacted>"
    assert red["model"] == "gemma"  # shape preserved
    assert red["student_name"] == "Amy"


def test_pre_restore_snapshot_creates_zip(tmp_path, monkeypatch):
    import routers.backup as bak
    monkeypatch.setattr(bak, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(bak, "_aria_data_dir", lambda: tmp_path / "aria_data")
    (tmp_path / "aria_data").mkdir(parents=True)
    (tmp_path / "aria_data" / "conversations.json").write_text('{"a":1}')
    name = bak._snapshot_pre_restore()
    assert name and name.startswith("aria-pre-restore-")
    zf = zipfile.ZipFile(tmp_path / "backups" / name)
    assert "manifest.json" in zf.namelist()
    assert "aria_data/conversations.json" in zf.namelist()


def test_restore_response_mentions_snapshot():
    import inspect
    import routers.backup as bak
    src = inspect.getsource(bak.restore_backup)
    assert "_snapshot_pre_restore()" in src
    assert "pre_restore_backup" in src
