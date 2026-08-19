"""Verify every independently installable sibling Janus named-plugin project.

The project set is discovered on every invocation. ``fast`` performs boundary,
metadata, import-target, and available-test checks. ``full`` also requires a
test suite for every project and validates independently built artifacts. The
nested ``jrtc-stream`` workspace has its own AGENTS.md-mandated
verification and is deliberately excluded here.
"""

from __future__ import annotations

import argparse
import ast
import email.parser
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = ROOT.parent / "main" / "v3.1"
CORE_SOURCE = CORE_ROOT / "src"

PLUGIN_LAYOUT = {
    "jrtc-audio": ("audiobridge", "jrtc_audio"),
    "jrtc-call": ("videocall", "jrtc_call"),
    "jrtc-echo": ("echotest", "jrtc_echo"),
    "jrtc-nosip": ("nosip", "jrtc_nosip"),
    "jrtc-rec": ("recordplay", "jrtc_rec"),
    "jrtc-room": ("videoroom", "jrtc_video"),
    "jrtc-sip": ("sip", "janus_sip_plugin"),
    "jrtc-text": ("textroom", "janus_textroom_plugin"),
}
REQUIRED_IDENTIFIERS = frozenset(identifier for identifier, _ in PLUGIN_LAYOUT.values())
GENERATED_DIRECTORY_NAMES = frozenset(
    {
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
    }
)
GENERATED_FILE_NAMES = frozenset({".coverage", "coverage.xml"})


@dataclass(frozen=True, slots=True)
class PluginProject:
    path: Path
    distribution: str
    identifier: str
    import_name: str
    entry_point_target: str

    @property
    def tests(self) -> tuple[Path, ...]:
        tests_dir = self.path / "tests"
        if not tests_dir.is_dir():
            return ()
        return tuple(sorted(tests_dir.rglob("test*.py")))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("fast", "full"),
        default="fast",
        help="fast runs static/runtime checks and available tests; full also builds artifacts",
    )
    return parser.parse_args()


def requirement_name(requirement: str) -> str:
    value = re.split(r"[<>=!~;\[\s]", requirement, maxsplit=1)[0]
    return value.strip().lower().replace("_", "-")


def normalized_requirement(requirement: str) -> str:
    return "".join(requirement.lower().replace("_", "-").split())


def discover_projects() -> tuple[list[PluginProject], list[str]]:
    projects: list[PluginProject] = []
    errors: list[str] = []
    for directory, (identifier, import_name) in sorted(PLUGIN_LAYOUT.items()):
        path = ROOT / directory
        if not path.is_dir():
            errors.append(f"missing required plugin project directory: {directory}")
            continue
        pyproject_path = path / "pyproject.toml"
        if not pyproject_path.is_file():
            errors.append(
                f"{path.name}: directory matches the plugin convention but has no pyproject.toml"
            )
            continue
        try:
            document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.name}: cannot parse pyproject.toml: {exc}")
            continue

        project = document.get("project")
        if not isinstance(project, dict):
            errors.append(f"{path.name}: pyproject.toml has no [project] table")
            continue
        distribution = project.get("name")
        if not isinstance(distribution, str):
            errors.append(f"{path.name}: [project].name must be a string")
            continue
        entry_points = project.get("entry-points", {})
        group = entry_points.get("jrtc.plugins", {}) if isinstance(entry_points, dict) else {}
        target = group.get(identifier) if isinstance(group, dict) else None
        projects.append(
            PluginProject(
                path=path,
                distribution=distribution,
                identifier=identifier,
                import_name=import_name,
                entry_point_target=target if isinstance(target, str) else "",
            )
        )
    return projects, errors


