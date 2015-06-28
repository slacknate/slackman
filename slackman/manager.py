import asyncio
import logging

from concurrent.futures import ThreadPoolExecutor

from .util import *
from .router import RouterTable, RouterKey
from .auth import generate_auth_token, send_auth_email

logger = logging.getLogger("Slack Client")


class SlackServerManager(object):
    def __init__(self, args):
        self.args = args
        self.loop = asyncio.get_event_loop()

        self.admin_uid_table = None
        self.send_connection = None

        self.command_handlers = {}
        self.admin_commands = []
        self.user_commands = []

        self.router_table = RouterTable()

    def register_admin_commands(self, *commands):
        self.admin_commands += commands

    def unregister_admin_commands(self, *commands):
        for command in commands:
            self.admin_commands.remove(command)

    def register_user_commands(self, *commands):
        self.user_commands += commands

    def unregister_user_commands(self, *commands):
        for command in commands:
            self.user_commands.remove(command)

    def register_handler(self, command, handler):
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError("Command handlers must be coroutines.")

        self.command_handlers[command] = handler

    def unregister_handler(self, command):
        del self.command_handlers[command]

    @asyncio.coroutine
    def auth_handler(self, event):
        yield from self.send({

            "id": 1,
            "type": "message",
            "channel": event["channel"],
            "text": "Sending authorization token to your email address. Please send the token as your next message."
        })

        email = yield from get_user_email(event["user"], self.args.token)

        auth_token = generate_auth_token()
        send_auth_email(auth_token, email, *self.args.email_info)

        key = RouterKey({"user": event["user"]})
        future = asyncio.Future()

        self.router_table.add_future(key, future)

        response_event = yield from future

        if response_event["text"] == auth_token:
            yield from self.send({

                "id": 1,
                "type": "message",
                "channel": event["channel"],
                "text": "Authorization succeeded."
            })

        else:
            yield from self.send({

                "id": 1,
                "type": "message",
                "channel": event["channel"],
                "text": "Authorization failed."
            })

    @asyncio.coroutine
    def handle_event(self, event):
        text_groups = [group for group in event["text"].split(" ") if group != ""]

        command = text_groups[0]
        args = text_groups[1:]

        uid = event["user"]

        if command == "$auth":
            if uid in self.admin_uid_table:
                yield from self.auth_handler(event)

            else:
                yield from self.send({

                    "id": 1,
                    "type": "message",
                    "channel": event["channel"],
                    "text": "You are not authorized to use this command."
                })

        elif command in self.admin_commands:
            if uid in self.admin_uid_table:
                handler = self.command_handlers.get(command)
                if handler is not None:
                    yield from handler(self, event, self.args.token, *args)

                else:
                    logger.debug("No handler registered for command %s", command)

            else:
                yield from self.send({

                    "id": 1,
                    "type": "message",
                    "channel": event["channel"],
                    "text": "You are not authorized to use this command."
                })

        elif command in self.user_commands:
            handler = self.command_handlers.get(command)
            if handler is not None:
                yield from handler(self, event, self.args.token, *args)

            else:
                logger.debug("No handler registered for command %s", command)

        elif command.startswith("$"):
            logger.debug("Unknown command %s", command)

            yield from self.send({

                "id": 1,
                "type": "message",
                "channel": event["channel"],
                "text": "Unknown command {}".format(command)
            })

    @asyncio.coroutine
    def send(self, event):
        yield from self.send_connection.send(event)

    @asyncio.coroutine
    def receive_events(self, queue):
        while True:
            try:
                event = yield from queue.get()
                logger.debug("Received event: %s", event)

                key = RouterKey(event)
                future_lists = self.router_table.get_futures(key)

                for future_list in future_lists:
                    for future in future_list:
                        future.set_result(event)

                asyncio.async(self.handle_event(event))

            except Exception:
                logger.exception("Error occurred")

    def event_thread(self, queue):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(self.receive_events(queue))

        except Exception:
            logger.exception("Error occurred")

    @asyncio.coroutine
    def run(self):
        try:
            queue = asyncio.Queue()

            executor = ThreadPoolExecutor(max_workers=1)
            self.loop.run_in_executor(executor, self.event_thread, queue)

            self.admin_uid_table = yield from get_user_ids(self.args.admins, self.args.token)
            self.send_connection = yield from start_slack_rtm_session(self.args.token)

            connection = yield from start_slack_rtm_session(self.args.token)
            while True:
                event = yield from connection.recv()
                if event["type"] == "message":
                    self.loop.call_soon_threadsafe(lambda: asyncio.async(queue.put(event)))

        except Exception:
            logger.exception("Error occurred")

        finally:
            yield from self.send_connection.close()