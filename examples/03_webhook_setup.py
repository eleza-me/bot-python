"""Registers (or removes) the webhook. Run once:

    python examples/03_webhook_setup.py https://bot.example.com/eleza/hook
    python examples/03_webhook_setup.py --info
    python examples/03_webhook_setup.py --delete
"""

import json
import sys

from _common import token

from eleza_bot import Client

api = Client(token())
arg = sys.argv[1] if len(sys.argv) > 1 else "--info"

if arg == "--delete":
    api.delete_webhook()
    print("Webhook removed; the bot is back on long polling.")
elif arg == "--info":
    print(json.dumps(api.get_webhook_info(), indent=2, ensure_ascii=False))
else:
    info = api.set_webhook(arg, max_connections=4)
    print(f"Webhook set to {info['url']}")
    if "secret" in info:
        # Shown only now. Keep it where the endpoint can read it.
        print(f"ELEZA_WEBHOOK_SECRET={info['secret']}")