def generated_artifacts(project: PluginProject) -> list[Path]:
    found: set[Path] = set()
    for path in project.path.rglob("*"):
        relative = path.relative_to(project.path)
        if any(
            part in GENERATED_DIRECTORY_NAMES or part.endswith(".egg-info")
            for part in relative.parts
        ):
            first_generated = next(
                index
                for index, part in enumerate(relative.parts)
                if part in GENERATED_DIRECTORY_NAMES or part.endswith(".egg-info")
            )
            found.add(project.path.joinpath(*relative.parts[: first_generated + 1]))
            continue
        if not path.is_file():
            continue
        if (
            path.name in GENERATED_FILE_NAMES
            or path.suffix in {".pyc", ".pyo", ".whl"}
            or path.name.endswith(".tar.gz")
        ):
            found.add(path)
    return sorted(found)


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
            if node.module in {"jrtc.models", "jrtc.lib.plugins"}:
                modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def check_source_boundaries(project: PluginProject, all_identifiers: frozenset[str]) -> list[str]:
    errors: list[str] = []
    forbidden = {
        *(f"jrtc.models.{identifier}" for identifier in all_identifiers | {"streaming"}),
        *(f"jrtc.lib.plugins.{identifier}" for identifier in all_identifiers | {"streaming"}),
    }
    for source in sorted((*project.path.glob("src/**/*.py"), *project.path.glob("tests/**/*.py"))):
        try:
            text = source.read_text(encoding="utf-8")
            modules = imported_modules(source)
        except (OSError, SyntaxError) as exc:
            errors.append(f"{source.relative_to(ROOT)}: cannot parse Python source: {exc}")
            continue
        references = {
            prefix
            for prefix in forbidden
            if prefix in text
            or any(module == prefix or module.startswith(f"{prefix}.") for module in modules)
        }
        if references:
            errors.append(
                f"{source.relative_to(ROOT)}: imports/references named core modules "
                f"{sorted(references)}"
            )
    return errors


def validate_project(
    project: PluginProject, all_identifiers: frozenset[str], *, full: bool
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    pyproject_path = project.path / "pyproject.toml"
    document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    metadata = document["project"]

    if project.distribution != project.path.name:
        errors.append(
            f"{project.path.name}: distribution must match its directory; "
            f"found {project.distribution!r}"
        )
    if not isinstance(metadata.get("version"), str) or not metadata["version"].strip():
        errors.append(f"{project.path.name}: [project].version is required")
    if not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
        errors.append(f"{project.path.name}: [project].description is required")
    if metadata.get("requires-python") != ">=3.12":
        errors.append(f"{project.path.name}: [project].requires-python must be >=3.12")
    readme = metadata.get("readme")
    if not isinstance(readme, str) or not (project.path / readme).is_file():
        errors.append(f"{project.path.name}: [project].readme must name an existing file")
    if not isinstance(metadata.get("license"), (str, dict)):
        errors.append(f"{project.path.name}: [project].license is required")
    if not isinstance(metadata.get("authors"), list) or not metadata["authors"]:
        errors.append(f"{project.path.name}: [project].authors is required")

    build_system = document.get("build-system")
    if not isinstance(build_system, dict) or not build_system.get("build-backend"):
        errors.append(f"{project.path.name}: a PEP 517 [build-system] is required")

    dependencies = metadata.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) for item in dependencies
    ):
        errors.append(f"{project.path.name}: [project].dependencies must be a string array")
        dependencies = []
    core_requirements = [
        normalized_requirement(item)
        for item in dependencies
        if requirement_name(item) == "jrtc"
    ]
    if core_requirements not in (["jrtc>=3.1,<4"], ["jrtc<4,>=3.1"]):
        errors.append(
            f"{project.path.name}: require exactly one unconditional jrtc>=3.1,<4 "
            f"dependency; found {core_requirements or 'none'}"
        )
    if any(requirement_name(item) == "janus-api" for item in dependencies):
        errors.append(f"{project.path.name}: legacy janus-api dependency is forbidden")

    entry_points = metadata.get("entry-points", {})
    group = entry_points.get("jrtc.plugins", {}) if isinstance(entry_points, dict) else {}
    if not isinstance(group, dict) or set(group) != {project.identifier}:
        errors.append(
            f"{project.path.name}: publish exactly one jrtc.plugins entry named "
            f"{project.identifier!r}"
        )
    expected_prefix = f"{project.import_name}:"
    if not project.entry_point_target.startswith(expected_prefix):
        errors.append(
            f"{project.path.name}: entry point must target {expected_prefix}<PluginClass>; "
            f"found {project.entry_point_target!r}"
        )
    elif not project.entry_point_target.partition(":")[2]:
        errors.append(f"{project.path.name}: entry point class name is empty")

    package = project.path / "src" / project.import_name
    if not (package / "__init__.py").is_file():
        errors.append(f"{project.path.name}: missing source package {project.import_name}")
    if not (package / "py.typed").is_file():
        errors.append(f"{project.path.name}: wheel typing marker py.typed is required")

    artifacts = generated_artifacts(project)
    if artifacts:
        rendered = ", ".join(str(path.relative_to(ROOT)) for path in artifacts)
        errors.append(f"{project.path.name}: generated artifacts are forbidden: {rendered}")

    errors.extend(check_source_boundaries(project, all_identifiers))
    if not project.tests:
        message = f"{project.path.name}: no tests/test*.py files found"
        if full:
            errors.append(message)
        else:
            warnings.append(message)
    return errors, warnings


