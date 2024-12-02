import os
import uuid
import json
import logging
import asyncio
from aiohttp import web
import websockets

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define upload directory
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Dictionary to keep track of file transfers
file_transfers = {}

async def handle_websocket_connection(websocket, path):
    """Handles the WebSocket communication."""
    try:
        logger.info(f"WebSocket connection established. Path: {path}")

        # Reject any connections not using the correct path
        if path != '/ws':
            logger.warning(f"Rejected connection for path: {path}")
            return

        async for message in websocket:
            await process_message(message, websocket)

    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
    finally:
        # Close all open file transfers on connection closure
        await cleanup_file_transfers()

async def process_message(message, websocket):
    """Process received WebSocket messages."""
    try:
        if isinstance(message, bytes):
            await handle_file_chunk(message, websocket)
        elif isinstance(message, str):
            data = json.loads(message)
            await handle_json_message(data, websocket)
    except json.JSONDecodeError:
        logger.error("Invalid JSON format received")
        await websocket.send(json.dumps({
            'type': 'error',
            'message': 'Invalid JSON format'
        }))
    except Exception as e:
        logger.error(f"Message processing error: {e}")
        await websocket.send(json.dumps({
            'type': 'error',
            'message': str(e)
        }))

async def handle_file_chunk(message, websocket):
    """Handles the incoming file chunks during transfer."""
    file_id = getattr(websocket, 'current_file_id', None)

    if not file_id or file_id not in file_transfers:
        await websocket.send(json.dumps({
            'type': 'error',
            'message': 'Invalid file transfer'
        }))
        return

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
        logger.error(f"Error writing file chunk: {e}")
        await websocket.send(json.dumps({
            'type': 'error',
            'message': str(e)
        }))

async def handle_json_message(data, websocket):
    """Handles the JSON messages (start, end, list_files)."""
    message_type = data.get('type')

    if message_type == 'start':
        await start_file_transfer(data, websocket)
    elif message_type == 'end':
        await end_file_transfer(data, websocket)
    elif message_type == 'list_files':
        await list_files(websocket)

async def start_file_transfer(data, websocket):
    """Initiates a file transfer."""
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

async def end_file_transfer(data, websocket):
    """Ends the file transfer and closes the file."""
    file_id = data.get('file_id')

    if file_id in file_transfers:
        file_transfers[file_id]['file'].close()
        del file_transfers[file_id]

    await websocket.send(json.dumps({
        'type': 'upload_complete',
        'message': 'File uploaded successfully'
    }))

async def list_files(websocket):
    """Lists the uploaded files in the server."""
    files = os.listdir(UPLOAD_DIR)
    await websocket.send(json.dumps({
        'type': 'file_list',
        'files': files
    }))

async def cleanup_file_transfers():
    """Cleans up any open file transfers."""
    for transfer in list(file_transfers.values()):
        transfer['file'].close()
    file_transfers.clear()

async def serve_index(request):
    """Serve the index.html file."""
    return web.FileResponse('./index.html')

def create_app():
    """Creates and configures the aiohttp web application."""
    app = web.Application()
    app.router.add_get('/', serve_index)
    return app

async def main():
    """Main entry point to run the HTTP and WebSocket servers."""
    # Set up the HTTP server
    web_app = create_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    http_site = web.TCPSite(runner, '0.0.0.0', 8080)
    await http_site.start()

    # Set up the WebSocket server
    websocket_server = await websockets.serve(handle_websocket_connection, "0.0.0.0", 4873)

    logger.info("Servers started:")
    logger.info("HTTP server running at: https://0.0.0.0:8080")
    logger.info("WebSocket server running at: ws://0.0.0.0:4873")

    # Keep the application running
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
