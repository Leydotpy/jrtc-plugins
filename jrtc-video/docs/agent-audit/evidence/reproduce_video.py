"""Execute the source aclose method with controlled lifecycle locks."""
import ast
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

source = Path(__file__).resolve().parents[3] / 'src/jrtc_video/service.py'
tree = ast.parse(source.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VideoRoomService')
method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'aclose')
env = {'asyncio': asyncio}
exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(source), 'exec'), env)

async def main():
 service = SimpleNamespace(_close_lock=asyncio.Lock(), _management_lock=asyncio.Lock(), _closed=False, _closing=False, _management_plugin=object())
 await service._management_lock.acquire()
 task = asyncio.create_task(env['aclose'](service))
 await asyncio.sleep(0)
 assert service._closing and not task.done()
 task.cancel()
 try:
  await task
 except asyncio.CancelledError:
  pass
 service._management_lock.release()
 await env['aclose'](service)
 print(json.dumps({'case': 'cancel-close-while-management-busy', 'closed': service._closed, 'cached_management_plugin_remains': service._management_plugin is not None, 'second_close_performs_cleanup': False}))

asyncio.run(main())
