import argparse


class Argument(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.kwargs = kwargs


def parse_args(*arguments):
    parser = argparse.ArgumentParser()

    parser.add_argument("--token", dest="token", required=True,
                        help="Authentication token of the slack bot integration that will be connecting.")
    parser.add_argument("--admins", dest="admins", nargs="+", required=True,
                        help="List of space delimited email addresses for Slack users to be treated as admins.")
    parser.add_argument("--log-level", dest="log_level", default="DEBUG", help="Sets the log level.")
    parser.add_argument("--email", dest="email_info", nargs=2, required=True,
                        help="Email address and password the Slack bot uses to send authorization tokens.")

    for argument in arguments:
        parser.add_argument(argument.name, **argument.kwargs)

    return parser.parse_known_args()
