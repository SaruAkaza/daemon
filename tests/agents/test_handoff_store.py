import copy
import json
from pathlib import Path
import pytest

from scripts.agents.contracts import ContractValidationError, load_json
from scripts.agents.handoff_store import (
    HandoffAlreadyExistsError,
    HandoffNotFoundError,
    HandoffStore,
    HandoffStoreError,
)

ROOT = Path(__file__).resolve().parents[2]


def load_fixture(name: str) -> dict:
    path = ROOT / "tests" / "agents" / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Hierarchy & Type Tests
# ---------------------------------------------------------------------------


def test_handoff_store_error_hierarchy():
    assert issubclass(HandoffStoreError, RuntimeError)
    assert issubclass(HandoffAlreadyExistsError, HandoffStoreError)
    assert issubclass(HandoffNotFoundError, HandoffStoreError)
    assert not issubclass(ContractValidationError, HandoffStoreError)


def test_handoff_store_is_immutable_api():
    """Handoffs are immutable delivery evidence; update and delete are not exposed."""
    store = HandoffStore()
    assert not hasattr(store, "update")
    assert not hasattr(store, "delete")
    assert not hasattr(store, "upsert")


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


def test_handoff_store_initialization_default_root():
    store = HandoffStore()
    expected_root = (ROOT / "coordination" / "handoffs").resolve()
    assert store.root.resolve() == expected_root
    assert store.root.exists()


def test_handoff_store_initialization_custom_root(tmp_path):
    custom_root = tmp_path / "custom_handoffs"
    store = HandoffStore(root=custom_root)
    assert store.root.resolve() == custom_root.resolve()
    assert custom_root.exists()


# ---------------------------------------------------------------------------
# Positive Tests
# ---------------------------------------------------------------------------


