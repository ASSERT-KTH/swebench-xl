"""Basic tests for the trajectory analysis tool."""
import json
import os
import pytest
from pathlib import Path
from traj.loader import load_trajectory, load_trajectories
from traj.bash_classifier import classify_bash
from traj.models import Operation

EXAMPLES_DIR = Path(os.environ.get(
    "TRAJ_EXAMPLES_DIR",
    "/Users/pontusberglund/Documents/Example Trajectories",
))


# --- bash classifier tests ---

class TestBashClassifier:

    def test_cat_is_read(self):
        ops = classify_bash("cat /path/to/file.java", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Read"
        assert ops[0].path == "/path/to/file.java"

    def test_head_is_read(self):
        ops = classify_bash("head -50 /app/src/Main.java", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Read"

    def test_sed_n_is_read(self):
        ops = classify_bash("sed -n '1,50p' /app/src/Main.java", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Read"

    def test_sed_i_is_write(self):
        ops = classify_bash("sed -i 's/foo/bar/g' /app/src/Main.java", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Write"

    def test_find_is_explore(self):
        ops = classify_bash("find /app -type f -name '*.java'", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Explore"
        assert ops[0].path == "/app"

    def test_ls_is_explore(self):
        ops = classify_bash("ls -la /app/src", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Explore"
        assert ops[0].path == "/app/src"

    def test_rg_files_is_explore_only(self):
        ops = classify_bash("rg --files /app | rg 'pattern'", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Explore"

    def test_rg_content_is_explore_and_read(self):
        ops = classify_bash("rg 'pattern' /app/src", step=1)
        assert len(ops) == 2
        actions = {op.action for op in ops}
        assert "Explore" in actions
        assert "Read" in actions

    def test_redirect_is_write(self):
        ops = classify_bash("echo 'hello' > /tmp/output.txt", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Write"
        assert ops[0].path == "/tmp/output.txt"

    def test_chained_commands(self):
        ops = classify_bash("cd /app && ls -la && cat README.md", step=1)
        assert len(ops) >= 2
        actions = [op.action for op in ops]
        assert "Explore" in actions
        assert "Read" in actions

    def test_bash_wrapper_stripped(self):
        ops = classify_bash("/bin/bash -lc 'cat /app/file.java'", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Read"
        assert ops[0].path == "/app/file.java"

    def test_unknown_command_is_other(self):
        ops = classify_bash("some-unknown-command --flag", step=1)
        assert len(ops) == 1
        assert ops[0].action == "Other"

    def test_sub_agent_flag(self):
        ops = classify_bash("cat /file.txt", step=1, sub_agent=True, sub_agent_name="test-agent")
        assert ops[0].sub_agent is True
        assert ops[0].sub_agent_name == "test-agent"


# --- adapter / loader tests ---

@pytest.mark.skipif(not EXAMPLES_DIR.exists(), reason="Example trajectories not available")
class TestCopilotAdapter:

    def test_loads_trajectory(self):
        result = load_trajectory(str(EXAMPLES_DIR / "Copilot CLI" / "trajectory_1.json"))
        assert result.agent == "copilot"
        assert result.session_id != ""
        assert len(result.operations) > 0

    def test_has_read_write_explore(self):
        result = load_trajectory(str(EXAMPLES_DIR / "Copilot CLI" / "trajectory_1.json"))
        actions = {op.action for op in result.operations}
        assert "Read" in actions
        assert "Write" in actions
        assert "Explore" in actions

    def test_sub_agent_detected(self):
        result = load_trajectory(str(EXAMPLES_DIR / "Copilot CLI" / "trajectory_1.json"))
        sub_ops = [op for op in result.operations if op.sub_agent]
        assert len(sub_ops) > 0
        assert any(op.sub_agent_name for op in sub_ops)

    def test_detail_field_populated(self):
        result = load_trajectory(str(EXAMPLES_DIR / "Copilot CLI" / "trajectory_1.json"))
        for op in result.operations:
            assert op.detail != "", f"Empty detail for {op.tool} at step {op.step}"


@pytest.mark.skipif(not EXAMPLES_DIR.exists(), reason="Example trajectories not available")
class TestCodexAdapter:

    def test_loads_trajectory(self):
        result = load_trajectory(str(EXAMPLES_DIR / "Codex CLI" / "trajectory_1.json"))
        assert result.agent == "codex"
        assert len(result.operations) > 0

    def test_has_read_write_explore(self):
        result = load_trajectory(str(EXAMPLES_DIR / "Codex CLI" / "trajectory_1.json"))
        actions = {op.action for op in result.operations}
        assert "Read" in actions
        assert "Write" in actions
        assert "Explore" in actions

    def test_file_edit_is_write(self):
        result = load_trajectory(str(EXAMPLES_DIR / "Codex CLI" / "trajectory_1.json"))
        writes = [op for op in result.operations if op.action == "Write"]
        file_edits = [op for op in writes if op.tool == "file_edit"]
        assert len(file_edits) > 0
        assert all(op.path != "" for op in file_edits)


@pytest.mark.skipif(not EXAMPLES_DIR.exists(), reason="Example trajectories not available")
class TestOpenHandsAdapter:

    def test_loads_trajectory(self):
        result = load_trajectory(str(EXAMPLES_DIR / "OpenHands" / "trajectory_1.json"))
        assert result.agent == "openhands"
        assert len(result.operations) > 0

    def test_has_read_write_explore(self):
        result = load_trajectory(str(EXAMPLES_DIR / "OpenHands" / "trajectory_1.json"))
        actions = {op.action for op in result.operations}
        assert "Read" in actions
        assert "Write" in actions
        assert "Explore" in actions

    def test_read_tool_has_path(self):
        result = load_trajectory(str(EXAMPLES_DIR / "OpenHands" / "trajectory_1.json"))
        reads = [op for op in result.operations if op.tool == "read"]
        assert len(reads) > 0
        assert all(op.path != "" for op in reads)


@pytest.mark.skipif(not EXAMPLES_DIR.exists(), reason="Example trajectories not available")
class TestDirectoryLoading:

    def test_load_all(self):
        results = load_trajectories(str(EXAMPLES_DIR))
        assert len(results) == 9  # 3 agents x 3 trajectories

    def test_agents_detected(self):
        results = load_trajectories(str(EXAMPLES_DIR))
        agents = {r.agent for r in results}
        assert agents == {"copilot", "codex", "openhands"}


# --- output format tests ---

class TestOutputFormat:

    def test_to_dict_excludes_none_sub_agent_name(self):
        op = Operation(step=1, action="Read", path="/file.txt", tool="cat")
        d = op.to_dict()
        assert "sub_agent_name" not in d

    def test_to_dict_includes_sub_agent_name_when_set(self):
        op = Operation(step=1, action="Read", path="/file.txt", tool="cat",
                       sub_agent=True, sub_agent_name="test")
        d = op.to_dict()
        assert d["sub_agent_name"] == "test"
