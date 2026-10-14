from __future__ import annotations

import hashlib
import pytest

from scripts.agents.change_set import ChangeOperation, ChangeSet
from scripts.agents.patch_applier import CandidateArtifact, PatchApplier


def test_construct_candidates_create_and_update():
    applier = PatchApplier()
    content1 = "Conteúdo para criação"
    content2 = "Conteúdo para atualização"
    sha1 = hashlib.sha256(content1.encode("utf-8")).hexdigest()
    sha2 = hashlib.sha256(content2.encode("utf-8")).hexdigest()

    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/file1.txt",
            expected_base_sha256=None,
            candidate_content=content1,
        ),
        ChangeOperation(
            operation_id="op-2",
            type="UPDATE",
            target_path="data/text/file2.txt",
            expected_base_sha256="oldsha",
            candidate_content=content2,
        ),
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=ops,
        metadata={},
    )

    candidates = applier.construct_candidates(cs)
    assert len(candidates) == 2
    assert isinstance(candidates, tuple)

    c1, c2 = candidates
    assert c1.operation_id == "op-1"
    assert c1.target_path == "data/text/file1.txt"
    assert c1.content_bytes == content1.encode("utf-8")
    assert c1.candidate_sha256 == sha1
    assert c1.encoding == "utf-8"
    assert c1.format == "text"

    assert c2.operation_id == "op-2"
    assert c2.target_path == "data/text/file2.txt"
    assert c2.content_bytes == content2.encode("utf-8")
    assert c2.candidate_sha256 == sha2
    assert c2.encoding == "utf-8"
    assert c2.format == "text"


def test_construct_candidates_sha256_exactness():
    applier = PatchApplier()
    content = "São Paulo, café, feijão — UTF-8 especial."
    expected_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()

    op = ChangeOperation(
        operation_id="op-utf8",
        type="CREATE",
        target_path="data/text/utf8.txt",
        expected_base_sha256=None,
        candidate_content=content,
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=(op,),
        metadata={},
    )
    candidates = applier.construct_candidates(cs)
    assert candidates[0].candidate_sha256 == expected_sha


def test_construct_candidates_rejects_unsupported_encoding():
    applier = PatchApplier()
    op = ChangeOperation(
        operation_id="op-bad",
        type="CREATE",
        target_path="data/text/bad.txt",
        expected_base_sha256=None,
        candidate_content="Hello",
        encoding="latin-1",
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=(op,),
        metadata={},
    )
    with pytest.raises(ValueError, match="ERR_PATCH_INVALID"):
        applier.construct_candidates(cs)


def test_construct_candidates_rejects_unsupported_format():
    applier = PatchApplier()
    op = ChangeOperation(
        operation_id="op-bad-fmt",
        type="CREATE",
        target_path="data/text/bad.txt",
        expected_base_sha256=None,
        candidate_content="Hello",
        encoding="utf-8",
        format="binary",
    )
    cs = ChangeSet(
        change_set_id="cs-1",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=(op,),
        metadata={},
    )
    with pytest.raises(ValueError, match="ERR_PATCH_INVALID"):
        applier.construct_candidates(cs)


def test_construct_candidates_empty_changeset():
    applier = PatchApplier()
    cs = ChangeSet(
        change_set_id="cs-empty",
        request_id="req-1",
        job_id="job-1",
        book_id="book-1",
        stage="extraction",
        agent="extractor",
        operations=(),
        metadata={},
    )
    candidates = applier.construct_candidates(cs)
    assert candidates == ()
