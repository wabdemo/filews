import asyncio
import os
import uuid
import json
import websockets
from aiohttp import web
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

file_transfers = {}

async def websocket_handler(websocket, path):
    try:
        logger.info(f"WebSocket connection received. Path: {path}")

        if path != '/ws':
            logger.warning(f"Rejected connection for path: {path}")
            return

        async for message in websocket:
            try:
                if isinstance(message, bytes):
                    file_id = getattr(websocket, 'current_file_id', None)

                    if not file_id or file_id not in file_transfers:
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': 'Invalid file transfer'
                        }))
                        continue

                    try:
                        file_transfers[file_id]['file'].write(message)

                        current_size = file_transfers[file_id]['file'].tell()
                        total_size = file_transfers[file_id]['total_size']
                        progress = int((current_size / total_size) * 100)

                        await websocket.send(json.dumps({
                            'type': 'progress',
                            'file_id': file_id,
                            'progress': progress
                        }))
                    except Exception as e:
                        logger.error(f"File transfer error: {e}")
                        await websocket.send(json.dumps({
                            'type': 'error',
                            'message': str(e)
                        }))

                elif isinstance(message, str):
                    data = json.loads(message)
                    logger.info(f"Received message type: {data.get('type')}")

                    if data.get('type') == 'start':
                        file_id = str(uuid.uuid4())
                        filename = data.get('filename', 'unnamed_file')
                        total_size = data.get('total_size', 0)
                        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{filename}")

                        file_transfers[file_id] = {
                            'file': open(file_path, 'wb'),
                            'filename': filename,
                            'total_size': total_size
                        }

                        websocket.current_file_id = file_id

                        await websocket.send(json.dumps({
                            'type': 'start_ack',
                            'file_id': file_id
                        }))

                    elif data.get('type') == 'end':
                        file_id = data.get('file_id')

                        if file_id in file_transfers:
                            file_transfers[file_id]['file'].close()
                            del file_transfers[file_id]

                        await websocket.send(json.dumps({
                            'type': 'upload_complete',
                            'message': 'File uploaded successfully'
                        }))

                    elif data.get('type') == 'list_files':
                        files = [f for f in os.listdir(UPLOAD_DIR)]
                        await websocket.send(json.dumps({
                            'type': 'file_list',
                            'files': files
                        }))

            except json.JSONDecodeError:
                logger.error("Invalid JSON message")
                await websocket.send(json.dumps({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }))
            except Exception as e:
                logger.error(f"Message processing error: {e}")

    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")
    finally:
        for transfer in list(file_transfers.values()):
            transfer['file'].close()
        file_transfers.clear()

async def serve_index(request):
    return web.FileResponse('./index.html')

def create_app():
    app = web.Application()
    app.router.add_get('/', serve_index)
    return app

async def main():
    web_app = create_app()

    runner = web.AppRunner(web_app)
    await runner.setup()

    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

    websocket_server = await websockets.serve(
        websocket_handler,
        "0.0.0.0",
        8081
    )

    print("Server started on port 8080")
    print("HTTP server running at: http://0.0.0.0:8080")

    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
