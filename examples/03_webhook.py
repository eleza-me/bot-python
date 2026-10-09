"""A webhook endpoint as a WSGI application.

Run it behind HTTPS (port 443 or 8443), for example with gunicorn behind nginx:

    gunicorn --chdir examples 03_webhook:application

or, to try it locally:  python examples/03_webhook.py

Register the public URL once with 03_webhook_setup.py.
Environment: ELEZA_BOT_TOKEN, ELEZA_WEBHOOK_SECRET.
"""

import os

from _common import token

from eleza_bot import Bot

bot = Bot(token())


@bot.on_start
def start(ctx):
    ctx.reply("سلام! این ربات با وبهوک کار می‌کند.")


@bot.on_text
def got(ctx):
    ctx.reply("دریافت شد: " + ctx.text)


# Checks the signature (401 when it is wrong), runs the handler, answers 200.
#
# Deliveries are "at least once": the same update can come twice. If doing
# something twice would hurt (charging, creating an order), remember
# ctx.update.id — in your database, with a unique index — and skip repeats.
application = bot.wsgi_app(os.environ.get("ELEZA_WEBHOOK_SECRET", ""))

if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    print("Listening on http://127.0.0.1:8080 (put HTTPS in front of it)")
    make_server("127.0.0.1", 8080, application).serve_forever()
