import asyncio
import logging

from concurrent.futures import ThreadPoolExecutor

from .util import *

logger = logging.getLogger("Slack Client")


class SlackServerManager(object):
    def __init__(self, args):
        self.args = args
        self.loop = asyncio.get_event_loop()

        self.command_handlers = {}
        self.admin_commands = ("$auth", "$power")
        self.user_commands = ("$gameinfo",)

        self.send_queue = asyncio.Queue()
        self.receive_queue = asyncio.Queue()

    def register_handler(self, command, handler):
        if not asyncio.iscoroutinefunction(handler):
            raise ValueError("Command handlers must be coroutines.")

        self.command_handlers[command] = handler

    def unregister_handler(self, command):
        del self.command_handlers[command]

    @asyncio.coroutine
    def receive_events(self, admin_uid_table, queue, token):
        try:
            connection = yield from start_slack_rtm_session(token)

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

                    if command in self.admin_commands:
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

    def receive_thread(self, admin_uid_table, token):
        try:

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(self.receive_events(admin_uid_table, self.receive_queue, token))

        except Exception:
            logger.exception("Error occurred")

    @asyncio.coroutine
    def send_events(self, queue, token):
        try:
            connection = yield from start_slack_rtm_session(token)

            while True:
                event = yield from queue.get()

                logger.debug("Sending event: %s", event)

                yield from connection.send(event)

        except Exception:
            logger.exception("Error occurred")

    def send_thread(self, admin_uid_table, token):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(self.send_events(self.send_queue, token))

        except Exception:
            logger.exception("Error occurred")

    def send_event(self, event):
        self.loop.call_soon_threadsafe(lambda: asyncio.async(self.send_queue.put(event)))

    @asyncio.coroutine
    def run(self):
        executor = ThreadPoolExecutor(max_workers=1)

        admin_uid_table = yield from get_user_ids(self.args.admins, self.args.token)
        connection = yield from start_slack_rtm_session(self.args.token)

        try:
            self.loop.run_in_executor(executor, self.receive_thread, admin_uid_table, self.args.token)
            self.loop.run_in_executor(executor, self.send_thread, admin_uid_table, self.args.token)

            while True:
                pass

        finally:
            yield from connection.close()

            self.loop.call_soon_threadsafe(lambda: asyncio.async(self.receive_queue.put({"type": "shutdown"})))
            executor.shutdown(wait=True)
