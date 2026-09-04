import copy
import json
from pathlib import Path
import pytest

from scripts.agents.contracts import ContractValidationError, load_json
from scripts.agents.job_store import (
    JobAlreadyExistsError,
    JobNotFoundError,
    JobStore,
    JobStoreError,
)

ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str) -> dict:
    path = ROOT / "tests" / "agents" / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Hierarchy & Type Tests
# ---------------------------------------------------------------------------


def test_job_store_error_hierarchy():
    assert issubclass(JobStoreError, RuntimeError)
    assert issubclass(JobAlreadyExistsError, JobStoreError)
    assert issubclass(JobNotFoundError, JobStoreError)
    assert not issubclass(ContractValidationError, JobStoreError)


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


def test_job_store_initialization_default_root():
    store = JobStore()
    expected_root = (ROOT / "coordination" / "jobs").resolve()
    assert store.root.resolve() == expected_root
    assert store.root.exists()


def test_job_store_initialization_custom_root(tmp_path):
    custom_root = tmp_path / "custom_jobs"
    store = JobStore(root=custom_root)
    assert store.root.resolve() == custom_root.resolve()
    assert custom_root.exists()


# ---------------------------------------------------------------------------
# Create Tests
# ---------------------------------------------------------------------------


def test_job_store_create_success(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = load_fixture("job-book-trevas.json")

    created = store.create(fixture)
    assert created == fixture

    job_file = tmp_path / f"{fixture['jobId']}.json"
    assert job_file.exists()

    persisted = json.loads(job_file.read_text(encoding="utf-8"))
    assert persisted == fixture


def test_job_store_create_rejects_duplicate(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = load_fixture("job-book-trevas.json")

    store.create(fixture)

    with pytest.raises(JobAlreadyExistsError) as exc_info:
        store.create(fixture)
    assert fixture["jobId"] in str(exc_info.value)
    assert isinstance(exc_info.value, JobStoreError)


def test_job_store_create_rejects_invalid_schema(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = copy.deepcopy(load_fixture("job-book-trevas.json"))
    fixture["status"] = "invalid_status_enum"

    with pytest.raises(ContractValidationError):
        store.create(fixture)

    assert not (tmp_path / f"{fixture['jobId']}.json").exists()


def test_job_store_create_rejects_non_dict_payload(tmp_path):
    store = JobStore(root=tmp_path)
    with pytest.raises(ContractValidationError):
        store.create(["not", "a", "dict"])


def test_job_store_create_path_traversal(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = copy.deepcopy(load_fixture("job-book-trevas.json"))
    fixture["jobId"] = "../evil-job"

    with pytest.raises(JobStoreError):
        store.create(fixture)


def test_job_store_create_does_not_mutate_input(tmp_path):
    store = JobStore(root=tmp_path)
    original = load_fixture("job-book-trevas.json")
    payload = copy.deepcopy(original)

    store.create(payload)
    assert payload == original


# ---------------------------------------------------------------------------
# Load Tests
# ---------------------------------------------------------------------------


def test_job_store_load_success(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = load_fixture("job-book-trevas.json")
    store.create(fixture)

    loaded = store.load(fixture["jobId"])
    assert loaded == fixture


def test_job_store_load_not_found(tmp_path):
    store = JobStore(root=tmp_path)

    with pytest.raises(JobNotFoundError) as exc_info:
        store.load("NON-EXISTENT-JOB-001")
    assert "NON-EXISTENT-JOB-001" in str(exc_info.value)
    assert isinstance(exc_info.value, JobStoreError)


def test_job_store_load_path_traversal(tmp_path):
    store = JobStore(root=tmp_path)

    with pytest.raises(JobStoreError):
        store.load("../evil-job")


def test_job_store_load_revalidates_and_rejects_corrupted_file(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = load_fixture("job-book-trevas.json")
    store.create(fixture)

    # Corrupt the payload on disk (stored schema violation)
    job_file = tmp_path / f"{fixture['jobId']}.json"
    corrupted = copy.deepcopy(fixture)
    corrupted["status"] = "corrupted_status"
    job_file.write_text(json.dumps(corrupted), encoding="utf-8")

    with pytest.raises(ContractValidationError):
        store.load(fixture["jobId"])


def test_job_store_load_rejects_malformed_json_syntax(tmp_path):
    store = JobStore(root=tmp_path)
    job_file = tmp_path / "SYNTAX-ERROR.json"
    job_file.write_text("unclosed { json", encoding="utf-8")

    with pytest.raises(ContractValidationError):
        store.load("SYNTAX-ERROR")


# ---------------------------------------------------------------------------
# Update Tests
# ---------------------------------------------------------------------------


def test_job_store_update_success(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = load_fixture("job-book-trevas.json")
    store.create(fixture)

    updated_payload = copy.deepcopy(fixture)
    updated_payload["status"] = "approved"
    updated_payload["stages"]["extraction"] = "pass"
    updated_payload["updatedAt"] = "2026-09-04T10:15:00-03:00"

    result = store.update(updated_payload)
    assert result == updated_payload

    loaded = store.load(fixture["jobId"])
    assert loaded == updated_payload
    assert loaded["status"] == "approved"
    assert loaded["stages"]["extraction"] == "pass"


def test_job_store_update_not_found_no_upsert(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = load_fixture("job-book-trevas.json")

    # Update without prior create must fail
    with pytest.raises(JobNotFoundError):
        store.update(fixture)

    assert not (tmp_path / f"{fixture['jobId']}.json").exists()


def test_job_store_update_rejects_invalid_payload(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = load_fixture("job-book-trevas.json")
    store.create(fixture)

    invalid_payload = copy.deepcopy(fixture)
    invalid_payload["status"] = "non_existent_status"

    with pytest.raises(ContractValidationError):
        store.update(invalid_payload)

    # Confirm original file on disk remains unchanged
    loaded = store.load(fixture["jobId"])
    assert loaded == fixture


def test_job_store_update_does_not_mutate_input(tmp_path):
    store = JobStore(root=tmp_path)
    fixture = load_fixture("job-book-trevas.json")
    store.create(fixture)

    updated_payload = copy.deepcopy(fixture)
    updated_payload["status"] = "approved"
    original_copy = copy.deepcopy(updated_payload)

    store.update(updated_payload)
    assert updated_payload == original_copy


# ---------------------------------------------------------------------------
# List Job IDs Tests
# ---------------------------------------------------------------------------


def test_job_store_list_job_ids_sorted_and_deterministic(tmp_path):
    store = JobStore(root=tmp_path)

    # Non-job files that should be ignored
    (tmp_path / ".gitkeep").touch()
    (tmp_path / "README.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "temp.json.tmp").write_text("{}", encoding="utf-8")

    job_ids = ["JOB-003", "JOB-001", "JOB-002", "JOB-ALPHA", "JOB-100"]
    fixture_template = load_fixture("job-book-trevas.json")

    for jid in reversed(job_ids):
        payload = copy.deepcopy(fixture_template)
        payload["jobId"] = jid
        store.create(payload)

    listed = store.list_job_ids()
    assert listed == sorted(job_ids)


def test_job_store_list_job_ids_empty(tmp_path):
    store = JobStore(root=tmp_path)
    (tmp_path / ".gitkeep").touch()
    assert store.list_job_ids() == []


def test_job_store_default_root_has_no_stray_jobs():
    store = JobStore()
    assert store.list_job_ids() == []
