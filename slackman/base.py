import asyncio
import logging

from concurrent.futures import ThreadPoolExecutor

from .util import *
from .auth import send_auth_email

logger = logging.getLogger("Slack Client")


class SlackServerManager(object):
    def __init__(self, args):
        self.args = args
        self.loop = asyncio.get_event_loop()

        self.command_handlers = {}
        self.admin_commands = []
        self.user_commands = []

        self.send_queue = asyncio.Queue()

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
    def auth_handler(self, event, token):
        yield from self.send({

            "id": 1,
            "type": "message",
            "channel": event["channel"],
            "text": "Sending authorization token to your email address. Please send the token as your next message."
        })

        email = yield from get_user_email(event["user"], token)

        send_auth_email(email, *self.args.email_info)

    @asyncio.coroutine
    def receive_events(self, admins, token):
        try:
            connection = yield from start_slack_rtm_session(token)
            admin_uid_table = yield from get_user_ids(admins, token)

            while True:
                event = yield from connection.recv()
                event_type = event.get("type")

                logger.debug("Received event: %s", event)

                if event_type == "shutdown":
                    break

                elif event_type == "message":
                    text_groups = [group for group in event["text"].split(" ") if group != ""]

                    command = text_groups[0]
                    args = text_groups[1:]

                    uid = event["user"]

                    if command == "$auth":
                        if uid in admin_uid_table:
                            yield from self.auth_handler(event, token)

                        else:
                            yield from connection.send({

                                "id": 1,
                                "type": "message",
                                "channel": event["channel"],
                                "text": "You are not authorized to use this command."
                            })

                    elif command in self.admin_commands:
                        if uid in admin_uid_table:
                            handler = self.command_handlers.get(command)
                            if handler is not None:
                                yield from handler(self, event, token, *args)

                            else:
                                logger.debug("No handler registered for command %s", command)

                        else:
                            yield from connection.send({

                                "id": 1,
                                "type": "message",
                                "channel": event["channel"],
                                "text": "You are not authorized to use this command."
                            })

                    elif command in self.user_commands:
                        handler = self.command_handlers.get(command)
                        if handler is not None:
                            yield from handler(self, event, token, *args)

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

    def receive_thread(self, admins, token):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(self.receive_events(admins, token))

        except Exception:
            logger.exception("Error occurred")

    @asyncio.coroutine
    def send(self, event):
        # FIXME: this seems spammy and bad...
        connection = yield from start_slack_rtm_session(self.args.token)

        yield from connection.send(event)
        yield from connection.close()

    @asyncio.coroutine
    def run(self):
        try:
            executor = ThreadPoolExecutor(max_workers=1)

            recv_future = self.loop.run_in_executor(executor, self.receive_thread, self.args.admins, self.args.token)

            yield from asyncio.wait([recv_future])

        except Exception:
            logger.exception("Error occurred")

        finally:
            self.loop.call_soon_threadsafe(lambda: asyncio.async(self.send_queue.put({"type": "shutdown"})))