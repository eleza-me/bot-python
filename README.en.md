# Eleza Bot SDK for Python

Build bots for [Eleza](https://eleza.me) in a few lines of Python: receive updates (long polling or webhook), send text and media, keyboards, inline mode and Eli posts.

[فارسی](README.md) · [Bot API guide](https://eleza.me/bots)

- No dependencies: Python 3.9+ and the standard library
- Automatic retries for rate limits (429) and transient failures, with an idempotency key so nothing is sent twice
- Webhook signature verification and a ready WSGI application
- Media upload in one call

## Install

```bash
pip install eleza-bot-sdk
```

Or straight from this repository: run `pip install .` in the folder.

## Get a token

Open a chat with **@BotFather** in Eleza and send `/newbot`. You get a token that starts with `ezb1.`.

**The token is a password.** It is shown once. Keep it out of your code and repository; read it from the environment. If it leaks: `/revoke`, then `/token` in BotFather.

## First bot

```python
import os
from eleza_bot import Bot

bot = Bot(os.environ["ELEZA_BOT_TOKEN"])

@bot.on_start
def start(ctx):
    ctx.reply(f"Hello {ctx.sender_name}!")

@bot.on_command("help")
def help_(ctx):
    ctx.reply("I repeat what you write.")

@bot.on_text
def echo(ctx):
    ctx.reply(ctx.text)

bot.run()  # long polling
```

```bash
ELEZA_BOT_TOKEN='ezb1.…' python bot.py
```

Complete bots are in [`examples/`](examples).

## Receiving updates

The first handler that matches an update handles it.

| Decorator | Runs when |
|---|---|
| `@bot.on_start` | the person pressed Start or sent `/start`; `ctx.payload` is the parameter of `eleza.me/<handle>?start=<payload>` |
| `@bot.on_command("help")` | `/help`; the rest of the text is `ctx.args` |
| `@bot.on_text` or `@bot.on_text(pattern=r"^\d+$")` | a text message that is not a command, optionally matching a regular expression |
| `@bot.on_kind("photo")` | a message of one kind: `photo`, `video`, `file`, `voice`, `audio`, `gif`, `video_note`, `sticker`, … |
| `@bot.on_message` | any new message that is not a command |
| `@bot.on_callback("city:*")` | an inline button was pressed; `ctx.callback_data` |
| `@bot.on_inline_query` | someone typed `@your_bot …` in a chat |
| `@bot.on(UpdateType.BOT_BLOCKED)` | any update type (`UpdateType` constants) |
| `@bot.fallback` | whatever no other handler took |
| `@bot.on_error` | a handler raised (`def f(error, update)`); the bot carries on with the next update |

**Delivery is at least once:** the same update may arrive twice. Where doing something twice would hurt (orders, credits), store `ctx.update.id` and skip repeats. Updates of one chat arrive in order; there is no order across chats.

A person's name and handle (`sender["name"]`, `sender["handle"]`) need the `profile:read` scope. A bot never gets a phone number.

### Long polling

Run **one** `bot.run()` process per bot: a second poll ends the first with `bot.poll_conflict`. An update is confirmed only after its handler returned, so a crash loses nothing. Ctrl+C and SIGTERM stop it cleanly.

```python
bot.run(
    timeout=30,                  # at most 50 seconds
    allowed_updates=["message.created", "command.received", "user.started_bot", "callback_query"],
    drop_pending_updates=False,  # True: skip what queued up while the bot was down
)
```

### Webhook

The URL must be HTTPS on port 443 or 8443 at a public address. Register it once and keep the secret:

```python
info = bot.api.set_webhook("https://bot.example.com/eleza/hook")
print(info["secret"])  # shown only this once
```

The simplest endpoint is the ready WSGI application (gunicorn, uWSGI, mod_wsgi):

```python
# hook.py  →  gunicorn hook:application
application = bot.wsgi_app(os.environ["ELEZA_WEBHOOK_SECRET"])
```

It checks the signature and the timestamp (401 when wrong), runs the handler and answers 200. Eleza waits 10 seconds for a 2xx and retries otherwise; hand slow work to a queue or another thread.

In a framework, pass the raw body and the headers yourself:

```python
# Flask
from eleza_bot import WebhookError

@app.post("/eleza/hook")
def hook():
    try:
        bot.handle_webhook(SECRET, request.get_data(), request.headers)
    except WebhookError:
        return "", 401
    return "", 200
```

```python
# FastAPI
from fastapi import HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

@app.post("/eleza/hook")
async def hook(request: Request):
    body = await request.body()
    try:
        await run_in_threadpool(bot.handle_webhook, SECRET, body, request.headers)
    except WebhookError:
        raise HTTPException(401)
    return Response(status_code=200)
```

While a webhook is set, long polling answers `bot.webhook_active`. Go back with `bot.api.delete_webhook()`.

## Sending

A bot can write only in a chat the person started, and not after they blocked it.

```python
from eleza_bot import Client

api = Client(os.environ["ELEZA_BOT_TOKEN"])   # or bot.api

sent = api.send_message(chat_id, "Hello!")
api.send_message(chat_id, "A reply", reply_to_seq=12)

api.edit_message(chat_id, sent["seq"], "New text")   # the bot's own messages only
api.delete_message(chat_id, sent["seq"])
api.set_reaction(chat_id, 12, "👍")
api.send_chat_action(chat_id)                         # "typing…"
```

### Formatting

`Text` is the safe way, because it needs no escaping. Use it whenever a piece of the text comes from a person or another system:

```python
from eleza_bot import Text

text = (Text("Order ").bold(order_name).plain(" is placed.").newline()
        .plain("Tracking code: ").code(tracking_code).newline()
        .link("View the order", "https://example.com/orders/42"))

api.send_message(chat_id, text)
```

Or with `parse_mode`:

```python
from eleza_bot import Markdown

api.send_message(chat_id, "*bold* _italic_ __underline__ ~strike~ ||spoiler|| `code` [link](https://eleza.me)",
                 parse_mode="markdown")

# Escape what you did not write yourself: an unclosed marker is a bot.parse_error
api.send_message(chat_id, "Hello " + Markdown.escape(user_name), parse_mode="markdown")
```

### Media

```python
from eleza_bot import InputFile

api.send_photo(chat_id, InputFile.from_path("photo.jpg"), text="caption")
api.send_file(chat_id, InputFile.from_bytes(pdf_bytes, "report.pdf"))
api.send_voice(chat_id, InputFile.from_path("voice.ogg"))
api.send_audio(chat_id, InputFile.from_path("song.mp3"), audio={"title": "Song", "performer": "Artist"})

# Upload once, send many times
media_id = api.upload_file(InputFile.from_path("banner.jpg"), "image")
for chat in chat_ids:
    api.send_photo(chat, media_id)
```

Also `send_video`, `send_gif`, `send_video_note` and `send_sticker`. A file is always given as an `InputFile`; no string is ever read as a path, so text from a person can never make your bot send a file from your server.

The kind of an upload differs from the kind of a message: a `photo` message carries an `image` upload (the others share their name). A bot can read only the media it uploaded itself.

## Keyboards

### Inline keyboard (under a message)

```python
from eleza_bot import Button, InlineKeyboard

keyboard = (InlineKeyboard()
            .row(Button.callback("Tehran", "city:thr"), Button.callback("Shiraz", "city:syz"))
            .row(Button.url("Site", "https://example.com"))
            .row(Button.switch_inline("Share…", "tehran")))

api.send_message(chat_id, "Choose a city", reply_markup=keyboard)

@bot.on_callback("city:*")
def city(ctx):
    ctx.answer("Selected")                           # always answer, so the button stops spinning
    ctx.edit_message("City: " + ctx.callback_data)   # edits the message the button is on
```

`callback_data` is at most 64 bytes and is never sent to people's apps: the server tells you which button was pressed and by whom, so you can trust it. Answer every press within 10 seconds. Up to 25 rows, 8 buttons per row, 100 in total. Remove the buttons with `api.edit_reply_markup(chat_id, seq, InlineKeyboard.none())`.

### Reply keyboard (replaces the person's keyboard)

```python
from eleza_bot import ReplyKeyboard

api.send_message(chat_id, "What next?",
                 reply_markup=ReplyKeyboard().row("Today", "Week").row("Settings").resize().one_time())

api.send_message(chat_id, "Closed", reply_markup=ReplyKeyboard.remove())
```

Pressing a button sends its text as an ordinary message from the person.

## Commands and deep links

```python
api.set_commands({"today": "Today's weather", "help": "Help"})
```

`https://eleza.me/my_weather_bot?start=promo42` opens the bot with a Start button; in `on_start`, `ctx.payload` is `promo42` (up to 64 characters of `A-Za-z0-9_-`).

## Inline mode

Send `/setinline` to BotFather first. Answer within 8 seconds:

```python
from eleza_bot import InlineResult

@bot.on_inline_query
def inline(ctx):
    ctx.answer_inline([
        InlineResult.article("thr", "Tehran", "Tehran: 24°, clear").description("24°, clear"),
        InlineResult.article("syz", "Shiraz", "Shiraz: 27°").thumbnail("https://example.com/syz.png"),
    ], cache_time=60)
```

Up to 50 results. The picked result is sent as the person's own message, marked "via @your_bot". Its buttons can only be URL or switch-inline buttons. Inline mode is not available in anonymous conversations.

## Eli posts

```python
post = api.create_post("A new version is out #eleza")

api.create_post("caption", media=[
    {"id": api.upload_file(InputFile.from_path("a.jpg"), "image", "post"), "alt": "what the picture shows"},
])

api.create_post(poll={"question": "Which one?", "options": ["A", "B"], "duration": "24h"})

api.delete_post(post["id"])
```

- Top-level posts only: a bot cannot reply, quote or publish threads.
- `limited: true` in the answer means the bot has no official mark, so the post reaches its followers and its profile only.
- `post.reply_created`, `post.reaction_changed` and `follower.added` arrive through `@bot.on(...)`. They open no way to message those people.

## Errors

```python
from eleza_bot import ApiError, TransportError

try:
    api.send_message(chat_id, "Hello")
except ApiError as e:
    if e.cannot_write:
        ...  # not started, or blocked: take this person off your list
    print(e.code, e.request_id)   # a stable code, e.g. bot.user_not_started
except TransportError:
    ...  # the network: no answer was received
```

| Status | `code` | Meaning |
|---|---|---|
| 401 | `bot.unauthorized` | wrong or revoked token |
| 403 | `bot.suspended`, `bot.switched_off`, `bot.disabled` | the bot is suspended or switched off |
| 403 | `bot.scope_missing` | the token lacks the scope |
| 403 | `bot.user_not_started`, `chat.blocked` | the person has not started the bot / has blocked it |
| 404 | `chat.not_found` | not a chat of this bot |
| 400 | `bot.parse_error`, `bot.markup_invalid` | broken formatting or keyboard |
| 409 | `bot.poll_conflict`, `bot.webhook_active` | another poll is running / a webhook is set |
| 429 | `rate_limited` | slow down; wait `retry_after` seconds |

The SDK retries 429, 5xx and network failures itself (3 times by default) and honors `retry_after`. Messages and posts always carry an idempotency key, so a retry never sends twice. For bulk sending, pace yourself too: by default 30 messages per second per bot and 60 per minute per chat.

## Options

```python
api = Client(
    token,
    timeout=30,          # seconds per request
    max_retries=3,
    language="en",       # language of error titles: fa or en
    base_url="https://api.eleza.me",
)

bot = Bot(api)           # or Bot(token, timeout=30, ...)
```

A proxy is read from the `HTTPS_PROXY` environment variable. The SDK is synchronous; in an asyncio program run its calls with `asyncio.to_thread`. For a route the SDK has no method for yet: `api.request("GET", "/bot/v1/…")`.

## Tests

```bash
python -m unittest discover -s . -p "test_*.py" -t .
```

## License

MIT — see [LICENSE](LICENSE).
