# stream-orchestrator-process

Safe, shell-free process execution for process-backed source drivers.

The package separates two responsibilities:

- a `CommandBuilder` turns a validated stream definition into a `ProcessSpec`;
- a `ProcessExecutor` owns process startup, bounded output capture, health, and shutdown.

`LocalProcessExecutor` is appropriate for development, desktop applications,
and deliberately single-node deployments. Server installations should replace
it with a Docker, Kubernetes, or remote-agent executor implementing the same
protocol.
