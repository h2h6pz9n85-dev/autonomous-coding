"""
Contract Tests for JSON Schemas
================================

Validates that JSON files produced and consumed by the pipeline
conform to expected schemas. Catches schema drift and malformed data.
"""

import json
import pytest
from pathlib import Path
import tempfile
import shutil


# -----------------------------------------------------------------------------
# Schema Definitions
# -----------------------------------------------------------------------------

FEATURE_LIST_SCHEMA = {
    "type": "object",
    "required": ["features"],
    "properties": {
        "project_name": {"type": "string"},
        "total_features": {"type": "integer", "minimum": 0},
        "features": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "passes"],
                "properties": {
                    "id": {"type": "string", "pattern": r"^F\d{3}$"},
                    "name": {"type": "string", "minLength": 1},
                    "description": {"type": "string"},
                    "priority": {"type": "integer", "minimum": 1},
                    "passes": {"type": "boolean"},
                },
            },
        },
    },
}

PROGRESS_SCHEMA = {
    "type": "object",
    "required": ["project", "status", "sessions"],
    "properties": {
        "project": {
            "type": "object",
            "required": ["name", "total_features"],
            "properties": {
                "name": {"type": "string"},
                "created_at": {"type": "string"},
                "total_features": {"type": "integer", "minimum": 0},
            },
        },
        "status": {
            "type": "object",
            "required": ["current_phase"],
            "properties": {
                "updated_at": {"type": "string"},
                "features_completed": {"type": "integer", "minimum": 0},
                "features_passing": {"type": "integer", "minimum": 0},
                "current_phase": {
                    "type": "string",
                    "enum": ["INITIALIZER", "IMPLEMENT", "REVIEW", "FIX", "ARCHITECTURE"],
                },
                "current_feature": {"type": ["string", "null"]},
                "current_branch": {"type": ["string", "null"]},
                "head_commit": {"type": ["string", "null"]},
            },
        },
        "sessions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["session_id", "agent_type", "outcome"],
                "properties": {
                    "session_id": {"type": "integer", "minimum": 1},
                    "agent_type": {
                        "type": "string",
                        "enum": ["INITIALIZER", "IMPLEMENT", "REVIEW", "FIX", "ARCHITECTURE"],
                    },
                    "started_at": {"type": "string"},
                    "completed_at": {"type": "string"},
                    "summary": {"type": "string"},
                    "features_touched": {"type": "array", "items": {"type": "string"}},
                    "outcome": {
                        "type": "string",
                        "enum": ["SUCCESS", "READY_FOR_REVIEW", "NEEDS_FIX", "ERROR"],
                    },
                    "commits": {"type": "array"},
                    "commit_range": {"type": ["object", "null"]},
                },
            },
        },
    },
}

REVIEWS_SCHEMA = {
    "type": "object",
    "required": ["reviews"],
    "properties": {
        "schema_version": {"type": "string"},
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["review_id", "feature_id", "verdict"],
                "properties": {
                    "review_id": {"type": "integer", "minimum": 1},
                    "feature_id": {"type": "string"},
                    "branch": {"type": "string"},
                    "agent_type": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "verdict": {
                        "type": "string",
                        "enum": ["PASS", "REQUEST_CHANGES", "REJECT"],
                    },
                    "issues": {"type": "object"},
                    "checklist": {"type": "object"},
                    "summary": {"type": "string"},
                },
            },
        },
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["fix_id", "review_id", "feature_id"],
                "properties": {
                    "fix_id": {"type": "integer", "minimum": 1},
                    "review_id": {"type": "integer", "minimum": 1},
                    "feature_id": {"type": "string"},
                    "issues_fixed": {"type": "array"},
                    "issues_deferred": {"type": "array"},
                },
            },
        },
    },
}


# -----------------------------------------------------------------------------
# Schema Validation Helper
# -----------------------------------------------------------------------------

