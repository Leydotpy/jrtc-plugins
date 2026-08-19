# stream-orchestrator-qt

A small optional adapter that runs the async orchestration API on a dedicated
`asyncio` loop thread and exposes completion/status callbacks suitable for Qt
applications. The base installation has no Qt dependency. Install the
`pyside6` or `pyqt6` extra only in the GUI application.

The application remains responsible for marshalling callbacks to the GUI
thread. The included optional QObject factories do that through queued Qt
signals.