def test_handoff_store_create_success(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = load_fixture("handoff-extraction.json")

    persisted_path = store.create(fixture)
    assert isinstance(persisted_path, Path)
    assert persisted_path.exists()
    assert persisted_path.name == f"{fixture['handoffId']}.json"

    on_disk = json.loads(persisted_path.read_text(encoding="utf-8"))
    assert on_disk == fixture


def test_handoff_store_roundtrip(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = load_fixture("handoff-extraction.json")

    store.create(fixture)
    loaded = store.load(fixture["handoffId"])
    assert loaded == fixture


def test_handoff_store_multiple_handoffs(tmp_path):
    store = HandoffStore(root=tmp_path)
    template = load_fixture("handoff-extraction.json")

    h1 = copy.deepcopy(template)
    h1["handoffId"] = "HANDOFF-TREVAS-SOURCE-001"
    h1["stage"] = "source"
    h1["agent"] = "source-agent"

    h2 = copy.deepcopy(template)
    h2["handoffId"] = "HANDOFF-TREVAS-EXTRACTION-001"

    store.create(h1)
    store.create(h2)

    assert store.load("HANDOFF-TREVAS-SOURCE-001") == h1
    assert store.load("HANDOFF-TREVAS-EXTRACTION-001") == h2


def test_handoff_store_utf8_preservation(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = copy.deepcopy(load_fixture("handoff-extraction.json"))
    fixture["changes"] = [
        "extração de páginas",
        "bênção celestial e demônio",
        "relação entre entidades",
        "transição de estágio concluída",
    ]

    store.create(fixture)
    loaded = store.load(fixture["handoffId"])

    assert loaded["changes"] == fixture["changes"]
    # Check that raw file content contains actual UTF-8 characters, not unicode escapes
    raw_content = (tmp_path / f"{fixture['handoffId']}.json").read_text(encoding="utf-8")
    assert "extração" in raw_content
    assert "bênção" in raw_content
    assert "demônio" in raw_content


def test_handoff_store_create_does_not_mutate_input(tmp_path):
    store = HandoffStore(root=tmp_path)
    original = load_fixture("handoff-extraction.json")
    payload = copy.deepcopy(original)

    store.create(payload)
    assert payload == original


def test_handoff_store_atomic_write_leaves_no_temp_files(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = load_fixture("handoff-extraction.json")

    persisted_path = store.create(fixture)
    assert persisted_path.exists()

    # Check that no .tmp files remain in root
    temp_files = list(tmp_path.glob("*.tmp"))
    assert temp_files == []


# ---------------------------------------------------------------------------
# Negative Tests
# ---------------------------------------------------------------------------


def test_handoff_store_create_rejects_duplicate(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = load_fixture("handoff-extraction.json")

    store.create(fixture)

    with pytest.raises(HandoffAlreadyExistsError) as exc_info:
        store.create(fixture)
    assert fixture["handoffId"] in str(exc_info.value)
    assert isinstance(exc_info.value, HandoffStoreError)


def test_handoff_store_immutability_on_disk(tmp_path):
    store = HandoffStore(root=tmp_path)
    original = load_fixture("handoff-extraction.json")
    store.create(original)

    # Attempt to overwrite with altered data under the same handoffId
    altered = copy.deepcopy(original)
    altered["status"] = "fail"
    altered["changes"] = ["malicious alteration attempt"]

    with pytest.raises(HandoffAlreadyExistsError):
        store.create(altered)

    # Verify on-disk file remained intact and identical to original
    loaded = store.load(original["handoffId"])
    assert loaded == original
    assert loaded["status"] == "pass_with_warnings"
    assert loaded["changes"] == original["changes"]


def test_handoff_store_load_not_found(tmp_path):
    store = HandoffStore(root=tmp_path)

    with pytest.raises(HandoffNotFoundError) as exc_info:
        store.load("NON-EXISTENT-HANDOFF-001")
    assert "NON-EXISTENT-HANDOFF-001" in str(exc_info.value)
    assert isinstance(exc_info.value, HandoffStoreError)


def test_handoff_store_create_rejects_non_dict_payload(tmp_path):
    store = HandoffStore(root=tmp_path)
    with pytest.raises(ContractValidationError):
        store.create(["not", "a", "dict"])


def test_handoff_store_create_rejects_schema_violation(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = copy.deepcopy(load_fixture("handoff-extraction.json"))
    del fixture["agent"]  # missing required property

    with pytest.raises(ContractValidationError):
        store.create(fixture)

    assert not (tmp_path / "HANDOFF-TREVAS-EXTRACTION-001.json").exists()


def test_handoff_store_create_rejects_unknown_property(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = copy.deepcopy(load_fixture("handoff-extraction.json"))
    fixture["unrecognized_field"] = "not_in_schema"

    with pytest.raises(ContractValidationError):
        store.create(fixture)


def test_handoff_store_create_rejects_rogue_agent(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = copy.deepcopy(load_fixture("handoff-extraction.json"))
    fixture["agent"] = "rogue-unregistered-agent"

    with pytest.raises(ContractValidationError):
        store.create(fixture)


def test_handoff_store_create_rejects_status_done(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = copy.deepcopy(load_fixture("handoff-extraction.json"))
    fixture["status"] = "done"  # 'done' is a Job status, forbidden on Handoff

    with pytest.raises(ContractValidationError):
        store.create(fixture)


def test_handoff_store_load_rejects_malformed_json_syntax(tmp_path):
    store = HandoffStore(root=tmp_path)
    corrupt_file = tmp_path / "CORRUPT-JSON.json"
    corrupt_file.write_text("unclosed { json", encoding="utf-8")

    with pytest.raises(ContractValidationError):
        store.load("CORRUPT-JSON")


def test_handoff_store_load_rejects_stored_schema_violation(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = load_fixture("handoff-extraction.json")
    store.create(fixture)

    # Corrupt on disk
    corrupt_payload = copy.deepcopy(fixture)
    corrupt_payload["status"] = "invalid_status_enum"
    (tmp_path / f"{fixture['handoffId']}.json").write_text(
        json.dumps(corrupt_payload), encoding="utf-8"
    )

    with pytest.raises(ContractValidationError):
        store.load(fixture["handoffId"])


def test_handoff_store_path_traversal_create(tmp_path):
    store = HandoffStore(root=tmp_path)
    fixture = copy.deepcopy(load_fixture("handoff-extraction.json"))

    fixture["handoffId"] = "../evil-handoff"
    with pytest.raises(HandoffStoreError):
        store.create(fixture)

    fixture["handoffId"] = "sub/dir/handoff"
    with pytest.raises(HandoffStoreError):
        store.create(fixture)

    fixture["handoffId"] = "sub\\dir\\handoff"
    with pytest.raises(HandoffStoreError):
        store.create(fixture)

    fixture["handoffId"] = "C:\\temp\\handoff"
    with pytest.raises(HandoffStoreError):
        store.create(fixture)


def test_handoff_store_path_traversal_load(tmp_path):
    store = HandoffStore(root=tmp_path)

    with pytest.raises(HandoffStoreError):
        store.load("../evil-handoff")

    with pytest.raises(HandoffStoreError):
        store.load("/absolute/evil-handoff")


# ---------------------------------------------------------------------------
# List Handoff IDs Tests
# ---------------------------------------------------------------------------


def test_handoff_store_list_handoff_ids_sorted_and_deterministic(tmp_path):
    store = HandoffStore(root=tmp_path)

    # Non-handoff files that should be ignored
    (tmp_path / ".gitkeep").touch()
    (tmp_path / "README.txt").write_text("info", encoding="utf-8")
    (tmp_path / "temp.json.tmp").write_text("{}", encoding="utf-8")

    handoff_ids = [
        "HANDOFF-TREVAS-SOURCE-001",
        "HANDOFF-TREVAS-EXTRACTION-001",
        "HANDOFF-TREVAS-EDITORIAL-001",
        "HANDOFF-TREVAS-ENTITIES-001",
    ]
    fixture_template = load_fixture("handoff-extraction.json")

    for hid in reversed(handoff_ids):
        payload = copy.deepcopy(fixture_template)
        payload["handoffId"] = hid
        store.create(payload)

    listed = store.list_handoff_ids()
    assert listed == sorted(handoff_ids)


def test_handoff_store_list_handoff_ids_empty(tmp_path):
    store = HandoffStore(root=tmp_path)
    (tmp_path / ".gitkeep").touch()
    assert store.list_handoff_ids() == []


def test_handoff_store_default_root_has_no_stray_handoffs():
    store = HandoffStore()
    assert store.list_handoff_ids() == []
