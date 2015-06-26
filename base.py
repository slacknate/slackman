import json
import asyncio
import argparse

from concurrent.futures import ThreadPoolExecutor

import aiohttp
import websockets


class SlackClientProtocol(websockets.client.WebSocketClientProtocol):
    @asyncio.coroutine
    def recv(self):
        result = yield from super().recv()
        return json.loads(result)


@asyncio.coroutine
def start_slack_rtm_session(token):
    response = yield from aiohttp.request("post", "https://slack.com/api/rtm.start", data={"token": token})
    resp_data = yield from response.json()

    if not resp_data["ok"]:
        raise ValueError("Unable to retrieve Websocket URL for Slack RTM session.")

    connection = yield from websockets.connect(resp_data["url"], klass=SlackClientProtocol)

    hello_event = yield from connection.recv()
    if hello_event.get("type") != "hello":
        yield from connection.close()

        raise ValueError("Did not receive hello message from Slack.")

    return connection


@asyncio.coroutine
def handle_events(queue):
    while True:
        event = yield from queue.get()
        event_type = event.get("type")

        if event_type == "shutdown":
            break

        print(event)

        # TODO: implement me!


def event_thread(queue):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(handle_events(queue))


@asyncio.coroutine
def main_loop(loop, queue, token):
    executor = ThreadPoolExecutor(max_workers=1)

    connection = yield from start_slack_rtm_session(token)

    try:
        loop.run_in_executor(executor, event_thread, queue)

        while True:
            event = yield from connection.recv()
            loop.call_soon_threadsafe(lambda: asyncio.async(queue.put(event)))

    finally:
        yield from connection.close()

        loop.call_soon_threadsafe(lambda: asyncio.async(queue.put({"type": "shutdown"})))
        executor.shutdown(wait=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", dest="token", required=True,
                        help="Authentication token of the slack bot integration that will be connecting.")

    args, _ = parser.parse_known_args()

    loop = asyncio.get_event_loop()

    queue = asyncio.Queue()

    loop.run_until_complete(main_loop(loop, queue, args.token))


if __name__ == "__main__":
    main()
