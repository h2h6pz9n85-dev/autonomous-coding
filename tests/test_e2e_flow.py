"""
End-to-End Flow Tests
=====================

Tests the complete orchestration loop by mocking Claude Code CLI outputs.
Simulates multiple agents working together to build a project.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock, call
import tempfile
import shutil
import asyncio

from config import AgentConfig, SessionState, SessionType
from autonomous_agent_demo import run_autonomous_agent, get_prompt_for_session


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def e2e_config(temp_project_dir):
    """Config for end-to-end testing with small feature count."""
    spec_file = temp_project_dir / "app_spec.txt"
    spec_file.write_text("""
<app_specification>
    <name>Test App</name>
    <description>A simple test application</description>
    <core_features>
        <feature>Health check endpoint</feature>
        <feature>User login</feature>
    </core_features>
</app_specification>
""")

    return AgentConfig(
        project_dir=temp_project_dir,
        spec_file=spec_file,
        implement_model="sonnet",
        review_model="opus",
        fix_model="sonnet",
        architecture_model="opus",
        architecture_interval=5,
        feature_count=2,
        max_iterations=10,  # Limit iterations for testing
        main_branch="main",
    )


# -----------------------------------------------------------------------------
# Mock Agent Responses
# -----------------------------------------------------------------------------

class MockAgentResponses:
    """
    Simulates Claude Code CLI responses for each agent type.

    Each response simulates what the agent would output and
    the side effects it would have on project files.
    """

    @staticmethod
    def initializer_response(project_dir: Path, feature_count: int = 2):
        """
        Simulates INITIALIZER agent creating feature_list.json and progress.json.
        """
        # Create feature_list.json
        feature_list = {
            "project_name": "Test App",
            "total_features": feature_count,
            "features": [
                {
                    "id": f"F{str(i+1).zfill(3)}",
                    "name": f"Feature {i+1}",
                    "description": f"Test feature {i+1}",
                    "priority": i+1,
                    "passes": False,
                }
                for i in range(feature_count)
            ]
        }
        (project_dir / "feature_list.json").write_text(json.dumps(feature_list, indent=2))

        # Create progress.json
        progress = {
            "project": {
                "name": "Test App",
                "created_at": "2025-01-29T10:00:00Z",
                "total_features": feature_count
            },
            "status": {
                "updated_at": "2025-01-29T10:00:00Z",
                "features_completed": 0,
                "features_passing": 0,
                "current_phase": "IMPLEMENT",
                "current_feature": None,
                "current_branch": None,
                "head_commit": "init123"
            },
            "sessions": [{
                "session_id": 1,
                "agent_type": "INITIALIZER",
                "started_at": "2025-01-29T10:00:00Z",
                "completed_at": "2025-01-29T10:30:00Z",
                "summary": f"Created feature_list.json with {feature_count} features",
                "features_touched": [],
                "outcome": "SUCCESS",
                "commits": [{"hash": "init123", "message": "Initial setup"}],
                "commit_range": {"from": None, "to": "init123"}
            }]
        }
        (project_dir / "progress.json").write_text(json.dumps(progress, indent=2))

        # Create reviews.json
        reviews = {"schema_version": "1.0", "reviews": [], "fixes": []}
        (project_dir / "reviews.json").write_text(json.dumps(reviews, indent=2))

        return "continue", "Initialized project with feature_list.json"

    @staticmethod
    def implement_response(project_dir: Path, feature_id: str, success: bool = True):
        """
        Simulates IMPLEMENT agent working on a feature.
        Updates progress.json to indicate ready for review.
        """
        progress = json.loads((project_dir / "progress.json").read_text())

        branch_name = f"feature/{feature_id.lower()}"
        commit_hash = f"impl{feature_id}"

        # Update status
        progress["status"]["current_phase"] = "REVIEW"
        progress["status"]["current_feature"] = feature_id
        progress["status"]["current_branch"] = branch_name
        progress["status"]["head_commit"] = commit_hash

        # Add session
        session_id = len(progress["sessions"]) + 1
        progress["sessions"].append({
            "session_id": session_id,
            "agent_type": "IMPLEMENT",
            "started_at": "2025-01-29T11:00:00Z",
            "completed_at": "2025-01-29T11:30:00Z",
            "summary": f"Implemented {feature_id}",
            "features_touched": [feature_id],
            "outcome": "READY_FOR_REVIEW",
            "commits": [{"hash": commit_hash, "message": f"Implement {feature_id}"}],
            "commit_range": {"from": "init123", "to": commit_hash}
        })

        (project_dir / "progress.json").write_text(json.dumps(progress, indent=2))

        return "continue", f"Implemented {feature_id}, ready for review"

    @staticmethod
    def review_pass_response(project_dir: Path, feature_id: str):
        """
        Simulates REVIEW agent approving a feature (PASS verdict).
        Merges to main and marks feature as passing.
        """
        progress = json.loads((project_dir / "progress.json").read_text())
        feature_list = json.loads((project_dir / "feature_list.json").read_text())
        reviews = json.loads((project_dir / "reviews.json").read_text())

        # Mark feature as passing
        for f in feature_list["features"]:
            if f["id"] == feature_id:
                f["passes"] = True
                break
        (project_dir / "feature_list.json").write_text(json.dumps(feature_list, indent=2))

        # Add review entry
        review_id = len(reviews["reviews"]) + 1
        reviews["reviews"].append({
            "review_id": review_id,
            "feature_id": feature_id,
            "branch": progress["status"]["current_branch"],
            "agent_type": "REVIEW",
            "timestamp": "2025-01-29T12:00:00Z",
            "verdict": "PASS",
            "issues": {"critical": [], "major": [], "minor": [], "suggestions": []},
            "checklist": {
                "functionality": "PASS",
                "security": "PASS",
                "testing": "PASS",
                "code_quality": "PASS",
                "error_handling": "PASS",
                "maintainability": "PASS"
            },
            "summary": "All checks passed"
        })
        (project_dir / "reviews.json").write_text(json.dumps(reviews, indent=2))

        # Update progress - clear current feature, increment completed
        progress["status"]["features_completed"] = progress["status"].get("features_completed", 0) + 1
        progress["status"]["features_passing"] = progress["status"].get("features_passing", 0) + 1
        progress["status"]["current_phase"] = "IMPLEMENT"
        progress["status"]["current_feature"] = None
        progress["status"]["current_branch"] = None

        # Add session
        session_id = len(progress["sessions"]) + 1
        progress["sessions"].append({
            "session_id": session_id,
            "agent_type": "REVIEW",
            "started_at": "2025-01-29T12:00:00Z",
            "completed_at": "2025-01-29T12:15:00Z",
            "summary": f"Reviewed {feature_id}: PASS - merged to main",
            "features_touched": [feature_id],
            "outcome": "SUCCESS",
            "commits": [],
            "commit_range": None
        })

        (project_dir / "progress.json").write_text(json.dumps(progress, indent=2))

        return "continue", f"Review PASS for {feature_id}, merged to main"

    @staticmethod
    def review_request_changes_response(project_dir: Path, feature_id: str, issues: list):
        """
        Simulates REVIEW agent requesting changes.
        """
        progress = json.loads((project_dir / "progress.json").read_text())
        reviews = json.loads((project_dir / "reviews.json").read_text())

        # Add review entry with issues
        review_id = len(reviews["reviews"]) + 1
        reviews["reviews"].append({
            "review_id": review_id,
            "feature_id": feature_id,
            "branch": progress["status"]["current_branch"],
            "agent_type": "REVIEW",
            "timestamp": "2025-01-29T12:00:00Z",
            "verdict": "REQUEST_CHANGES",
            "issues": {
                "critical": [],
                "major": [{"id": f"R{review_id}-M{i+1}", "description": issue} for i, issue in enumerate(issues)],
                "minor": [],
                "suggestions": []
            },
            "checklist": {
                "functionality": "PASS",
                "security": "PASS",
                "testing": "FAIL",
                "code_quality": "PASS",
                "error_handling": "PASS",
                "maintainability": "PASS"
            },
            "summary": f"Found {len(issues)} issues requiring fixes"
        })
        (project_dir / "reviews.json").write_text(json.dumps(reviews, indent=2))

        # Update progress to FIX phase
        progress["status"]["current_phase"] = "FIX"

        # Add session
        session_id = len(progress["sessions"]) + 1
        progress["sessions"].append({
            "session_id": session_id,
            "agent_type": "REVIEW",
            "started_at": "2025-01-29T12:00:00Z",
            "completed_at": "2025-01-29T12:15:00Z",
            "summary": f"Reviewed {feature_id}: REQUEST_CHANGES",
            "features_touched": [feature_id],
            "outcome": "NEEDS_FIX",
            "commits": [],
            "commit_range": None
        })

        (project_dir / "progress.json").write_text(json.dumps(progress, indent=2))

        return "continue", f"Review REQUEST_CHANGES for {feature_id}"

    @staticmethod
    def fix_response(project_dir: Path, feature_id: str):
        """
        Simulates FIX agent addressing review issues.
        """
        progress = json.loads((project_dir / "progress.json").read_text())
        reviews = json.loads((project_dir / "reviews.json").read_text())

        # Get last review for this feature
        last_review = [r for r in reviews["reviews"] if r["feature_id"] == feature_id][-1]
        review_id = last_review["review_id"]

        # Add fix entry
        fix_id = len(reviews.get("fixes", [])) + 1
        issues_fixed = [
            {"issue_id": issue["id"], "fix_description": f"Fixed: {issue['description']}", "commit": f"fix{fix_id}"}
            for issue in last_review["issues"]["major"]
        ]

        if "fixes" not in reviews:
            reviews["fixes"] = []
        reviews["fixes"].append({
            "fix_id": fix_id,
            "review_id": review_id,
            "feature_id": feature_id,
            "agent_type": "FIX",
            "timestamp": "2025-01-29T13:00:00Z",
            "issues_fixed": issues_fixed,
            "issues_deferred": [],
            "tests_added": ["test_fix"],
            "merged_to_main": False,
            "pending_review": True
        })
        (project_dir / "reviews.json").write_text(json.dumps(reviews, indent=2))

        # Update progress to REVIEW phase (re-verification)
        progress["status"]["current_phase"] = "REVIEW"
        progress["status"]["head_commit"] = f"fix{fix_id}"

        # Add session
        session_id = len(progress["sessions"]) + 1
        progress["sessions"].append({
            "session_id": session_id,
            "agent_type": "FIX",
            "started_at": "2025-01-29T13:00:00Z",
            "completed_at": "2025-01-29T13:30:00Z",
            "summary": f"Fixed {len(issues_fixed)} issues for {feature_id}",
            "features_touched": [feature_id],
            "outcome": "READY_FOR_REVIEW",
            "commits": [{"hash": f"fix{fix_id}", "message": "Fix review issues"}],
            "commit_range": {"from": progress["status"]["head_commit"], "to": f"fix{fix_id}"}
        })

        (project_dir / "progress.json").write_text(json.dumps(progress, indent=2))

        return "continue", f"Fixed issues for {feature_id}, ready for re-review"

    @staticmethod
    def architecture_response(project_dir: Path):
        """
        Simulates ARCHITECTURE agent doing codebase review.
        Architecture reviews now go to reviews.json (unified with code reviews).
        """
        progress = json.loads((project_dir / "progress.json").read_text())
        reviews = json.loads((project_dir / "reviews.json").read_text())

        review_id = max([r["review_id"] for r in reviews.get("reviews", [])], default=0) + 1
        reviews["reviews"].append({
            "review_id": review_id,
            "feature_id": None,
            "feature_name": f"Architecture Review #{review_id}",
            "branch": None,
            "agent_type": "ARCHITECTURE",
            "timestamp": "2025-01-29T14:00:00Z",
            "trigger": "Every 5 features",
            "features_completed": progress["status"]["features_completed"],
            "verdict": "PASS",
            "health_status": "GOOD",
            "metrics": {
                "total_files": 10,
                "total_lines": 500,
                "largest_file": {"path": "app/main.py", "lines": 100},
                "test_coverage_percent": 85
            },
            "issues": {"critical": [], "major": [], "minor": [], "suggestions": []},
            "checklist": {
                "structure": "PASS",
                "dependencies": "PASS",
                "security": "PASS",
                "testing": "PASS",
                "code_quality": "PASS"
            },
            "summary": "Architecture review: GOOD health status"
        })
        (project_dir / "reviews.json").write_text(json.dumps(reviews, indent=2))

        # Update progress
        progress["status"]["current_phase"] = "IMPLEMENT"

        session_id = len(progress["sessions"]) + 1
        progress["sessions"].append({
            "session_id": session_id,
            "agent_type": "ARCHITECTURE",
            "started_at": "2025-01-29T14:00:00Z",
            "completed_at": "2025-01-29T14:30:00Z",
            "summary": "Architecture review: GOOD health status",
            "features_touched": [],
            "outcome": "SUCCESS",
            "commits": [],
            "commit_range": None
        })

        (project_dir / "progress.json").write_text(json.dumps(progress, indent=2))

        return "continue", "Architecture review complete"


# -----------------------------------------------------------------------------
# End-to-End Tests
# -----------------------------------------------------------------------------

class TestEndToEndFlow:
    """
    End-to-end tests simulating complete project builds.
    """

    @pytest.mark.asyncio
    async def test_e2e_two_features_both_pass_first_try(self, e2e_config):
        """
        E2E: Build 2 features, both pass review on first try.

        Expected flow:
        1. INITIALIZER creates feature_list.json
        2. IMPLEMENT F001
        3. REVIEW F001 → PASS
        4. IMPLEMENT F002
        5. REVIEW F002 → PASS
        6. Complete (max_iterations or all features done)
        """
        project_dir = e2e_config.project_dir
        call_count = [0]
        feature_index = [0]

        async def mock_run_agent_session(prompt, project_dir, model, config):
            call_count[0] += 1

            # Determine which agent based on what files exist and their state
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                # First call - INITIALIZER
                return MockAgentResponses.initializer_response(project_dir, feature_count=2)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]

            if phase == "IMPLEMENT":
                # Find next feature to implement
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if not f["passes"]:
                        return MockAgentResponses.implement_response(project_dir, f["id"])
                # All done
                return "continue", "All features implemented"

            elif phase == "REVIEW":
                return MockAgentResponses.review_pass_response(project_dir, current_feature)

            return "continue", "Unknown state"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            # Limit iterations to prevent infinite loop
            e2e_config.max_iterations = 6

            await run_autonomous_agent(e2e_config)

        # Verify results
        feature_list = json.loads((project_dir / "feature_list.json").read_text())
        progress = json.loads((project_dir / "progress.json").read_text())

        # Both features should be passing
        assert all(f["passes"] for f in feature_list["features"])

        # Should have completed 2 features
        assert progress["status"]["features_completed"] == 2
        assert progress["status"]["features_passing"] == 2

        # Check session history
        session_types = [s["agent_type"] for s in progress["sessions"]]
        assert "INITIALIZER" in session_types
        assert session_types.count("IMPLEMENT") == 2
        assert session_types.count("REVIEW") == 2

    @pytest.mark.asyncio
    async def test_e2e_feature_needs_fix_cycle(self, e2e_config):
        """
        E2E: Feature fails review, gets fixed, then passes.

        Expected flow:
        1. INITIALIZER
        2. IMPLEMENT F001
        3. REVIEW F001 → REQUEST_CHANGES
        4. FIX F001
        5. REVIEW F001 → PASS
        6. Done (max_iterations)
        """
        project_dir = e2e_config.project_dir
        review_count = [0]

        async def mock_run_agent_session(prompt, project_dir, model, config):
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                return MockAgentResponses.initializer_response(project_dir, feature_count=1)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]

            if phase == "IMPLEMENT":
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if not f["passes"]:
                        return MockAgentResponses.implement_response(project_dir, f["id"])
                return "continue", "All done"

            elif phase == "REVIEW":
                review_count[0] += 1
                if review_count[0] == 1:
                    # First review - fail
                    return MockAgentResponses.review_request_changes_response(
                        project_dir, current_feature, ["Missing tests", "No error handling"]
                    )
                else:
                    # Second review (after fix) - pass
                    return MockAgentResponses.review_pass_response(project_dir, current_feature)

            elif phase == "FIX":
                return MockAgentResponses.fix_response(project_dir, current_feature)

            return "continue", "Unknown"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            e2e_config.max_iterations = 6
            e2e_config.feature_count = 1

            await run_autonomous_agent(e2e_config)

        # Verify
        feature_list = json.loads((project_dir / "feature_list.json").read_text())
        progress = json.loads((project_dir / "progress.json").read_text())
        reviews = json.loads((project_dir / "reviews.json").read_text())

        # Feature should pass after fix
        assert feature_list["features"][0]["passes"] is True

        # Should have review entries
        assert len(reviews["reviews"]) == 2  # REQUEST_CHANGES + PASS
        assert reviews["reviews"][0]["verdict"] == "REQUEST_CHANGES"
        assert reviews["reviews"][1]["verdict"] == "PASS"

        # Should have fix entry
        assert len(reviews["fixes"]) == 1

        # Session flow should include FIX
        session_types = [s["agent_type"] for s in progress["sessions"]]
        assert "FIX" in session_types

    @pytest.mark.asyncio
    async def test_e2e_architecture_review_triggers(self, e2e_config):
        """
        E2E: Architecture review triggers after N features.

        Expected flow with architecture_interval=2:
        1. INITIALIZER
        2. IMPLEMENT F001 → REVIEW → PASS (1 complete)
        3. IMPLEMENT F002 → REVIEW → PASS (2 complete)
        4. ARCHITECTURE review triggers
        5. Continue to next feature
        """
        project_dir = e2e_config.project_dir
        e2e_config.architecture_interval = 2
        e2e_config.feature_count = 3
        arch_review_called = [False]

        async def mock_run_agent_session(prompt, project_dir, model, config):
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                return MockAgentResponses.initializer_response(project_dir, feature_count=3)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]
            features_completed = progress["status"]["features_completed"]

            if phase == "IMPLEMENT":
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if not f["passes"]:
                        return MockAgentResponses.implement_response(project_dir, f["id"])
                return "continue", "All done"

            elif phase == "REVIEW":
                # After passing, check if arch review should trigger
                result = MockAgentResponses.review_pass_response(project_dir, current_feature)

                # Re-read progress after update
                updated_progress = json.loads((project_dir / "progress.json").read_text())
                completed = updated_progress["status"]["features_completed"]

                # Manually trigger architecture phase if at interval
                if completed > 0 and completed % config.architecture_interval == 0:
                    updated_progress["status"]["current_phase"] = "ARCHITECTURE"
                    (project_dir / "progress.json").write_text(json.dumps(updated_progress, indent=2))

                return result

            elif phase == "ARCHITECTURE":
                arch_review_called[0] = True
                return MockAgentResponses.architecture_response(project_dir)

            return "continue", "Unknown"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            e2e_config.max_iterations = 10

            await run_autonomous_agent(e2e_config)

        # Verify architecture review was called
        assert arch_review_called[0] is True

        # Check reviews.json has architecture review entry
        reviews = json.loads((project_dir / "reviews.json").read_text())
        arch_reviews = [r for r in reviews["reviews"] if r["agent_type"] == "ARCHITECTURE"]
        assert len(arch_reviews) >= 1

        # Session history should include ARCHITECTURE
        progress = json.loads((project_dir / "progress.json").read_text())
        session_types = [s["agent_type"] for s in progress["sessions"]]
        assert "ARCHITECTURE" in session_types

    @pytest.mark.asyncio
    async def test_e2e_multiple_fix_cycles(self, e2e_config):
        """
        E2E: Feature requires multiple fix attempts.

        Flow:
        1. INITIALIZER
        2. IMPLEMENT → REVIEW (FAIL) → FIX → REVIEW (FAIL) → FIX → REVIEW (PASS)
        """
        project_dir = e2e_config.project_dir
        review_count = [0]

        async def mock_run_agent_session(prompt, project_dir, model, config):
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                return MockAgentResponses.initializer_response(project_dir, feature_count=1)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]

            if phase == "IMPLEMENT":
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if not f["passes"]:
                        return MockAgentResponses.implement_response(project_dir, f["id"])
                return "continue", "Done"

            elif phase == "REVIEW":
                review_count[0] += 1
                if review_count[0] < 3:
                    # First two reviews fail
                    return MockAgentResponses.review_request_changes_response(
                        project_dir, current_feature, [f"Issue from review {review_count[0]}"]
                    )
                else:
                    # Third review passes
                    return MockAgentResponses.review_pass_response(project_dir, current_feature)

            elif phase == "FIX":
                return MockAgentResponses.fix_response(project_dir, current_feature)

            return "continue", "Unknown"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            e2e_config.max_iterations = 10
            e2e_config.feature_count = 1

            await run_autonomous_agent(e2e_config)

        # Verify
        reviews = json.loads((project_dir / "reviews.json").read_text())

        # Should have 3 reviews (2 fails, 1 pass)
        assert len(reviews["reviews"]) == 3
        assert reviews["reviews"][0]["verdict"] == "REQUEST_CHANGES"
        assert reviews["reviews"][1]["verdict"] == "REQUEST_CHANGES"
        assert reviews["reviews"][2]["verdict"] == "PASS"

        # Should have 2 fix entries
        assert len(reviews["fixes"]) == 2

        # Feature should ultimately pass
        feature_list = json.loads((project_dir / "feature_list.json").read_text())
        assert feature_list["features"][0]["passes"] is True

    @pytest.mark.asyncio
    async def test_e2e_error_recovery(self, e2e_config):
        """
        E2E: Agent encounters error, recovers on retry.
        """
        project_dir = e2e_config.project_dir
        call_count = [0]

        async def mock_run_agent_session(prompt, project_dir, model, config):
            call_count[0] += 1
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                # First call - simulate error
                if call_count[0] == 1:
                    return "error", "Simulated network error"
                # Retry succeeds
                return MockAgentResponses.initializer_response(project_dir, feature_count=1)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]

            if phase == "IMPLEMENT":
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if not f["passes"]:
                        return MockAgentResponses.implement_response(project_dir, f["id"])
                return "continue", "Done"

            elif phase == "REVIEW":
                return MockAgentResponses.review_pass_response(project_dir, current_feature)

            return "continue", "Unknown"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            e2e_config.max_iterations = 5
            e2e_config.feature_count = 1

            await run_autonomous_agent(e2e_config)

        # Despite error, should eventually succeed
        assert (project_dir / "feature_list.json").exists()
        feature_list = json.loads((project_dir / "feature_list.json").read_text())
        assert feature_list["features"][0]["passes"] is True

    @pytest.mark.asyncio
    async def test_e2e_verifies_correct_models_used(self, e2e_config):
        """
        E2E: Verify correct models are used for each agent type.
        """
        project_dir = e2e_config.project_dir
        models_used = []

        async def mock_run_agent_session(prompt, project_dir, model, config):
            models_used.append(model)
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                return MockAgentResponses.initializer_response(project_dir, feature_count=1)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]

            if phase == "IMPLEMENT":
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if not f["passes"]:
                        return MockAgentResponses.implement_response(project_dir, f["id"])
                return "continue", "Done"

            elif phase == "REVIEW":
                return MockAgentResponses.review_pass_response(project_dir, current_feature)

            return "continue", "Unknown"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            e2e_config.max_iterations = 4
            e2e_config.feature_count = 1
            e2e_config.implement_model = "sonnet"
            e2e_config.review_model = "opus"

            await run_autonomous_agent(e2e_config)

        # Should have used sonnet for INITIALIZER and IMPLEMENT, opus for REVIEW
        assert "sonnet" in models_used  # INITIALIZER uses implement_model
        assert "opus" in models_used    # REVIEW uses review_model

    @pytest.mark.asyncio
    async def test_e2e_respects_max_iterations(self, e2e_config):
        """
        E2E: Orchestrator stops at max_iterations.
        """
        project_dir = e2e_config.project_dir
        call_count = [0]

        async def mock_run_agent_session(prompt, project_dir, model, config):
            call_count[0] += 1
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                # Create many features to ensure we hit max_iterations
                return MockAgentResponses.initializer_response(project_dir, feature_count=100)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]

            if phase == "IMPLEMENT":
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if not f["passes"]:
                        return MockAgentResponses.implement_response(project_dir, f["id"])
                return "continue", "Done"

            elif phase == "REVIEW":
                return MockAgentResponses.review_pass_response(project_dir, current_feature)

            return "continue", "Unknown"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            e2e_config.max_iterations = 5

            await run_autonomous_agent(e2e_config)

        # Should have stopped at or before max_iterations
        assert call_count[0] <= 5


# -----------------------------------------------------------------------------
# Flow Verification Tests
# -----------------------------------------------------------------------------

class TestFlowVerification:
    """
    Tests that verify the flow rules are enforced.
    """

    @pytest.mark.asyncio
    async def test_only_review_marks_passing(self, e2e_config):
        """
        Verify that only REVIEW agent can mark features as passing.

        Tracks state transitions to ensure:
        - After IMPLEMENT: feature is NOT passing
        - After REVIEW (PASS): feature IS passing
        """
        project_dir = e2e_config.project_dir
        state_checks = {
            "after_implement_passes": None,
            "before_review_passes": None,
            "after_review_passes": None,
        }

        async def mock_run_agent_session(prompt, project_dir, model, config):
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                return MockAgentResponses.initializer_response(project_dir, feature_count=1)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]

            if phase == "IMPLEMENT":
                # Find a feature that hasn't passed yet
                feature_list = json.loads(feature_list_path.read_text())
                target_feature = None
                for f in feature_list["features"]:
                    if not f["passes"]:
                        target_feature = f["id"]
                        break

                if target_feature is None:
                    return "continue", "All features done"

                result = MockAgentResponses.implement_response(project_dir, target_feature)

                # Check: after IMPLEMENT, the feature should NOT be passing
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if f["id"] == target_feature:
                        state_checks["after_implement_passes"] = f["passes"]
                        break

                return result

            elif phase == "REVIEW":
                # Check: before REVIEW marks it
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if f["id"] == current_feature:
                        state_checks["before_review_passes"] = f["passes"]
                        break

                result = MockAgentResponses.review_pass_response(project_dir, current_feature)

                # Check: after REVIEW marks it
                feature_list = json.loads(feature_list_path.read_text())
                for f in feature_list["features"]:
                    if f["id"] == current_feature:
                        state_checks["after_review_passes"] = f["passes"]
                        break

                return result

            return "continue", "Unknown"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            e2e_config.max_iterations = 4
            e2e_config.feature_count = 1

            await run_autonomous_agent(e2e_config)

        # Verify the state transitions
        assert state_checks["after_implement_passes"] is False, \
            "IMPLEMENT should NOT mark feature as passing"
        assert state_checks["before_review_passes"] is False, \
            "Feature should not be passing before REVIEW"
        assert state_checks["after_review_passes"] is True, \
            "REVIEW should mark feature as passing"

    @pytest.mark.asyncio
    async def test_fix_does_not_merge(self, e2e_config):
        """
        Verify that FIX agent does not merge or mark passing.
        """
        project_dir = e2e_config.project_dir
        review_count = [0]

        async def mock_run_agent_session(prompt, project_dir, model, config):
            feature_list_path = project_dir / "feature_list.json"

            if not feature_list_path.exists():
                return MockAgentResponses.initializer_response(project_dir, feature_count=1)

            progress = json.loads((project_dir / "progress.json").read_text())
            phase = progress["status"]["current_phase"]
            current_feature = progress["status"]["current_feature"]

            if phase == "IMPLEMENT":
                return MockAgentResponses.implement_response(project_dir, "F001")

            elif phase == "REVIEW":
                review_count[0] += 1
                if review_count[0] == 1:
                    return MockAgentResponses.review_request_changes_response(
                        project_dir, current_feature, ["Issue"]
                    )
                return MockAgentResponses.review_pass_response(project_dir, current_feature)

            elif phase == "FIX":
                # Before FIX
                feature_list = json.loads(feature_list_path.read_text())
                assert feature_list["features"][0]["passes"] is False

                result = MockAgentResponses.fix_response(project_dir, current_feature)

                # After FIX - should still NOT be passing
                feature_list = json.loads(feature_list_path.read_text())
                assert feature_list["features"][0]["passes"] is False, "FIX should not mark passing"

                # Phase should be REVIEW (for re-verification)
                progress = json.loads((project_dir / "progress.json").read_text())
                assert progress["status"]["current_phase"] == "REVIEW"

                return result

            return "continue", "Unknown"

        with patch('autonomous_agent_demo.run_agent_session', side_effect=mock_run_agent_session):
            e2e_config.max_iterations = 6
            e2e_config.feature_count = 1

            await run_autonomous_agent(e2e_config)
