import asyncio

from stream_orchestrator_qt import AsyncioLoopThread


def test_loop_thread_executes_and_stops() -> None:
    runner = AsyncioLoopThread()

    async def value() -> int:
        await asyncio.sleep(0)
        return 42

    assert runner.submit(value()).result(timeout=5) == 42
    runner.stop()
    assert not runner.running
