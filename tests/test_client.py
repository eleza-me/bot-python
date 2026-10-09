import re
import unittest

from .fakes import FakeTransport, make_client

from eleza_bot import (ApiError, Button, Client, ElezaError, InlineKeyboard, InlineResult, InputFile, Markdown,
                       ReplyKeyboard, Text, TransportError)


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.http = FakeTransport()
        self.slept = []

    def client(self, **options):
        return make_client(self.http, self.slept, **options)

    def test_get_me_sends_the_token_and_decodes(self):
        self.http.json(200, {"id": "u1", "handle": "my_bot", "is_bot": True})
        me = self.client(language="en").get_me()
        self.assertEqual(me["handle"], "my_bot")
        r = self.http.sent()
        self.assertEqual((r["method"], r["url"]), ("GET", "https://api.eleza.me/bot/v1/me"))
        self.assertEqual(r["headers"]["Authorization"], "Bot ezb1.bot.key.secret")
        self.assertEqual(r["headers"]["Accept-Language"], "en")
        self.assertIsNone(r["body"])

    def test_empty_token_is_refused(self):
        with self.assertRaises(ElezaError):
            Client("  ")

    def test_send_message_adds_an_idempotency_key_and_keyboard(self):
        self.http.json(200, {"chat_id": "c1", "message_id": "m1", "seq": 7, "created_at": 1})
        kb = (InlineKeyboard().row(Button.callback("تهران", "city:thr"), Button.url("Site", "https://example.com"))
              .row(Button.switch_inline("Share")))
        out = self.client().send_message("c1", "سلام", reply_markup=kb, reply_to_seq=3)
        self.assertEqual(out["seq"], 7)
        r = self.http.sent()
        self.assertEqual((r["method"], r["url"]), ("POST", "https://api.eleza.me/bot/v1/chats/c1/messages"))
        self.assertIn("سلام".encode(), r["body"], "UTF-8 is not escaped")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", r["json"]["client_message_id"]))
        self.assertEqual(r["json"]["kind"], "text")
        self.assertEqual(r["json"]["reply_to_seq"], 3)
        self.assertEqual(r["json"]["reply_markup"]["inline_keyboard"], [
            [{"text": "تهران", "callback_data": "city:thr"}, {"text": "Site", "url": "https://example.com"}],
            [{"text": "Share", "switch_inline_query": ""}],
        ])

    def test_text_builder_becomes_entities_with_utf16_offsets(self):
        self.http.json(200, {"seq": 1})
        text = Text("😀 ").bold("سلام").plain(" ").link("here", "https://e.com").code("")
        self.client().send_message("c1", text)
        j = self.http.sent()["json"]
        self.assertEqual(j["text"], "😀 سلام here")
        self.assertEqual(j["entities"], [
            {"type": "bold", "offset": 3, "length": 4},
            {"type": "text_link", "offset": 8, "length": 4, "url": "https://e.com"},
        ])

    def test_reply_keyboards(self):
        kb = ReplyKeyboard().row("A", "B").row("C").resize().one_time().placeholder("Pick")
        self.assertEqual(kb.to_dict(), {
            "keyboard": [[{"text": "A"}, {"text": "B"}], [{"text": "C"}]],
            "resize_keyboard": True, "one_time_keyboard": True, "input_field_placeholder": "Pick",
        })
        self.assertEqual(ReplyKeyboard.remove().to_dict(), {"remove_keyboard": True})

    def test_callback_data_is_bounded_in_bytes(self):
        Button.callback("x", "a" * 64)
        with self.assertRaises(ElezaError):
            Button.callback("x", "a" * 65)
        with self.assertRaises(ElezaError):
            Button.callback("x", "س" * 33)

    def test_edit_and_remove_keyboard(self):
        self.http.json(200, {"seq": 7, "text": "new"})
        self.client().edit_message("c1", 7, "new", reply_markup=InlineKeyboard.none())
        r = self.http.sent()
        self.assertEqual((r["method"], r["url"]), ("PATCH", "https://api.eleza.me/bot/v1/chats/c1/messages/7"))
        self.assertEqual(r["json"], {"text": "new", "reply_markup": {"inline_keyboard": []}})

    def test_edit_needs_something(self):
        with self.assertRaises(ElezaError):
            self.client().edit_message("c1", 7)

    def test_no_content_answers(self):
        self.http.json(204).json(204).json(204).json(204)
        c = self.client()
        c.delete_message("c1", 7)
        self.assertEqual(self.http.sent()["method"], "DELETE")
        c.set_reaction("c1", 7, "👍")
        self.assertEqual(self.http.sent()["json"], {"emoji": "👍"})
        self.assertTrue(self.http.sent()["url"].endswith("/messages/7/reaction"))
        c.send_chat_action("c1")
        self.assertEqual(self.http.sent()["json"], {"action": "typing"})
        c.delete_webhook(True)
        self.assertTrue(self.http.sent()["url"].endswith("/bot/v1/webhook?drop_pending_updates=true"))

    def test_answer_callback_sends_an_empty_object(self):
        self.http.json(200, {"delivered": True}).json(200, {"delivered": False})
        c = self.client()
        self.assertTrue(c.answer_callback_query("q1"))
        self.assertEqual(self.http.sent()["body"], b"{}")
        self.assertFalse(c.answer_callback_query("q1", "Saved", alert=True))
        self.assertEqual(self.http.sent()["json"], {"text": "Saved", "alert": True})

    def test_answer_inline_query(self):
        self.http.json(204)
        self.client().answer_inline_query("q1", [
            InlineResult.article("thr", "Tehran", "Tehran: 24°").description("clear").thumbnail("https://e.com/t.png"),
            {"type": "article", "id": "syz", "title": "Shiraz", "text": "Shiraz: 27°"},
        ], cache_time=60, is_personal=True, next_offset="p2")
        j = self.http.sent()["json"]
        self.assertEqual([r["id"] for r in j["results"]], ["thr", "syz"])
        self.assertEqual(j["results"][0]["thumb_url"], "https://e.com/t.png")
        self.assertEqual((j["cache_time"], j["is_personal"], j["next_offset"]), (60, True, "p2"))

    def test_get_updates(self):
        self.http.json(200, {"updates": [
            {"update_id": 10, "type": "message.created", "occurred_at": "2026-10-03T08:00:00.000Z", "bot_id": "u1", "v": 1,
             "data": {"chat_id": "c1", "from": {"id": "u7", "name": "Sara"}, "message": {"seq": 12, "kind": "text", "text": "hi"}}},
        ]})
        ups = self.client().get_updates(10, 50, 30, ["message.created", "callback_query"])
        self.assertEqual(len(ups), 1)
        self.assertEqual((ups[0].id, ups[0].text, ups[0].sender_name, ups[0].seq), (10, "hi", "Sara", 12))
        r = self.http.sent()
        self.assertEqual(r["url"], "https://api.eleza.me/bot/v1/updates?limit=50&timeout=30&offset=10&allowed_updates=message.created%2Ccallback_query")
        self.assertGreater(r["timeout"], 30.0, "the HTTP timeout outlasts the poll")

    def test_commands(self):
        self.http.json(204).json(200, {"commands": [{"command": "help", "description": "Help"}]})
        c = self.client()
        c.set_commands({"/today": "Weather", "help": "Help"}, "en")
        self.assertEqual(self.http.sent()["json"], {"commands": [{"command": "today", "description": "Weather"},
                                                                 {"command": "help", "description": "Help"}], "language": "en"})
        self.assertEqual(c.get_commands()[0]["command"], "help")

    def test_set_webhook(self):
        self.http.json(200, {"url": "https://b.example/h", "secret": "s" * 20, "pending_update_count": 0})
        info = self.client().set_webhook("https://b.example/h", max_connections=4)
        self.assertEqual(info["secret"], "s" * 20)
        self.assertEqual(self.http.sent()["json"], {"url": "https://b.example/h", "max_connections": 4})

    def test_api_errors_carry_the_stable_code(self):
        self.http.problem(403, "bot.user_not_started")
        with self.assertRaises(ApiError) as cm:
            self.client().send_message("c1", "x")
        e = cm.exception
        self.assertEqual((e.code, e.status, e.request_id), ("bot.user_not_started", 403, "req-1"))
        self.assertTrue(e.cannot_write)
        self.assertNotIn("ezb1", str(e))
        self.assertEqual(len(self.http.requests), 1, "4xx is not retried")

    def test_rate_limit_is_retried_after_retry_after(self):
        self.http.problem(429, "rate_limited", retry_after=2).json(200, {"seq": 1})
        self.client().send_message("c1", "x")
        self.assertEqual(self.slept, [2.0])
        self.assertEqual(self.http.sent(0)["json"]["client_message_id"], self.http.sent(1)["json"]["client_message_id"],
                         "a retry repeats the same idempotency key")

    def test_server_and_network_errors_are_retried_for_idempotent_calls(self):
        self.http.fail().problem(503, "service.unavailable", True).json(200, {"id": "u1"})
        self.assertEqual(self.client().get_me()["id"], "u1")
        self.assertEqual(len(self.http.requests), 3)

    def test_network_error_on_a_non_idempotent_call_is_not_retried(self):
        self.http.fail()
        with self.assertRaises(TransportError):
            self.client().answer_callback_query("q1")
        self.assertEqual(len(self.http.requests), 1)

    def test_retries_stop(self):
        self.http.problem(500, "internal").problem(500, "internal")
        with self.assertRaises(ApiError) as cm:
            self.client(max_retries=1).get_me()
        self.assertEqual(cm.exception.code, "internal")
        self.assertEqual(len(self.http.requests), 2)

    def test_poll_conflict_is_not_retried(self):
        self.http.problem(409, "bot.poll_conflict")
        with self.assertRaises(ApiError):
            self.client().get_updates()

    def test_non_json_error_from_a_proxy(self):
        self.http.json(502, {"oops": 1}).json(502, {"oops": 1})
        with self.assertRaises(ApiError) as cm:
            self.client(max_retries=1).get_me()
        self.assertEqual(cm.exception.code, "http.502")

    def test_upload_and_send_photo(self):
        data = b"a" * 5 + b"b" * 5 + b"cc"  # 12 bytes, parts of 5
        (self.http
         .json(201, {"upload_id": "up1", "media_id": "md1", "part_size": 5, "state": "uploading", "parts": [
             {"n": 1, "url": "https://s3.example/p?part=1&sig=x"}, {"n": 2, "url": "https://s3.example/p?part=2&sig=x"},
             {"n": 3, "url": "https://s3.example/p?part=3&sig=x"}]})
         .json(200).json(200).json(200)
         .json(202, {"upload_id": "up1", "media_id": "md1", "state": "processing"})
         .problem(409, "media.not_ready", True)
         .json(200, {"seq": 9}))
        out = self.client().send_photo("c1", InputFile.from_bytes(data, "cat.jpg"), text="caption")
        self.assertEqual(out["seq"], 9)
        self.assertEqual(self.http.sent(0)["json"], {"purpose": "chat", "kind": "image", "size": 12, "mime": "image/jpeg", "filename": "cat.jpg"})
        for i, chunk in ((1, b"aaaaa"), (2, b"bbbbb"), (3, b"cc")):
            part = self.http.requests[i]
            self.assertEqual((part["method"], part["body"]), ("PUT", chunk))
            self.assertNotIn("Authorization", part["headers"], "the token never goes to the storage host")
        self.assertEqual(self.http.requests[4]["url"], "https://api.eleza.me/bot/v1/uploads/up1/complete")
        self.assertEqual(self.http.requests[4]["body"], b"")
        send = self.http.sent()["json"]
        send.pop("client_message_id")
        self.assertEqual(send, {"kind": "photo", "attachment": "md1", "text": "caption"})
        self.assertEqual(len(self.http.requests), 7, "the send is repeated while the media is processed")

    def test_failed_upload_is_aborted(self):
        (self.http
         .json(201, {"upload_id": "up1", "media_id": "md1", "part_size": 5, "state": "uploading", "parts": [{"n": 1, "url": "https://s3.example/p"}]})
         .json(403).json(204))
        with self.assertRaises(ApiError) as cm:
            self.client().upload_file(InputFile.from_bytes(b"abc", "a.bin"))
        self.assertEqual(cm.exception.code, "upload.part_failed")
        self.assertEqual(self.http.sent()["method"], "DELETE")
        self.assertTrue(self.http.sent()["url"].endswith("/bot/v1/uploads/up1"))

    def test_create_post_is_idempotent(self):
        self.http.problem(409, "bot.post_in_progress", True).json(200, {"id": "p1", "limited": True})
        out = self.client().create_post("خبر تازه", reply_policy="followers")
        self.assertEqual(out["id"], "p1")
        self.assertEqual(self.http.sent(0)["json"]["client_post_id"], self.http.sent(1)["json"]["client_post_id"])
        self.assertEqual(self.http.sent()["json"]["reply_policy"], "followers")

    def test_token_stays_out_of_repr(self):
        self.assertNotIn("secret", repr(self.client()))

    def test_markdown_escape(self):
        self.assertEqual(Markdown.escape("a*b_c~d||e`f[g](h) \\"), "a\\*b\\_c\\~d\\|\\|e\\`f\\[g](h) \\\\")
        self.assertEqual(Markdown.bold("1*2"), "*1\\*2*")
        self.assertEqual(Markdown.link("a]b", "https://e.com/x_(y)"), "[a\\]b](https://e.com/x_(y%29)")


if __name__ == "__main__":
    unittest.main()
