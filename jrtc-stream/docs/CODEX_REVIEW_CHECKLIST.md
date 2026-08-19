# Codex review checklist

Use `AGENTS.md` as the controlling instruction file. Record evidence for every
item rather than marking it from inspection alone.

- [ ] Package graph matches the declared architecture.
- [ ] Core imports only the standard library.
- [ ] Only `_compat.py` imports `jrtc`.
- [ ] Django and Qt packages do not import Janus packages.
- [ ] Source adapters do not import Django or Qt.
- [ ] Commands never use a shell or untrusted raw argument/pipeline strings.
- [ ] Restart/backoff/terminal states are deterministic and tested.
- [ ] Mountpoint loss causes source retargeting, not stale process reuse.
- [ ] Missing Janus mountpoint handling is limited to the correct error code.
- [ ] Secrets are resolved outside serialized metadata.
- [ ] SRS callbacks are reconciled against the API.
- [ ] Django repository CAS behavior and migrations are tested.
- [ ] Qt callbacks enter the GUI thread through signals in optional adapters.
- [ ] Real integration suites cover Janus, SRS, encoders, RTSP, and browsers.
- [ ] Failure injection and graceful shutdown pass.
- [ ] Wheels/sdists install in clean environments.
- [ ] Version ranges and compatibility matrices are justified.
- [ ] Security review and release gates are complete.
