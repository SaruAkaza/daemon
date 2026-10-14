from __future__ import annotations

import json
import pytest

from scripts.agents.application_runtime import ResourceBounds
from scripts.agents.change_set import ChangeOperation, ChangeSet
from scripts.agents.content_validator import ContentValidationResult, ContentValidator


def test_content_validator_valid_utf8_text():
    bounds = ResourceBounds()
    validator = ContentValidator(bounds)
    op = ChangeOperation(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/test.txt",
        expected_base_sha256=None,
        candidate_content="Hello world! Este é um texto em português.",
    )
    result = validator.validate_operation_content(op)
    assert result.valid is True
    assert result.code is None
    assert len(result.reasons) == 0


def test_content_validator_rejects_bom():
    bounds = ResourceBounds()
    validator = ContentValidator(bounds)
    # UTF-8 BOM character
    op = ChangeOperation(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/test.txt",
        expected_base_sha256=None,
        candidate_content="﻿Hello with BOM",
    )
    result = validator.validate_operation_content(op)
    assert result.valid is False
    assert result.code == "ERR_UNSUPPORTED_CONTENT_DOMAIN"
    assert any("BOM" in r for r in result.reasons)


def test_content_validator_rejects_non_utf8_encoding_declared():
    bounds = ResourceBounds()
    validator = ContentValidator(bounds)
    op = ChangeOperation(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/test.txt",
        expected_base_sha256=None,
        candidate_content="Hello",
        encoding="latin-1",
    )
    result = validator.validate_operation_content(op)
    assert result.valid is False
    assert result.code == "ERR_UNSUPPORTED_CONTENT_DOMAIN"


def test_content_validator_rejects_null_bytes():
    bounds = ResourceBounds()
    validator = ContentValidator(bounds)
    op = ChangeOperation(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/test.txt",
        expected_base_sha256=None,
        candidate_content="Hello" + chr(0) + "World",
    )
    result = validator.validate_operation_content(op)
    assert result.valid is False
    assert result.code == "ERR_UNSUPPORTED_CONTENT_DOMAIN"


def test_content_validator_valid_json():
    bounds = ResourceBounds()
    validator = ContentValidator(bounds)
    op = ChangeOperation(
        operation_id="op-1",
        type="CREATE",
        target_path="data/structured/spells.json",
        expected_base_sha256=None,
        candidate_content=json.dumps({"spells": [{"name": "Bola de Fogo", "cost": 10}]}),
    )
    result = validator.validate_operation_content(op)
    assert result.valid is True
    assert result.code is None


def test_content_validator_malformed_json_rejected():
    bounds = ResourceBounds()
    validator = ContentValidator(bounds)
    op = ChangeOperation(
        operation_id="op-1",
        type="CREATE",
        target_path="data/structured/spells.json",
        expected_base_sha256=None,
        candidate_content="{invalid json: true,",
    )
    result = validator.validate_operation_content(op)
    assert result.valid is False
    assert result.code == "ERR_PATCH_INVALID"
    assert any("Malformed JSON" in r for r in result.reasons)


def test_content_validator_file_size_exceeded():
    # Limit max file size to 100 bytes
    bounds = ResourceBounds(max_file_size_bytes=100)
    validator = ContentValidator(bounds)
    op = ChangeOperation(
        operation_id="op-1",
        type="CREATE",
        target_path="data/text/big.txt",
        expected_base_sha256=None,
        candidate_content="A" * 101,
    )
    result = validator.validate_operation_content(op)
    assert result.valid is False
    assert result.code == "ERR_RESOURCE_BOUND_EXCEEDED"
    assert any("max_file_size_bytes" in r for r in result.reasons)


def test_content_validator_changeset_operations_count_exceeded():
    bounds = ResourceBounds(max_operations_per_changeset=2)
    validator = ContentValidator(bounds)
    ops = tuple(
        ChangeOperation(
            operation_id=f"op-{i}",
            type="CREATE",
            target_path=f"data/text/doc_{i}.txt",
            expected_base_sha256=None,
            candidate_content=f"Content {i}",
        )
        for i in range(3)
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
    result = validator.validate_changeset_bounds(cs)
    assert result.valid is False
    assert result.code == "ERR_RESOURCE_BOUND_EXCEEDED"
    assert any("max_operations_per_changeset" in r for r in result.reasons)


def test_content_validator_changeset_total_bytes_exceeded():
    bounds = ResourceBounds(max_changeset_size_bytes=150)
    validator = ContentValidator(bounds)
    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/doc1.txt",
            expected_base_sha256=None,
            candidate_content="A" * 100,
        ),
        ChangeOperation(
            operation_id="op-2",
            type="CREATE",
            target_path="data/text/doc2.txt",
            expected_base_sha256=None,
            candidate_content="B" * 60,
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
    result = validator.validate_changeset_bounds(cs)
    assert result.valid is False
    assert result.code == "ERR_RESOURCE_BOUND_EXCEEDED"
    assert any("max_changeset_size_bytes" in r for r in result.reasons)


def test_content_validator_changeset_bounds_pass():
    bounds = ResourceBounds(max_changeset_size_bytes=500, max_operations_per_changeset=5)
    validator = ContentValidator(bounds)
    ops = (
        ChangeOperation(
            operation_id="op-1",
            type="CREATE",
            target_path="data/text/doc1.txt",
            expected_base_sha256=None,
            candidate_content="Hello world",
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
    result = validator.validate_changeset_bounds(cs)
    assert result.valid is True
    assert result.code is None
