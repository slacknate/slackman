import asyncio
import logging

from wakeonlan import wol
from slackman import SlackServerManager, Argument, parse_args


@asyncio.coroutine
def power_handler(manager, event, state):
    if state.lower() == "on":
        wol.send_magic_packet(manager.args.mac_addr)

        yield from manager.send(event["channel"], "Powering on server.")

    elif state.lower() == "off":
        yield from manager.send(event["channel"], "Power off not implemented. Sorry! Coming soon!")

    else:
        yield from manager.send(event["channel"], "Unknown power state {}".format(state))


def main():
    args, _ = parse_args(Argument("--mac-addr", dest="mac_addr", required=True, help="MAC address of the server."))

    logging.basicConfig(level=args.log_level)

    manager = SlackServerManager(args)
    manager.register_admin_commands("$power")
    manager.register_handler("$power", power_handler)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(manager.run())


if __name__ == "__main__":
    main()