import asyncio

import aiohttp
import websockets

from .protocol import SlackClientProtocol


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
def get_user_ids(emails, token):
    response = yield from aiohttp.request("post", "https://slack.com/api/users.list", data={"token": token})
    resp_data = yield from response.json()

    if not resp_data["ok"]:
        raise ValueError("Unable to retrieve Slack user list.")

    members = resp_data["members"]

    admin_uid_table = {}
    for user_data in members:
        user_email = user_data["profile"].get("email")

        if user_email in emails:
            admin_uid_table[user_data["id"]] = user_email

    return admin_uid_table