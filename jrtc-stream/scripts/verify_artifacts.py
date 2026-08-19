from __future__ import annotations

import re
import subprocess
import sys
import tarfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
EXPECTED_DISTRIBUTIONS = {
    "jrtc-stream": "0.2.0",
    "janus-stream-orchestrator": "0.1.0",
    "stream-orchestrator": "0.1.0",
    "stream-orchestrator-django": "0.1.0",
    "stream-orchestrator-ffmpeg": "0.1.0",
    "stream-orchestrator-gstreamer": "0.1.0",
    "stream-orchestrator-process": "0.1.0",
    "stream-orchestrator-qt": "0.1.0",
    "stream-orchestrator-srs": "0.1.0",
}
FORBIDDEN_MEMBER_PARTS = frozenset(
    {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv", "__pycache__"}
)
FORBIDDEN_CONTENT = (
    re.compile(rb"[A-Za-z]:\\\\Users\\\\", re.IGNORECASE),
    re.compile(rb"/Users/[^/]+/"),
    re.compile(rb"/home/[^/]+/"),
    re.compile(rb"pypi-[A-Za-z0-9_-]{16,}"),
)


def metadata_value(metadata: str, field: str) -> str:
    prefix = f"{field}: "
    for line in metadata.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise RuntimeError(f"wheel metadata is missing {field!r}")


def verify_member(archive: Path, name: str, data: bytes, *, wheel: bool) -> None:
    parts = set(Path(name).parts)
    if parts & FORBIDDEN_MEMBER_PARTS or name.endswith((".pyc", ".pyo")):
        raise RuntimeError(f"{archive.name} contains generated member {name!r}")
    if wheel and ("/tests/" in f"/{name}/" or Path(name).name.startswith("test_")):
        raise RuntimeError(f"{archive.name} contains test file {name!r}")
    if any(pattern.search(data) for pattern in FORBIDDEN_CONTENT):
        raise RuntimeError(f"{archive.name} contains a local path or token in {name!r}")


def verify_sdist(archive: Path) -> None:
    with tarfile.open(archive, "r:gz") as package:
        for member in package.getmembers():
            if not member.isfile():
                continue
            file_object = package.extractfile(member)
            verify_member(
                archive,
                member.name,
                b"" if file_object is None else file_object.read(),
                wheel=False,
            )


def main() -> int:
    wheels = sorted(DIST.glob("*.whl"))
    sdists = sorted(DIST.glob("*.tar.gz"))
    if len(wheels) != len(EXPECTED_DISTRIBUTIONS):
        raise RuntimeError(f"expected 9 wheels, found {len(wheels)}")
    if len(sdists) != len(EXPECTED_DISTRIBUTIONS):
        raise RuntimeError(f"expected 9 source distributions, found {len(sdists)}")

    versions: dict[str, str] = {}
    for wheel in wheels:
        with ZipFile(wheel) as archive:
            members = archive.namelist()
            for member in members:
                if member.endswith("/"):
                    continue
                verify_member(wheel, member, archive.read(member), wheel=True)
            metadata_member = next(
                (name for name in members if name.endswith(".dist-info/METADATA")),
                None,
            )
            if metadata_member is None:
                raise RuntimeError(f"{wheel.name} has no METADATA file")
            metadata = archive.read(metadata_member).decode("utf-8")
            name = metadata_value(metadata, "Name")
            versions[name] = metadata_value(metadata, "Version")
            if not any(name.endswith("/py.typed") for name in members):
                raise RuntimeError(f"{wheel.name} does not include py.typed")

            if name == "jrtc-stream":
                entry_points_member = next(
                    (item for item in members if item.endswith(".dist-info/entry_points.txt")),
                    None,
                )
                if entry_points_member is None:
                    raise RuntimeError(f"{wheel.name} has no entry_points.txt")
                expected_entry_point = (
                    "[jrtc.plugins]\nstreaming = janus_streaming._compat:StreamingPlugin"
                )
                entry_points = archive.read(entry_points_member).decode("utf-8").strip()
                if entry_points != expected_entry_point:
                    raise RuntimeError(
                        f"{wheel.name} has unexpected entry-point metadata: {entry_points!r}"
                    )

    if versions != EXPECTED_DISTRIBUTIONS:
        raise RuntimeError(f"built distributions differ from expected set: {versions}")

    for sdist in sdists:
        verify_sdist(sdist)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "twine",
            "check",
            "--strict",
            *map(str, wheels),
            *map(str, sdists),
        ],
        check=True,
    )
    print("Validated 9 wheels and 9 source distributions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
