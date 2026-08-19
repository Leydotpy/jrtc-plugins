from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"


@dataclass(frozen=True)
class Rule:
    source_root: str
    allowed_workspace_imports: frozenset[str]


RULES: dict[str, Rule] = {
    "stream-orchestrator": Rule("stream_orchestrator", frozenset()),
    "stream-orchestrator-process": Rule(
        "stream_orchestrator_process", frozenset({"stream_orchestrator"})
    ),
    "stream-orchestrator-ffmpeg": Rule(
        "stream_orchestrator_ffmpeg",
        frozenset({"stream_orchestrator", "stream_orchestrator_process"}),
    ),
    "stream-orchestrator-gstreamer": Rule(
        "stream_orchestrator_gstreamer",
        frozenset({"stream_orchestrator", "stream_orchestrator_process"}),
    ),
    "stream-orchestrator-srs": Rule("stream_orchestrator_srs", frozenset({"stream_orchestrator"})),
    "jrtc-stream": Rule("janus_streaming", frozenset()),
    "janus-stream-orchestrator": Rule(
        "janus_stream_orchestrator",
        frozenset({"janus_streaming", "stream_orchestrator"}),
    ),
    "stream-orchestrator-django": Rule(
        "stream_orchestrator_django", frozenset({"stream_orchestrator"})
    ),
    "stream-orchestrator-qt": Rule("stream_orchestrator_qt", frozenset({"stream_orchestrator"})),
}

WORKSPACE_IMPORTS = frozenset(rule.source_root for rule in RULES.values())


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            values.add(node.module)
    return values


def imports_for(path: Path) -> set[str]:
    return {module.split(".", 1)[0] for module in imported_modules(path)}


def check_shell_usage(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    errors: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant):
                if keyword.value.value is True:
                    errors.append(f"{path}: shell=True is forbidden")
    return errors


def main() -> int:
    errors: list[str] = []
    for project, rule in RULES.items():
        source_dir = PROJECTS / project / "src" / rule.source_root
        if not source_dir.is_dir():
            errors.append(f"missing source package: {source_dir}")
            continue
        for path in source_dir.rglob("*.py"):
            modules = imported_modules(path)
            imported = imports_for(path)
            forbidden = (imported & WORKSPACE_IMPORTS) - rule.allowed_workspace_imports
            if forbidden:
                errors.append(
                    f"{path}: forbidden workspace imports: {', '.join(sorted(forbidden))}"
                )
            errors.extend(check_shell_usage(path))

            forbidden_streaming_modules = {
                "jrtc.lib.plugins.streaming",
                "jrtc.models.streaming",
            }
            if any(
                module in forbidden_streaming_modules
                or any(module.startswith(f"{prefix}.") for prefix in forbidden_streaming_modules)
                for module in modules
            ):
                errors.append(
                    f"{path}: Streaming models and helpers must be owned by janus_streaming"
                )

            if "jrtc" in imported:
                expected = PROJECTS / "jrtc-stream" / "src" / "janus_streaming" / "_compat.py"
                if path != expected:
                    errors.append(
                        "jrtc imports are allowed only in "
                        f"{expected.relative_to(ROOT)}; found in {path}"
                    )

    streaming_pyproject = PROJECTS / "jrtc-stream" / "pyproject.toml"
    streaming_metadata = tomllib.loads(streaming_pyproject.read_text(encoding="utf-8"))["project"]
    dependencies = streaming_metadata.get("dependencies", [])
    if "jrtc>=3.1,<4" not in dependencies:
        errors.append("jrtc-stream must depend on the supported jrtc>=3.1,<4 range")
    if any(
        dependency.lower().startswith(("janus-api>", "janus-api=", "janus-api<"))
        for dependency in dependencies
    ):
        errors.append("jrtc-stream must not depend on the legacy janus-api distribution")
    entry_points = streaming_metadata.get("entry-points", {}).get("jrtc.plugins", {})
    if entry_points.get("streaming") != "janus_streaming._compat:StreamingPlugin":
        errors.append(
            "jrtc-stream must publish its concrete class as the 'streaming' "
            "jrtc.plugins entry point"
        )

    core = PROJECTS / "stream-orchestrator" / "src" / "stream_orchestrator"
    forbidden_core = {"django", "PyQt6", "PySide6", "httpx", "pydantic", "subprocess"}
    for path in core.rglob("*.py"):
        found = imports_for(path) & forbidden_core
        if found:
            errors.append(f"{path}: framework-neutral core imports {sorted(found)}")

    if errors:
        print("Dependency-boundary check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Dependency-boundary check passed for all workspace packages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
