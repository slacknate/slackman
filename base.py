import aiohttp
import asyncio
import argparse

from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory


class MyClientProtocol(WebSocketClientProtocol):

    def onConnect(self, response):
        print("Server connected: {0}".format(response.peer))

    def onOpen(self):
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
        if isBinary:
            print("Binary message received: {0} bytes".format(len(payload)))
        else:
            print("Text message received: {0}".format(payload.decode('utf8')))

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))


@asyncio.coroutine
def start_slack_rtm_session(token):
    response = yield from aiohttp.request("post", "https://slack.com/api/rtm.start", data={"token": token})
    resp_data = yield from response.json()

    if not resp_data["ok"]:
        raise ValueError("Unable to retrieve Websocket URL for Slack RTM session.")

    return resp_data["url"]


@asyncio.coroutine
def main_loop(loop, token):
    ws_url = yield from start_slack_rtm_session(token)

    factory = WebSocketClientFactory(ws_url)
    factory.protocol = MyClientProtocol

    conn = yield from loop.create_connection(factory, ws_url)
    print(conn)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", dest="token", required=True,
                        help="Authentication token of the slack bot integration that will be connecting.")

    args, _ = parser.parse_known_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_loop(loop, args.token))


if __name__ == "__main__":
    main()
