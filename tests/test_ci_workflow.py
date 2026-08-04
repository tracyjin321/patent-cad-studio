from pathlib import Path

import yaml


def test_component_library_ci_installs_frontend_runtime_dependencies_before_pytest():
    workflow_path = Path(__file__).parents[1] / ".github" / "workflows" / "component-library.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    commands = [
        step["run"]
        for step in workflow["jobs"]["validate"]["steps"]
        if "run" in step
    ]

    assert "npm ci" in commands
    assert commands.index("npm ci") < commands.index("PYTHONPATH=. pytest -q")
