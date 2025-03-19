import asyncio
import json
from typing import Dict, Any, Set
import aiohttp
from aiohttp import web

_websockets = set()

async def broadcast(data):
    """
    Broadcast data to all connected WebSocket clients.
    
    Args:
        data: The data to broadcast
    """
    if not _websockets:
        print("No WebSocket connections available")
        return
        
    try:
        # Convert data to JSON string
        if isinstance(data, dict) or isinstance(data, list):
            data_str = json.dumps(data)
            # 添加调试信息 - 打印数据的关键部分
            if isinstance(data, dict):
                print(f"Broadcasting data with keys: {list(data.keys())}")
                if 'recent_trades' in data:
                    print(f"Recent trades count: {len(data['recent_trades'])}")
        else:
            data_str = str(data)
        
        closed_ws = set()
        for ws in _websockets:
            try:
                await ws.send_str(data_str)
                print(f"Data sent to WebSocket client")
            except Exception as e:
                print(f"Error sending data to websocket: {e}")
                closed_ws.add(ws)
        
        _websockets.difference_update(closed_ws)
        
    except Exception as e:
        print(f"Error in broadcast: {e}")
        import traceback
        print(traceback.format_exc())

def register_websocket(ws):
    _websockets.add(ws)
    print(f"WebSocket registered. Total connections: {len(_websockets)}")

def unregister_websocket(ws):
    if ws in _websockets:
        _websockets.remove(ws)
    print(f"WebSocket unregistered. Total connections: {len(_websockets)}")

async def handle_websocket(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    print("New WebSocket connection established")
    register_websocket(ws)
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    print(f"Received WebSocket message: {data}")
                    
                    if "action" in data:
                        if data["action"] == "fetch_balances":
                            print("Received fetch_balances request")
                            await ws.send_str(json.dumps({"log": "Received fetch_balances request, processing..."}))
                        elif data["action"] == "close":
                            await ws.close()
                except json.JSONDecodeError:
                    print(f"Invalid JSON received: {msg.data}")
            elif msg.type == web.WSMsgType.ERROR:
                print(f"WebSocket connection closed with exception {ws.exception()}")
    finally:
        unregister_websocket(ws)
        print("WebSocket connection closed")
    
    return ws