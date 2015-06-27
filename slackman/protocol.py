import json
import asyncio
import websockets


class SlackClientProtocol(websockets.client.WebSocketClientProtocol):
    """
    Websocket Protocol subclass that auto-converts
    between dict and string JSON representations.
    """
    @asyncio.coroutine
    def send(self, data):
        result = yield from super().send(json.dumps(data))
        return result

    @asyncio.coroutine
    def recv(self):
        result = yield from super().recv()
        return json.loads(result)