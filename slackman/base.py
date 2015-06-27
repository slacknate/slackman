import json
import asyncio
import logging
import argparse

from concurrent.futures import ThreadPoolExecutor

import aiohttp
import websockets

logger = logging.getLogger("Slack Client")

ADMIN_COMMANDS = [

    "$auth",
    "$power",
]

USER_COMMANDS = [

    "$gameinfo",
]

COMMAND_HANDLERS = {}


class SlackClientProtocol(websockets.client.WebSocketClientProtocol):
    @asyncio.coroutine
    def send(self, data):
        result = yield from super().send(json.dumps(data))
        return result

    @asyncio.coroutine
    def recv(self):
        result = yield from super().recv()
        return json.loads(result)


def register_handler(command, handler):
    if not asyncio.iscoroutinefunction(handler):
        raise ValueError("Command handlers must be coroutines.")

    COMMAND_HANDLERS[command] = handler


def unregister_handler(command):
    del COMMAND_HANDLERS[command]


@asyncio.coroutine
def handle_events(admin_uid_table, queue, token):
    try:
        connection = yield from start_slack_rtm_session(token)

        while True:
            event = yield from queue.get()
            event_type = event.get("type")

            logger.debug("Event: %s", event)

            if event_type == "shutdown":
                break

            elif event_type == "message":
                text_groups = [group for group in event["text"].split(" ") if group != ""]

                command = text_groups[0]
                args = text_groups[1:]

                uid = event["user"]

                if command in ADMIN_COMMANDS:
                    if uid in admin_uid_table:
                        handler = COMMAND_HANDLERS.get(command)
                        if handler is not None:
                            yield from handler(connection, event, *args)

                        else:
                            logger.debug("No handler registered for command %s", command)

                    else:
                        yield from connection.send({

                            "id": 1,
                            "type": "message",
                            "channel": event["channel"],
                            "text": "You are not authorized to use this command."
                        })

                elif command in USER_COMMANDS:
                    handler = COMMAND_HANDLERS.get(command)
                    if handler is not None:
                        yield from handler(connection, event, *args)

                    else:
                        logger.debug("No handler registered for command %s", command)

                elif command.startswith("$"):
                    logger.debug("Unknown command %s", command)

                    yield from connection.send({

                        "id": 1,
                        "type": "message",
                        "channel": event["channel"],
                        "text": "Unknown command {}".format(command)
                    })

    except Exception:
        logger.exception("Error occurred")


def event_thread(admin_uid_table, queue, token):
    try:

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(handle_events(admin_uid_table, queue, token))

    except Exception:
        logger.exception("Error occurred")


@asyncio.coroutine
def get_admin_user_ids(emails, token):
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
def main_loop(loop, queue, args):
    executor = ThreadPoolExecutor(max_workers=1)

    admin_uid_table = yield from get_admin_user_ids(args.admins, args.token)
    connection = yield from start_slack_rtm_session(args.token)

    try:
        loop.run_in_executor(executor, event_thread, admin_uid_table, queue, args.token)

        while True:
            event = yield from connection.recv()
            loop.call_soon_threadsafe(lambda: asyncio.async(queue.put(event)))

    finally:
        yield from connection.close()

        loop.call_soon_threadsafe(lambda: asyncio.async(queue.put({"type": "shutdown"})))
        executor.shutdown(wait=True)