def validate_schema(data: dict, schema: dict, path: str = "") -> list[str]:
    """
    Simple schema validator. Returns list of validation errors.

    Not as comprehensive as jsonschema library, but sufficient for contract tests
    and avoids external dependency.
    """
    errors = []

    # Check type
    expected_type = schema.get("type")
    if expected_type:
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "integer": int,
            "boolean": bool,
            "null": type(None),
        }

        # Handle union types like ["string", "null"]
        if isinstance(expected_type, list):
            allowed_types = tuple(type_map[t] for t in expected_type)
            if not isinstance(data, allowed_types):
                errors.append(f"{path}: expected one of {expected_type}, got {type(data).__name__}")
                return errors
        else:
            expected_python_type = type_map.get(expected_type)
            if expected_python_type and not isinstance(data, expected_python_type):
                errors.append(f"{path}: expected {expected_type}, got {type(data).__name__}")
                return errors

    # Check required fields
    if isinstance(data, dict):
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                errors.append(f"{path}: missing required field '{field}'")

        # Validate properties
        properties = schema.get("properties", {})
        for key, value in data.items():
            if key in properties:
                sub_errors = validate_schema(value, properties[key], f"{path}.{key}")
                errors.extend(sub_errors)

    # Check array items
    if isinstance(data, list):
        items_schema = schema.get("items")
        if items_schema:
            for i, item in enumerate(data):
                sub_errors = validate_schema(item, items_schema, f"{path}[{i}]")
                errors.extend(sub_errors)

    # Check enum
    enum_values = schema.get("enum")
    if enum_values and data not in enum_values:
        errors.append(f"{path}: value '{data}' not in allowed values {enum_values}")

    # Check minimum
    minimum = schema.get("minimum")
    if minimum is not None and isinstance(data, (int, float)) and data < minimum:
        errors.append(f"{path}: value {data} is less than minimum {minimum}")

    # Check minLength
    min_length = schema.get("minLength")
    if min_length is not None and isinstance(data, str) and len(data) < min_length:
        errors.append(f"{path}: string length {len(data)} is less than minimum {min_length}")

    return errors


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp)


@pytest.fixture
def valid_feature_list():
    """A valid feature_list.json structure."""
    return {
        "project_name": "Test App",
        "total_features": 3,
        "features": [
            {"id": "F001", "name": "Health check", "description": "Basic health endpoint", "priority": 1, "passes": True},
            {"id": "F002", "name": "User login", "description": "Authentication", "priority": 2, "passes": False},
            {"id": "F003", "name": "Dashboard", "description": "Main dashboard", "priority": 3, "passes": False},
        ],
    }


@pytest.fixture
def valid_progress():
    """A valid progress.json structure."""
    return {
        "project": {
            "name": "Test App",
            "created_at": "2025-01-29T10:00:00Z",
            "total_features": 3,
        },
        "status": {
            "updated_at": "2025-01-29T12:00:00Z",
            "features_completed": 1,
            "features_passing": 1,
            "current_phase": "IMPLEMENT",
            "current_feature": None,
            "current_branch": None,
            "head_commit": "abc123",
        },
        "sessions": [
            {
                "session_id": 1,
                "agent_type": "INITIALIZER",
                "started_at": "2025-01-29T10:00:00Z",
                "completed_at": "2025-01-29T10:30:00Z",
                "summary": "Created feature list",
                "features_touched": [],
                "outcome": "SUCCESS",
                "commits": [{"hash": "init123", "message": "Initial setup"}],
                "commit_range": None,
            },
        ],
    }


@pytest.fixture
def valid_reviews():
    """A valid reviews.json structure."""
    return {
        "schema_version": "1.0",
        "reviews": [
            {
                "review_id": 1,
                "feature_id": "F001",
                "branch": "feature/f001",
                "agent_type": "REVIEW",
                "timestamp": "2025-01-29T11:00:00Z",
                "verdict": "PASS",
                "issues": {"critical": [], "major": [], "minor": []},
                "checklist": {"functionality": "PASS", "security": "PASS"},
                "summary": "All checks passed",
            },
        ],
        "fixes": [],
    }


# -----------------------------------------------------------------------------
# Contract Tests: feature_list.json
# -----------------------------------------------------------------------------