def command_environment(project: PluginProject) -> dict[str, str]:
    environment = os.environ.copy()
    python_paths = [str(project.path / "src"), str(CORE_SOURCE)]
    existing = environment.get("PYTHONPATH")
    if existing:
        python_paths.append(existing)
    environment["PYTHONPATH"] = os.pathsep.join(python_paths)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def run_command(
    label: str,
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout: float,
) -> str | None:
    print(f"\n==> {label}", flush=True)
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"{label}: command could not complete: {exc}"
    if completed.returncode:
        return f"{label}: command exited with status {completed.returncode}"
    return None


def smoke_test(project: PluginProject) -> str | None:
    module, _, attribute = project.entry_point_target.partition(":")
    script = (
        "import importlib, sys; "
        "module = importlib.import_module(sys.argv[1]); "
        "plugin = getattr(module, sys.argv[2]); "
        "assert plugin.identifier == sys.argv[3]; "
        "assert plugin.name == 'janus.plugin.' + sys.argv[3]"
    )
    return run_command(
        f"{project.path.name}: entry-point import",
        [sys.executable, "-c", script, module, attribute, project.identifier],
        cwd=ROOT,
        environment=command_environment(project),
        timeout=60,
    )


def run_tests(project: PluginProject) -> str | None:
    if not project.tests:
        return None
    return run_command(
        f"{project.path.name}: tests",
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-q",
            str(project.path / "tests"),
        ],
        cwd=ROOT,
        environment=command_environment(project),
        timeout=300,
    )


def inspect_wheel(project: PluginProject, wheel: Path) -> list[str]:
    errors: list[str] = []
    with ZipFile(wheel) as archive:
        members = archive.namelist()
        if any(member.startswith("jrtc/") for member in members):
            errors.append(f"{project.path.name}: wheel illegally contains jrtc core files")
        if f"{project.import_name}/py.typed" not in members:
            errors.append(f"{project.path.name}: wheel does not contain py.typed")

        metadata_name = next(
            (member for member in members if member.endswith(".dist-info/METADATA")), None
        )
        entry_points_name = next(
            (member for member in members if member.endswith(".dist-info/entry_points.txt")),
            None,
        )
        if metadata_name is None:
            errors.append(f"{project.path.name}: wheel has no METADATA")
        else:
            metadata = email.parser.Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
            wheel_requirements = metadata.get_all("Requires-Dist", [])
            core_requirements = [
                normalized_requirement(item)
                for item in wheel_requirements
                if requirement_name(item) == "jrtc"
            ]
            if core_requirements not in (
                ["jrtc>=3.1,<4"],
                ["jrtc<4,>=3.1"],
            ):
                errors.append(
                    f"{project.path.name}: wheel metadata must retain jrtc>=3.1,<4; "
                    f"found {core_requirements or 'none'}"
                )
        if entry_points_name is None:
            errors.append(f"{project.path.name}: wheel has no entry_points.txt")
        else:
            entry_points_text = archive.read(entry_points_name).decode("utf-8")
            expected = f"{project.identifier} = {project.entry_point_target}"
            if "[jrtc.plugins]" not in entry_points_text or expected not in entry_points_text:
                errors.append(
                    f"{project.path.name}: wheel entry point does not contain {expected!r}"
                )
    return errors


