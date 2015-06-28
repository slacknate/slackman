import smtplib

from random import SystemRandom
from email.message import Message

AUTH_EMAIL = """
Hello Cathedral user,

You have requested authorization to use administrative commands.

Authorization token: {auth_token}
"""


def generate_auth_token():
    rand = SystemRandom()
    bits = rand.getrandbits(256)
    secret = "{:064x}".format(bits)
    return secret


def send_auth_email(auth_token, destination, username, password):
    msg = Message()
    msg.add_header("subject", "Cathedral Admin Access")
    msg.set_payload(AUTH_EMAIL.format(auth_token=auth_token))

    server = smtplib.SMTP("smtp.gmail.com:587")
    server.starttls()

    server.login(username, password)
    server.sendmail(username, destination, msg.as_string())

    server.quit()