class TestFeatureListSchema:
    """Contract tests for feature_list.json schema."""

    def test_valid_feature_list_passes_validation(self, valid_feature_list):
        """Valid feature_list.json should pass schema validation."""
        errors = validate_schema(valid_feature_list, FEATURE_LIST_SCHEMA)
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_feature_list_requires_features_array(self, valid_feature_list):
        """feature_list.json must have 'features' array."""
        invalid = {"project_name": "Test"}  # Missing features
        errors = validate_schema(invalid, FEATURE_LIST_SCHEMA)
        assert any("features" in e for e in errors)

    def test_feature_requires_id_name_passes(self, valid_feature_list):
        """Each feature must have id, name, and passes fields."""
        invalid = valid_feature_list.copy()
        invalid["features"] = [{"name": "Test"}]  # Missing id and passes
        errors = validate_schema(invalid, FEATURE_LIST_SCHEMA)
        assert any("id" in e for e in errors)
        assert any("passes" in e for e in errors)

    def test_feature_passes_must_be_boolean(self):
        """Feature 'passes' field must be boolean."""
        invalid = {
            "features": [{"id": "F001", "name": "Test", "passes": "yes"}]
        }
        errors = validate_schema(invalid, FEATURE_LIST_SCHEMA)
        assert any("boolean" in e for e in errors)

    def test_feature_id_format(self):
        """Feature ID should follow F### pattern (documented but not strictly enforced)."""
        # This is a documentation test - the schema has a pattern but our validator
        # doesn't enforce regex. This documents the expected format.
        valid_ids = ["F001", "F002", "F999"]
        invalid_ids = ["f001", "F1", "FEATURE001", "001"]

        import re
        pattern = r"^F\d{3}$"
        for valid_id in valid_ids:
            assert re.match(pattern, valid_id), f"{valid_id} should be valid"
        for invalid_id in invalid_ids:
            assert not re.match(pattern, invalid_id), f"{invalid_id} should be invalid"

    def test_flat_array_format_accepted(self, temp_dir):
        """progress.py accepts flat array format for backwards compatibility."""
        from progress import count_passing_features

        # Flat array (legacy format)
        flat_format = [
            {"id": "F001", "name": "Test", "passes": True},
            {"id": "F002", "name": "Test2", "passes": False},
        ]
        (temp_dir / "feature_list.json").write_text(json.dumps(flat_format))

        passing, total = count_passing_features(temp_dir)
        assert passing == 1
        assert total == 2

    def test_nested_format_accepted(self, temp_dir, valid_feature_list):
        """progress.py accepts nested {features: [...]} format."""
        from progress import count_passing_features

        (temp_dir / "feature_list.json").write_text(json.dumps(valid_feature_list))

        passing, total = count_passing_features(temp_dir)
        assert passing == 1
        assert total == 3


# -----------------------------------------------------------------------------
# Contract Tests: progress.json
# -----------------------------------------------------------------------------

class TestProgressSchema:
    """Contract tests for progress.json schema."""

    def test_valid_progress_passes_validation(self, valid_progress):
        """Valid progress.json should pass schema validation."""
        errors = validate_schema(valid_progress, PROGRESS_SCHEMA)
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_progress_requires_project_status_sessions(self):
        """progress.json must have project, status, and sessions."""
        invalid = {"project": {"name": "Test", "total_features": 1}}
        errors = validate_schema(invalid, PROGRESS_SCHEMA)
        assert any("status" in e for e in errors)
        assert any("sessions" in e for e in errors)

    def test_status_requires_current_phase(self, valid_progress):
        """Status must have current_phase field."""
        invalid = valid_progress.copy()
        invalid["status"] = {"features_completed": 0}
        errors = validate_schema(invalid, PROGRESS_SCHEMA)
        assert any("current_phase" in e for e in errors)

    def test_current_phase_must_be_valid_enum(self, valid_progress):
        """current_phase must be one of the valid agent types."""
        invalid = valid_progress.copy()
        invalid["status"]["current_phase"] = "INVALID_PHASE"
        errors = validate_schema(invalid, PROGRESS_SCHEMA)
        assert any("INVALID_PHASE" in e for e in errors)

    def test_session_requires_id_type_outcome(self, valid_progress):
        """Each session must have session_id, agent_type, outcome."""
        invalid = valid_progress.copy()
        invalid["sessions"] = [{"agent_type": "IMPLEMENT"}]  # Missing session_id and outcome
        errors = validate_schema(invalid, PROGRESS_SCHEMA)
        assert any("session_id" in e for e in errors)
        assert any("outcome" in e for e in errors)

    def test_session_outcome_must_be_valid_enum(self, valid_progress):
        """Session outcome must be one of the valid values."""
        invalid = valid_progress.copy()
        invalid["sessions"][0]["outcome"] = "MAYBE"
        errors = validate_schema(invalid, PROGRESS_SCHEMA)
        assert any("MAYBE" in e for e in errors)


