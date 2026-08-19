# stream-orchestrator-ffmpeg

A profile-driven FFmpeg command builder and source driver. The public API never
accepts arbitrary shell text. Applications register trusted profiles, and the
builder produces an argument vector for a `ProcessExecutor`.

```python
from stream_orchestrator_ffmpeg import default_profiles, make_ffmpeg_driver
from stream_orchestrator_process import LocalProcessExecutor

driver = make_ffmpeg_driver(
    executor=LocalProcessExecutor(allowed_executables={"ffmpeg"}),
    profiles=default_profiles(),
)
```

For servers, substitute a container or remote-agent executor. The orchestration
core remains unchanged.
