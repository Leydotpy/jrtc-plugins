# stream-orchestrator-gstreamer

A structured `gst-launch-1.0` command builder and process-backed source driver.
Only trusted profiles can select elements and properties. User input is never
executed through a shell.

This reference implementation is intentionally process-isolated. A future
`Gst`/GObject executor can implement the same orchestration driver contract
when applications need direct `GstBus` events.
