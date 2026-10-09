import io
import time
import unittest

from .fakes import FakeTransport, make_client

from eleza_bot import ApiError, Bot, Update, UpdateType, WebhookError, webhook

SECRET = "whsec_0123456789abcdef"
BODY = b'{"update_id":1791000000123,"type":"message.created","occurred_at":"2026-10-03T08:00:00.000Z","bot_id":"u1","v":1,"data":{"chat_id":"c1"}}'


def update(type_, data, id_=1):
    return Update(id_, type_, "2026-10-03T08:00:00.000Z", "u1", data)


def msg(kind, text=""):
    return {"chat_id": "c1", "from": {"id": "u7"}, "message": {"seq": 1, "kind": kind, "text": text}}


class BotTest(unittest.TestCase):
    def setUp(self):
        self.http = FakeTransport()
        self.bot = Bot(make_client(self.http))

    def test_routing(self):
        seen = []
        bot = self.bot
        bot.on_start(lambda c: seen.append("start:" + c.payload))
        bot.on_command("/Help")(lambda c: seen.append("help:" + c.args))
        bot.on_text(pattern=r"^\d+$")(lambda c: seen.append("digits"))
        bot.on_text(lambda c: seen.append("text:" + c.text))
        bot.on_kind("photo")(lambda c: seen.append("photo"))
        bot.on_callback("city:*")(lambda c: seen.append("city:" + c.callback_data))
        bot.on_callback("ok")(lambda c: seen.append("ok"))
        bot.on_inline_query(lambda c: seen.append("inline:" + c.query))
        bot.fallback(lambda c: seen.append("other:" + c.update.type))

        bot.handle(update(UpdateType.USER_STARTED_BOT, {**msg("text", "/start promo"), "command": "start", "payload": "promo"}))
        bot.handle(update(UpdateType.COMMAND_RECEIVED, {**msg("text", "/help me"), "command": "help", "args": "me"}))
        bot.handle(update(UpdateType.MESSAGE_CREATED, msg("text", "42")))
        bot.handle(update(UpdateType.MESSAGE_CREATED, msg("text", "hello")))
        bot.handle(update(UpdateType.MESSAGE_CREATED, msg("photo", "caption")))
        bot.handle(update(UpdateType.CALLBACK_QUERY, {"id": "q", "chat_id": "c1", "data": "city:thr"}))
        bot.handle(update(UpdateType.CALLBACK_QUERY, {"id": "q", "chat_id": "c1", "data": "ok"}))
        bot.handle(update(UpdateType.CALLBACK_QUERY, {"id": "q", "chat_id": "c1", "data": "okay"}))
        bot.handle(update(UpdateType.INLINE_QUERY, {"id": "q", "query": "tehran"}))
        bot.handle(update("something.new", {}))

        self.assertEqual(seen, ["start:promo", "help:me", "digits", "text:hello", "photo", "city:city:thr", "ok",
                                "other:callback_query", "inline:tehran", "other:something.new"])

    def test_decorators_return_the_function(self):
        @self.bot.on_text
        def echo(ctx):
            return None

        @self.bot.on_callback
        def press(ctx):
            return None

        self.assertTrue(callable(echo) and callable(press))
        self.assertTrue(self.bot.handle(update(UpdateType.CALLBACK_QUERY, {"id": "q", "data": "x"})))

    def test_unhandled_update_is_ignored(self):
        self.assertFalse(self.bot.handle(update("something.new", {})))

    def test_handler_errors_go_to_on_error(self):
        errors = []

        @self.bot.on_message
        def boom(ctx):
            raise RuntimeError("boom")

        self.bot.on_error(lambda e, u: errors.append(f"{e}@{u.id}"))
        self.assertTrue(self.bot.handle(update(UpdateType.MESSAGE_CREATED, {}, 5)))
        self.assertEqual(errors, ["boom@5"])

    def test_context_shortcuts(self):
        self.http.json(200, {"seq": 2}).json(200, {"delivered": True}).json(200, {"seq": 1})
        self.bot.on_text(lambda c: c.reply_quoting("pong"))

        @self.bot.on_callback
        def press(c):
            c.answer("done")
            c.edit_message("picked " + c.callback_data)

        self.bot.handle(update(UpdateType.MESSAGE_CREATED, {"chat_id": "c1", "message": {"seq": 4, "kind": "text", "text": "ping"}}))
        self.assertEqual(self.http.sent()["json"]["reply_to_seq"], 4)
        self.bot.handle(update(UpdateType.CALLBACK_QUERY, {"id": "q9", "chat_id": "c1", "data": "a", "message": {"seq": 1}}))
        self.assertTrue(self.http.requests[1]["url"].endswith("/bot/v1/callback-queries/q9/answer"))
        self.assertEqual(self.http.requests[2]["method"], "PATCH")
        self.assertTrue(self.http.requests[2]["url"].endswith("/bot/v1/chats/c1/messages/1"))

    def test_run_confirms_handled_updates_and_stops(self):
        def u(i):
            return {"update_id": i, "type": "message.created", "data": {"chat_id": "c1", "message": {"seq": i, "kind": "text", "text": "t"}}}

        (self.http.json(200, {"updates": [u(10), u(11)]})
         .problem(503, "service.unavailable", True)  # retried by the client
         .json(200, {"updates": [u(12)]})
         .json(200, {"updates": []}))  # the confirmation on the way out
        handled = []

        @self.bot.on_text
        def on_text(c):
            handled.append(c.update.id)
            if c.update.id == 12:
                self.bot.stop()

        self.bot.run(timeout=20, allowed_updates=["message.created"])
        urls = [r["url"] for r in self.http.requests]
        self.assertEqual(handled, [10, 11, 12])
        self.assertIn("allowed_updates=message.created", urls[0])
        self.assertNotIn("offset=", urls[0])
        self.assertIn("offset=12", urls[1])
        self.assertNotIn("allowed_updates", urls[1])
        self.assertIn("offset=13", urls[3])
        self.assertIn("timeout=0", urls[3])

    def test_run_gives_up_on_errors_a_retry_cannot_fix(self):
        self.http.problem(409, "bot.webhook_active")
        with self.assertRaises(ApiError) as cm:
            self.bot.run()
        self.assertEqual(cm.exception.code, ApiError.WEBHOOK_ACTIVE)

    def test_keyboard_interrupt_ends_run_quietly(self):
        self.http.json(200, {"updates": [{"update_id": 5, "type": "message.created", "data": {}}]}).json(200, {"updates": []})

        @self.bot.fallback
        def stop(ctx):
            raise KeyboardInterrupt

        self.bot.run()
        self.assertEqual(len(self.http.requests), 1, "the interrupted update was not confirmed")

    def test_drop_pending_updates(self):
        (self.http.json(200, {"updates": [{"update_id": 5, "type": "message.created", "data": {}}]})
         .json(200, {"updates": []}).problem(401, "bot.unauthorized").json(200, {"updates": []}))
        handled = []
        self.bot.fallback(lambda c: handled.append(1))
        with self.assertRaises(ApiError):
            self.bot.run(drop_pending_updates=True)
        self.assertEqual(handled, [])
        self.assertIn("offset=6", self.http.requests[1]["url"])
        self.assertIn("offset=6", self.http.requests[2]["url"])