# -----------------------------------------------------------------------------
# Contract Tests: reviews.json
# -----------------------------------------------------------------------------

class TestReviewsSchema:
    """Contract tests for reviews.json schema."""

    def test_valid_reviews_passes_validation(self, valid_reviews):
        """Valid reviews.json should pass schema validation."""
        errors = validate_schema(valid_reviews, REVIEWS_SCHEMA)
        assert errors == [], f"Unexpected validation errors: {errors}"

    def test_reviews_requires_reviews_array(self):
        """reviews.json must have 'reviews' array."""
        invalid = {"schema_version": "1.0"}
        errors = validate_schema(invalid, REVIEWS_SCHEMA)
        assert any("reviews" in e for e in errors)

    def test_review_requires_id_feature_verdict(self, valid_reviews):
        """Each review must have review_id, feature_id, verdict."""
        invalid = valid_reviews.copy()
        invalid["reviews"] = [{"feature_id": "F001"}]  # Missing review_id and verdict
        errors = validate_schema(invalid, REVIEWS_SCHEMA)
        assert any("review_id" in e for e in errors)
        assert any("verdict" in e for e in errors)

    def test_verdict_must_be_valid_enum(self, valid_reviews):
        """Verdict must be PASS, REQUEST_CHANGES, or REJECT."""
        invalid = valid_reviews.copy()
        invalid["reviews"][0]["verdict"] = "LGTM"
        errors = validate_schema(invalid, REVIEWS_SCHEMA)
        assert any("LGTM" in e for e in errors)

    def test_fix_requires_ids(self, valid_reviews):
        """Each fix must have fix_id, review_id, feature_id."""
        invalid = valid_reviews.copy()
        invalid["fixes"] = [{"issues_fixed": []}]  # Missing required IDs
        errors = validate_schema(invalid, REVIEWS_SCHEMA)
        assert any("fix_id" in e for e in errors)


# -----------------------------------------------------------------------------
# Round-trip Tests
# -----------------------------------------------------------------------------

class TestSchemaRoundTrip:
    """Test that data can be written and read back correctly."""

    def test_feature_list_round_trip(self, temp_dir, valid_feature_list):
        """feature_list.json survives write/read cycle."""
        file_path = temp_dir / "feature_list.json"

        # Write
        file_path.write_text(json.dumps(valid_feature_list, indent=2))

        # Read back
        loaded = json.loads(file_path.read_text())

        assert loaded == valid_feature_list

    def test_progress_round_trip(self, temp_dir, valid_progress):
        """progress.json survives write/read cycle."""
        file_path = temp_dir / "progress.json"

        # Write
        file_path.write_text(json.dumps(valid_progress, indent=2))

        # Read back
        loaded = json.loads(file_path.read_text())

        assert loaded == valid_progress

    def test_reviews_round_trip(self, temp_dir, valid_reviews):
        """reviews.json survives write/read cycle."""
        file_path = temp_dir / "reviews.json"

        # Write
        file_path.write_text(json.dumps(valid_reviews, indent=2))

        # Read back
        loaded = json.loads(file_path.read_text())

        assert loaded == valid_reviews
