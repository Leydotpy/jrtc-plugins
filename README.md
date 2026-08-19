# Janus named-plugin workspace

Each `jrtc-*/` directory is an independently installable distribution that
depends on `jrtc>=3.1,<4`. Core exposes the `jrtc` import
namespace but contains no named plugin implementation or protocol models.

The outer workspace covers EchoTest, VideoCall, SIP, NoSIP, AudioBridge,
VideoRoom, TextRoom, and Record&Play under their canonical distribution names:
`jrtc-echo`, `jrtc-call`, `jrtc-sip`, `jrtc-nosip`, `jrtc-audio`, `jrtc-video`,
`jrtc-text`, and `jrtc-rec`. The verifier uses this explicit mapping so package
renames cannot silently change plugin identifiers or import namespaces.

Streaming is not present in Janus Core. Its standalone `jrtc-stream`
distribution is maintained in the nested
`jrtc-stream/projects/jrtc-stream` project and uses the same
`jrtc.plugins` entry-point contract. The nested directory is a separate uv
workspace with its own `AGENTS.md`, lockfile, boundary checks, tests, and
artifact verifier, so it is explicitly excluded from this outer workspace.

## Development

```bash
uv sync --group dev
uv run python scripts/verify_plugins.py --mode fast
uv run python scripts/verify_plugins.py --mode full
```

Verify the Streaming workspace separately from `jrtc-stream/`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_boundaries.py
uv run python scripts/run_tests.py
uv run python scripts/build_all.py
uv run python scripts/verify_artifacts.py
```

`fast` validates metadata, entry points, dependency and import boundaries,
source syntax, runtime entry-point targets, and runs every available test
suite. It warns when an in-progress project has no tests. `full` additionally
requires tests for every project, builds each wheel and sdist in a temporary
copy, inspects wheel ownership/metadata, and runs `twine check`.

Both modes reject generated artifacts inside plugin projects and imports from
named core model/plugin modules. Build outputs are temporary; commit `uv.lock`,
but do not commit virtual environments, caches, wheels, sdists, or egg-info.
Use the root-only sync shown above: editable `--all-packages` installs with
setuptools create ignored `*.egg-info` directories in each source tree, which
the clean-tree verifier intentionally rejects.
