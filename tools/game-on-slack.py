import asyncio
import logging

from slackman import SlackServerManager, Argument, parse_args


def main():
    args, _ = parse_args()

    logging.basicConfig(level=args.log_level)

    manager = SlackServerManager(args)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(manager.run())


if __name__ == "__main__":
    main()
