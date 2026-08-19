from __future__ import annotations

import argparse
import email.parser
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate hashes and an SPDX SBOM.")
    parser.add_argument("--dist", type=Path, default=DIST, help="directory containing archives")
    parser.add_argument(
        "--name",
        default="jrtc-stream-workspace-release",
        help="SPDX document name",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wheel_metadata(wheel: Path) -> email.message.Message:
    with ZipFile(wheel) as archive:
        member = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        return email.parser.Parser().parsestr(archive.read(member).decode("utf-8"))


def spdx_id(name: str) -> str:
    return "SPDXRef-Package-" + "".join(
        character if character.isalnum() else "-" for character in name
    )


def main() -> int:
    arguments = parse_args()
    dist = arguments.dist.resolve()
    archives = sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")], key=lambda path: path.name)
    if not archives:
        raise RuntimeError("no release archives found; run scripts/build_all.py first")

    hashes = {archive.name: sha256(archive) for archive in archives}
    (dist / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items()),
        encoding="utf-8",
        newline="\n",
    )

    packages: list[dict[str, object]] = []
    relationships: list[dict[str, str]] = []
    for wheel in sorted(dist.glob("*.whl"), key=lambda path: path.name):
        metadata = wheel_metadata(wheel)
        name = str(metadata["Name"])
        version = str(metadata["Version"])
        identifier = spdx_id(name)
        requires = metadata.get_all("Requires-Dist", [])
        license_declared = (
            metadata.get("License-Expression") or metadata.get("License") or "NOASSERTION"
        )
        packages.append(
            {
                "SPDXID": identifier,
                "name": name,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": license_declared,
                "copyrightText": "NOASSERTION",
                "checksums": [{"algorithm": "SHA256", "checksumValue": hashes[wheel.name]}],
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{name}@{version}",
                    }
                ],
                "comment": json.dumps(
                    {
                        "wheel": wheel.name,
                        "requires_dist": requires,
                    },
                    sort_keys=True,
                ),
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": identifier,
            }
        )

    release_digest = hashlib.sha256(
        "".join(f"{name}:{digest}\n" for name, digest in hashes.items()).encode()
    ).hexdigest()
    created = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": arguments.name,
        "documentNamespace": (
            "https://spdx.org/spdxdocs/jrtc-stream-workspace-" + release_digest[:24]
        ),
        "creationInfo": {
            "created": created,
            "creators": ["Tool: scripts/generate_release_metadata.py"],
        },
        "packages": packages,
        "relationships": relationships,
    }
    (dist / "SBOM.spdx.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Generated SHA256SUMS.txt and SBOM.spdx.json for {len(archives)} archives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
