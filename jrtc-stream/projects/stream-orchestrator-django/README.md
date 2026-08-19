# stream-orchestrator-django

Optional Django adapter for `stream-orchestrator`. It supplies a durable
repository, event/outbox tables, and small service-access helpers. It does not
know about Janus, SRS, FFmpeg, GStreamer, Channels, or a particular API layer.

Add `stream_orchestrator_django` to `INSTALLED_APPS`, run migrations, then
compose an `OrchestratorService` in your Django project using whichever
mountpoint backend and source drivers your deployment requires.
