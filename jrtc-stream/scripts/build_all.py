from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
DIST = ROOT / "dist"


def main() -> int:
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)
    projects = sorted(path for path in PROJECTS.iterdir() if (path / "pyproject.toml").is_file())
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required to build this workspace")
    subprocess.run(
        [
            uv,
            "build",
            "--all-packages",
            "--no-sources",
            "--out-dir",
            str(DIST),
        ],
        check=True,
        cwd=ROOT,
    )
    print(f"Built {len(projects)} projects into {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
