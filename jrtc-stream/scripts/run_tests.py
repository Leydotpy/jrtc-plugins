from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
ALL_PROJECTS = (
    "stream-orchestrator",
    "stream-orchestrator-process",
    "stream-orchestrator-ffmpeg",
    "stream-orchestrator-gstreamer",
    "stream-orchestrator-srs",
    "jrtc-stream",
    "janus-stream-orchestrator",
    "stream-orchestrator-django",
    "stream-orchestrator-qt",
)
JANUS_PROJECTS = frozenset({"jrtc-stream", "janus-stream-orchestrator"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--portable",
        action="store_true",
        help="skip packages requiring Python 3.14 and jrtc",
    )
    args = parser.parse_args()

    selected = [
        project for project in ALL_PROJECTS if not args.portable or project not in JANUS_PROJECTS
    ]
    source_paths = [str(PROJECTS / project / "src") for project in ALL_PROJECTS]
    existing_pythonpath = os.environ.get("PYTHONPATH")
    if existing_pythonpath:
        source_paths.append(existing_pythonpath)
    environment = os.environ | {
        "PYTHONPATH": os.pathsep.join(source_paths),
        # Third-party global pytest plugins can make workspace verification
        # non-reproducible or keep subprocesses alive after a suite finishes.
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
    }

    for project in selected:
        print(f"Testing {project}", flush=True)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "pytest_asyncio.plugin",
                "-q",
                str(PROJECTS / project / "tests"),
            ],
            check=True,
            cwd=ROOT,
            env=environment,
        )
    print(f"Passed test suites for {len(selected)} projects.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