class WebhookTest(unittest.TestCase):
    def test_signature_matches_the_documented_scheme(self):
        import hashlib
        import hmac
        want = "v1=" + hmac.new(SECRET.encode(), b"1791000000.1791000000123." + BODY, hashlib.sha256).hexdigest()
        self.assertEqual(webhook.sign(SECRET, 1791000000, "1791000000123", BODY), want)
        self.assertEqual(webhook.sign(SECRET.encode(), "1791000000", "1791000000123", BODY.decode()), want)

    def test_verify(self):
        now = 1791000100
        sig = webhook.sign(SECRET, now, "1791000000123", BODY)
        ok = lambda **kw: webhook.verify(**{"secret": SECRET, "signature": sig, "timestamp": str(now), "delivery_id": "1791000000123",
                                           "raw_body": BODY, "now": now, **kw})
        self.assertTrue(ok(now=now + 299))
        self.assertFalse(ok(now=now + 301), "too old")
        self.assertFalse(ok(now=now - 301), "from the future")
        self.assertFalse(ok(delivery_id="1791000000124"), "another delivery")
        self.assertFalse(ok(raw_body=BODY + b" "), "body changed")
        self.assertFalse(ok(secret="another-secret-0123"))
        self.assertFalse(ok(timestamp="abc"))
        self.assertFalse(ok(signature=""))
        self.assertFalse(ok(signature="v1=é"))

    def test_parse(self):
        ts = str(int(time.time()))
        headers = {"X-ELEZA-SIGNATURE": webhook.sign(SECRET, ts, "1791000000123", BODY), "x-eleza-timestamp": ts,
                   "X-Eleza-Delivery-Id": ["1791000000123"]}
        u = webhook.parse(SECRET, BODY, headers)
        self.assertEqual((u.id, u.chat_id), (1791000000123, "c1"))
        with self.assertRaises(WebhookError):
            webhook.parse(SECRET, BODY, {"X-Eleza-Timestamp": ts})

    def test_wsgi_app(self):
        seen = []
        bot = Bot(make_client(FakeTransport()))
        bot.on(UpdateType.MESSAGE_CREATED)(lambda c: seen.append(c.chat_id))
        app = bot.wsgi_app(SECRET)

        def call(method="POST", body=BODY, signature=None):
            ts = str(int(time.time()))
            status = []
            environ = {"REQUEST_METHOD": method, "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body),
                       "HTTP_X_ELEZA_SIGNATURE": signature or webhook.sign(SECRET, ts, "1791000000123", body),
                       "HTTP_X_ELEZA_TIMESTAMP": ts, "HTTP_X_ELEZA_DELIVERY_ID": "1791000000123"}
            list(app(environ, lambda s, h: status.append(s)))
            return status[0][:3]

        self.assertEqual(call(), "200")
        self.assertEqual(seen, ["c1"])
        self.assertEqual(call(signature="v1=00"), "401")
        self.assertEqual(call(method="GET"), "405")
        self.assertEqual(call(body=b""), "400")
        self.assertEqual(seen, ["c1"])


if __name__ == "__main__":
    unittest.main()