def build_project(project: PluginProject, temporary_root: Path) -> list[str]:
    errors: list[str] = []
    staged_project = temporary_root / "sources" / project.path.name
    output = temporary_root / "artifacts" / project.path.name
    output.mkdir(parents=True)
    shutil.copytree(
        project.path,
        staged_project,
        ignore=shutil.ignore_patterns(
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "__pycache__",
            "*.egg-info",
            "*.pyc",
            "build",
            "dist",
        ),
    )
    environment = command_environment(project)
    error = run_command(
        f"{project.path.name}: wheel/sdist build",
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            "--wheel",
            "--outdir",
            str(output),
            str(staged_project),
        ],
        cwd=ROOT,
        environment=environment,
        timeout=300,
    )
    if error:
        return [error]
    wheels = sorted(output.glob("*.whl"))
    sdists = sorted(output.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        return [
            f"{project.path.name}: expected one wheel and one sdist; "
            f"found {len(wheels)} wheel(s), {len(sdists)} sdist(s)"
        ]
    errors.extend(inspect_wheel(project, wheels[0]))
    twine_error = run_command(
        f"{project.path.name}: twine check",
        [sys.executable, "-m", "twine", "check", str(wheels[0]), str(sdists[0])],
        cwd=ROOT,
        environment=environment,
        timeout=120,
    )
    if twine_error:
        errors.append(twine_error)
    return errors


def check_workspace_artifacts() -> list[str]:
    errors: list[str] = []
    for name in ("build", "dist"):
        path = ROOT / name
        if path.exists():
            errors.append(f"top-level generated artifact directory is forbidden: {path.name}")
    for pattern in ("*.whl", "*.tar.gz"):
        for path in ROOT.glob(pattern):
            errors.append(f"top-level generated artifact is forbidden: {path.name}")
    return errors


def main() -> int:
    arguments = parse_args()
    full = arguments.mode == "full"
    projects, errors = discover_projects()
    initial_names = {project.path.name for project in projects}
    identifiers = frozenset(project.identifier for project in projects)

    missing = REQUIRED_IDENTIFIERS - identifiers
    if missing:
        errors.append(f"missing required named-plugin projects: {sorted(missing)}")
    if len(identifiers) != len(projects):
        errors.append("plugin identifiers must be unique")
    import_names = {project.import_name for project in projects}
    if len(import_names) != len(projects):
        errors.append("plugin import namespaces must be unique")
    errors.extend(check_workspace_artifacts())

    warnings: list[str] = []
    for project in projects:
        project_errors, project_warnings = validate_project(project, identifiers, full=full)
        errors.extend(project_errors)
        warnings.extend(project_warnings)

    if errors:
        print("Plugin verification failed before command execution:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    command_errors: list[str] = []
    for project in projects:
        if error := smoke_test(project):
            command_errors.append(error)
        if error := run_tests(project):
            command_errors.append(error)

    if full and not command_errors:
        with tempfile.TemporaryDirectory(prefix="janus-plugin-verification-") as directory:
            temporary_root = Path(directory)
            for project in projects:
                command_errors.extend(build_project(project, temporary_root))

    final_projects, final_discovery_errors = discover_projects()
    command_errors.extend(final_discovery_errors)
    final_names = {project.path.name for project in final_projects}
    if final_names != initial_names:
        command_errors.append(
            "plugin project set changed during verification; rerun so every new project is checked"
        )
    for project in projects:
        artifacts = generated_artifacts(project)
        if artifacts:
            rendered = ", ".join(str(path.relative_to(ROOT)) for path in artifacts)
            command_errors.append(
                f"{project.path.name}: commands left generated artifacts behind: {rendered}"
            )

    if command_errors:
        print("\nPlugin verification failed:", file=sys.stderr)
        for error in command_errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"\nVerified {len(projects)} plugin project(s) in {arguments.mode} mode: "
        + ", ".join(project.path.name for project in projects)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
