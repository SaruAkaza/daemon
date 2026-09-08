from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

from scripts.agents.filesystem_primitives import FileSystemPrimitives


def test_exclusive_create_success(tmp_path: Path):
    target = tmp_path / "data" / "new.txt"
    staged = tmp_path / "staging" / "op1.bin"
    staged.parent.mkdir(parents=True)
    staged.write_text("Hello exclusive", encoding="utf-8")
    expected_sha = hashlib.sha256(b"Hello exclusive").hexdigest()

    actual_sha = FileSystemPrimitives.exclusive_create(target, staged)
    assert actual_sha == expected_sha
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == "Hello exclusive"


def test_exclusive_create_already_exists(tmp_path: Path):
    target = tmp_path / "data" / "existing.txt"
    target.parent.mkdir(parents=True)
    target.write_text("Old content", encoding="utf-8")

    staged = tmp_path / "staging" / "op1.bin"
    staged.parent.mkdir(parents=True)
    staged.write_text("New content", encoding="utf-8")

    with pytest.raises(FileExistsError):
        FileSystemPrimitives.exclusive_create(target, staged)

    # Existing content must remain untouched
    assert target.read_text(encoding="utf-8") == "Old content"


def test_atomic_replace_success(tmp_path: Path):
    target = tmp_path / "data" / "target.txt"
    target.parent.mkdir(parents=True)
    target.write_text("V1 content", encoding="utf-8")

    staged = tmp_path / "staging" / "op_v2.bin"
    staged.parent.mkdir(parents=True)
    staged.write_text("V2 content", encoding="utf-8")
    expected_sha = hashlib.sha256(b"V2 content").hexdigest()

    actual_sha = FileSystemPrimitives.atomic_replace(target, staged)
    assert actual_sha == expected_sha
    assert target.read_text(encoding="utf-8") == "V2 content"


def test_compensating_remove_success(tmp_path: Path):
    target = tmp_path / "data" / "to_remove.txt"
    target.parent.mkdir(parents=True)
    target.write_text("Created then rollback", encoding="utf-8")
    sha = hashlib.sha256(b"Created then rollback").hexdigest()

    result = FileSystemPrimitives.compensating_remove(target, sha)
    assert result is True
    assert not target.exists()


def test_compensating_remove_mismatch_refused(tmp_path: Path):
    target = tmp_path / "data" / "external_tamper.txt"
    target.parent.mkdir(parents=True)
    target.write_text("Tampered by external actor", encoding="utf-8")

    expected_sha = hashlib.sha256(b"Original expected").hexdigest()
    result = FileSystemPrimitives.compensating_remove(target, expected_sha)
    assert result is False
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Tampered by external actor"


def test_compensating_restore_success(tmp_path: Path):
    target = tmp_path / "data" / "restore_target.txt"
    target.parent.mkdir(parents=True)
    target.write_text("Current Post Apply", encoding="utf-8")
    post_sha = hashlib.sha256(b"Current Post Apply").hexdigest()

    backup = tmp_path / "staging" / "backups" / "orig_snapshot.bin"
    backup.parent.mkdir(parents=True)
    backup.write_text("Original pristine content", encoding="utf-8")

    result = FileSystemPrimitives.compensating_restore(target, backup, post_sha)
    assert result is True
    assert target.read_text(encoding="utf-8") == "Original pristine content"


def test_compensating_restore_mismatch_refused(tmp_path: Path):
    target = tmp_path / "data" / "restore_target.txt"
    target.parent.mkdir(parents=True)
    target.write_text("External concurrent change", encoding="utf-8")

    expected_post_sha = hashlib.sha256(b"Our transaction change").hexdigest()
    backup = tmp_path / "staging" / "backups" / "orig_snapshot.bin"
    backup.parent.mkdir(parents=True)
    backup.write_text("Original pristine content", encoding="utf-8")

    result = FileSystemPrimitives.compensating_restore(target, backup, expected_post_sha)
    assert result is False
    assert target.read_text(encoding="utf-8") == "External concurrent change"
