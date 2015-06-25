import json
import aiohttp
import asyncio
import argparse
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

    hello_message = yield from connection.recv()
    if hello_message.get("type") != "hello":
        raise ValueError("Did not receive hello message from Slack.")

    return connection


@asyncio.coroutine
def main_loop(token):
    connection = yield from start_slack_rtm_session(token)



    yield from connection.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", dest="token", required=True,
                        help="Authentication token of the slack bot integration that will be connecting.")

    args, _ = parser.parse_known_args()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_loop(args.token))


if __name__ == "__main__":
    main()
