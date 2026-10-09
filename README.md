<div dir="rtl">

# SDK ربات الزا برای پایتون

با این کتابخانه در چند خط پایتون برای [الزا](https://eleza.me) ربات بسازید: دریافت پیام‌ها (long polling یا وبهوک)، ارسال متن و رسانه، دکمه‌ها، حالت درون‌خطی (inline) و انتشار الی.

[English](README.en.md) · [راهنمای Bot API](https://eleza.me/bots)

- بدون وابستگی: فقط پایتون 3.9 به بالا و کتابخانهٔ استاندارد
- تلاش دوبارهٔ خودکار برای محدودیت نرخ (429) و خطاهای موقت، با کلید تکرارناپذیری تا پیامی دوبار فرستاده نشود
- بررسی امضای وبهوک و یک برنامهٔ WSGI آماده
- بارگذاری رسانه در یک فراخوانی

## نصب

</div>

```bash
pip install eleza-bot-sdk
```

<div dir="rtl">

یا مستقیم از همین مخزن: داخل پوشه `pip install .` را اجرا کنید.

## ساخت ربات و گرفتن توکن

در برنامهٔ الزا با **@BotFather** گفت‌وگو کنید و `/newbot` را بفرستید. در پایان یک توکن می‌گیرید که با `ezb1.` شروع می‌شود.

**توکن مثل رمز عبور است.** فقط یک بار نشان داده می‌شود؛ آن را در کد و مخزن نگذارید و از متغیر محیطی بخوانید. اگر لو رفت در BotFather دستور `/revoke` و سپس `/token` را بفرستید.

## اولین ربات

</div>

```python
import os
from eleza_bot import Bot

bot = Bot(os.environ["ELEZA_BOT_TOKEN"])

@bot.on_start
def start(ctx):
    ctx.reply(f"سلام {ctx.sender_name}!")

@bot.on_command("help")
def help_(ctx):
    ctx.reply("هر چه بنویسی تکرار می‌کنم.")

@bot.on_text
def echo(ctx):
    ctx.reply(ctx.text)

bot.run()  # long polling
```

```bash
ELEZA_BOT_TOKEN='ezb1.…' python bot.py
```

<div dir="rtl">

نمونه‌های کامل در پوشهٔ [`examples/`](examples) هستند.

## دریافت به‌روزرسانی‌ها

اولین هندلری که با یک به‌روزرسانی جور باشد آن را می‌گیرد.

| دکوراتور | چه وقت اجرا می‌شود |
|---|---|
| `@bot.on_start` | کاربر «شروع» را زده یا `/start` فرستاده؛ `ctx.payload` پارامتر پیوند `eleza.me/<handle>?start=<payload>` است |
| `@bot.on_command("help")` | دستور `/help`؛ متن بعد از دستور در `ctx.args` |
| `@bot.on_text` یا `@bot.on_text(pattern=r"^\d+$")` | پیام متنی (غیر از دستور)، در صورت نیاز با عبارت باقاعده |
| `@bot.on_kind("photo")` | پیام از یک نوع خاص: `photo`، `video`، `file`، `voice`، `audio`، `gif`، `video_note`، `sticker` و … |
| `@bot.on_message` | هر پیام تازه‌ای که دستور نیست |
| `@bot.on_callback("city:*")` | فشردن دکمهٔ شیشه‌ای؛ `ctx.callback_data` |
| `@bot.on_inline_query` | کاربر در یک گفت‌وگو `@ربات شما …` نوشته |
| `@bot.on(UpdateType.BOT_BLOCKED)` | هر نوع به‌روزرسانی (ثابت‌های `UpdateType`) |
| `@bot.fallback` | هر چیزی که هندلر دیگری نداشت |
| `@bot.on_error` | خطای هندلرها (`def f(error, update)`)؛ ربات با به‌روزرسانی بعدی ادامه می‌دهد |

**تضمین تحویل «حداقل یک بار» است:** ممکن است یک به‌روزرسانی دوبار برسد. اگر تکرار یک کار ضرر دارد (ثبت سفارش، کسر اعتبار)، `ctx.update.id` را ذخیره کنید و تکراری‌ها را رد کنید. ترتیب به‌روزرسانی‌های یک گفت‌وگو حفظ می‌شود؛ بین گفت‌وگوهای مختلف ترتیبی وجود ندارد.

نام و شناسهٔ کاربر (`sender["name"]`، `sender["handle"]`) فقط با مجوز `profile:read` می‌آید. شمارهٔ تلفن هرگز به ربات داده نمی‌شود.

### Long polling

برای هر ربات فقط **یک** پردازش `bot.run()` اجرا کنید؛ اجرای دوم، اولی را با خطای `bot.poll_conflict` متوقف می‌کند. به‌روزرسانی فقط بعد از تمام‌شدن هندلرش تأیید می‌شود، پس اگر برنامه وسط کار از کار بیفتد چیزی گم نمی‌شود. با Ctrl+C یا SIGTERM تمیز متوقف می‌شود.

</div>

```python
bot.run(
    timeout=30,                  # حداکثر ۵۰ ثانیه
    allowed_updates=["message.created", "command.received", "user.started_bot", "callback_query"],
    drop_pending_updates=False,  # True: هر چه در نبود ربات جمع شده نادیده گرفته شود
)
```

<div dir="rtl">

### وبهوک

نشانی باید HTTPS روی درگاه 443 یا 8443 و در دسترس عموم باشد. یک بار ثبتش کنید و راز (secret) را نگه دارید:

</div>

```python
info = bot.api.set_webhook("https://bot.example.com/eleza/hook")
print(info["secret"])  # فقط همین یک بار نشان داده می‌شود
```

<div dir="rtl">

ساده‌ترین راه، برنامهٔ WSGI آماده است (gunicorn، uWSGI، mod_wsgi):

</div>

```python
# hook.py  →  gunicorn hook:application
application = bot.wsgi_app(os.environ["ELEZA_WEBHOOK_SECRET"])
```

<div dir="rtl">

امضا و زمان درخواست بررسی می‌شود (در صورت نادرستی 401)، هندلر اجرا می‌شود و 200 برمی‌گردد. الزا ۱۰ ثانیه منتظر پاسخ 2xx می‌ماند و در غیر این صورت دوباره تلاش می‌کند؛ کار طولانی را به صف یا یک نخ دیگر بسپارید.

در فریم‌ورک‌ها بدنهٔ خام و هدرها را خودتان بدهید:

</div>

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

<div dir="rtl">

تا وقتی وبهوک فعال است long polling کار نمی‌کند (`bot.webhook_active`). برای برگشتن: `bot.api.delete_webhook()`.

## ارسال پیام

ربات فقط در گفت‌وگویی می‌تواند بنویسد که کاربر آن را شروع کرده باشد، و نه بعد از این‌که کاربر ربات را مسدود کرد.

</div>

```python
from eleza_bot import Client

api = Client(os.environ["ELEZA_BOT_TOKEN"])   # یا bot.api

sent = api.send_message(chat_id, "سلام!")
api.send_message(chat_id, "پاسخ به پیام شما", reply_to_seq=12)

api.edit_message(chat_id, sent["seq"], "متن تازه")   # فقط پیام‌های خود ربات
api.delete_message(chat_id, sent["seq"])
api.set_reaction(chat_id, 12, "👍")
api.send_chat_action(chat_id)                         # «در حال نوشتن…»
```

<div dir="rtl">

### قالب‌بندی متن

امن‌ترین راه `Text` است، چون نیازی به escape ندارد؛ هر جا بخشی از متن از کاربر یا سیستم دیگری می‌آید از آن استفاده کنید:

</div>

```python
from eleza_bot import Text

text = (Text("سفارش ").bold(order_name).plain(" ثبت شد.").newline()
        .plain("کد پیگیری: ").code(tracking_code).newline()
        .link("مشاهدهٔ سفارش", "https://example.com/orders/42"))

api.send_message(chat_id, text)
```

<div dir="rtl">

یا با `parse_mode`:

</div>

```python
from eleza_bot import Markdown

api.send_message(chat_id, "*پررنگ* _کج_ __زیرخط__ ~خط‌خورده~ ||پنهان|| `کد` [پیوند](https://eleza.me)",
                 parse_mode="markdown")

# متنی که خودتان ننوشته‌اید را escape کنید؛ علامت بازِ بسته‌نشده خطای bot.parse_error می‌دهد
api.send_message(chat_id, "سلام " + Markdown.escape(user_name), parse_mode="markdown")
```

<div dir="rtl">

### رسانه

</div>

```python
from eleza_bot import InputFile

api.send_photo(chat_id, InputFile.from_path("photo.jpg"), text="زیرنویس")
api.send_file(chat_id, InputFile.from_bytes(pdf_bytes, "report.pdf"))
api.send_voice(chat_id, InputFile.from_path("voice.ogg"))
api.send_audio(chat_id, InputFile.from_path("song.mp3"), audio={"title": "نام آهنگ", "performer": "خواننده"})

# یک بار بارگذاری، چند بار ارسال
media_id = api.upload_file(InputFile.from_path("banner.jpg"), "image")
for chat in chat_ids:
    api.send_photo(chat, media_id)
```

<div dir="rtl">

همچنین `send_video`، `send_gif`، `send_video_note` و `send_sticker`. فایل همیشه با `InputFile` داده می‌شود و هیچ رشته‌ای به‌عنوان مسیر فایل تعبیر نمی‌شود، پس متن کاربر هرگز نمی‌تواند فایلی از سرور شما را بفرستد.

نوع بارگذاری با نوع پیام فرق دارد: پیام `photo` یک بارگذاری از نوع `image` دارد (بقیه هم‌نام‌اند). ربات فقط به رسانه‌ای که خودش بارگذاری کرده دسترسی دارد.

## دکمه‌ها

### دکمه‌های شیشه‌ای (زیر پیام)

</div>

```python
from eleza_bot import Button, InlineKeyboard

keyboard = (InlineKeyboard()
            .row(Button.callback("تهران", "city:thr"), Button.callback("شیراز", "city:syz"))
            .row(Button.url("سایت", "https://example.com"))
            .row(Button.switch_inline("اشتراک‌گذاری…", "tehran")))

api.send_message(chat_id, "یک شهر انتخاب کن", reply_markup=keyboard)

@bot.on_callback("city:*")
def city(ctx):
    ctx.answer("انتخاب شد")                        # همیشه پاسخ بدهید تا دکمه از حالت انتظار دربیاید
    ctx.edit_message("شهر: " + ctx.callback_data)   # همان پیام را ویرایش می‌کند
```

<div dir="rtl">

`callback_data` حداکثر ۶۴ بایت است و هرگز به برنامه‌های کاربران فرستاده نمی‌شود؛ سرور می‌گوید کدام دکمه را چه کسی زده، پس می‌توانید به آن اعتماد کنید. به هر فشردن دکمه ظرف ۱۰ ثانیه پاسخ دهید. حداکثر ۲۵ ردیف، ۸ دکمه در هر ردیف و ۱۰۰ دکمه در کل. برای برداشتن دکمه‌ها: `api.edit_reply_markup(chat_id, seq, InlineKeyboard.none())`.

### صفحه‌کلید پاسخ (به‌جای صفحه‌کلید کاربر)

</div>

```python
from eleza_bot import ReplyKeyboard

api.send_message(chat_id, "بعد چه؟",
                 reply_markup=ReplyKeyboard().row("امروز", "این هفته").row("تنظیمات").resize().one_time())

api.send_message(chat_id, "بسته شد", reply_markup=ReplyKeyboard.remove())
```

<div dir="rtl">

فشردن هر دکمه متن آن را به‌عنوان پیام معمولی کاربر می‌فرستد.

## دستورها و پیوند شروع

</div>

```python
api.set_commands({"today": "هوای امروز", "help": "راهنما"})
```

<div dir="rtl">

پیوند `https://eleza.me/my_weather_bot?start=promo42` ربات را با دکمهٔ «شروع» باز می‌کند و `ctx.payload` در `on_start` مقدار `promo42` خواهد بود (حداکثر ۶۴ نویسه از `A-Za-z0-9_-`).

## حالت درون‌خطی

ابتدا در BotFather دستور `/setinline` را بفرستید. ظرف ۸ ثانیه پاسخ دهید:

</div>

```python
from eleza_bot import InlineResult

@bot.on_inline_query
def inline(ctx):
    ctx.answer_inline([
        InlineResult.article("thr", "تهران", "تهران: ۲۴ درجه، صاف").description("۲۴°، صاف"),
        InlineResult.article("syz", "شیراز", "شیراز: ۲۷ درجه").thumbnail("https://example.com/syz.png"),
    ], cache_time=60)
```

<div dir="rtl">

حداکثر ۵۰ نتیجه. نتیجهٔ انتخاب‌شده به‌عنوان پیام خود کاربر و با نشان «از طریق @ربات» فرستاده می‌شود. دکمه‌های نتیجه فقط می‌توانند پیوند یا switch-inline باشند. حالت درون‌خطی در گفت‌وگوهای ناشناس در دسترس نیست.

## انتشار الی

</div>

```python
post = api.create_post("نسخهٔ تازه منتشر شد #eleza")

api.create_post("زیرنویس", media=[
    {"id": api.upload_file(InputFile.from_path("a.jpg"), "image", "post"), "alt": "توضیح تصویر"},
])

api.create_post(poll={"question": "کدام؟", "options": ["الف", "ب"], "duration": "24h"})

api.delete_post(post["id"])
```

<div dir="rtl">

- فقط پست سطح‌اول: ربات نمی‌تواند پاسخ بدهد، نقل‌قول کند یا رشته بسازد.
- `limited: true` در پاسخ یعنی ربات نشان رسمی ندارد و پست فقط به دنبال‌کننده‌ها و پروفایل ربات می‌رسد.
- به‌روزرسانی‌های `post.reply_created`، `post.reaction_changed` و `follower.added` با `@bot.on(...)` دریافت می‌شوند. این‌ها راهی برای پیام‌دادن به آن افراد باز نمی‌کنند.

## خطاها

</div>

```python
from eleza_bot import ApiError, TransportError

try:
    api.send_message(chat_id, "سلام")
except ApiError as e:
    if e.cannot_write:
        ...  # کاربر ربات را شروع نکرده یا مسدود کرده است: او را از فهرست ارسال بردارید
    print(e.code, e.request_id)   # کد پایدار، مثل bot.user_not_started
except TransportError:
    ...  # شبکه: پاسخی دریافت نشد
```

<div dir="rtl">

| وضعیت | `code` | معنی |
|---|---|---|
| 401 | `bot.unauthorized` | توکن نادرست یا باطل‌شده |
| 403 | `bot.suspended`، `bot.switched_off`، `bot.disabled` | ربات تعلیق یا خاموش شده |
| 403 | `bot.scope_missing` | توکن مجوز این کار را ندارد |
| 403 | `bot.user_not_started`، `chat.blocked` | کاربر ربات را شروع نکرده / مسدود کرده |
| 404 | `chat.not_found` | این گفت‌وگو متعلق به ربات نیست |
| 400 | `bot.parse_error`، `bot.markup_invalid` | قالب‌بندی متن یا دکمه‌ها نادرست است |
| 409 | `bot.poll_conflict`، `bot.webhook_active` | polling دیگری در جریان است / وبهوک فعال است |
| 429 | `rate_limited` | محدودیت نرخ؛ `retry_after` ثانیه صبر کنید |

کتابخانه خودش 429، خطاهای 5xx و قطعی شبکه را (پیش‌فرض تا ۳ بار) دوباره امتحان می‌کند و به `retry_after` احترام می‌گذارد. ارسال پیام و پست همیشه با کلید تکرارناپذیری انجام می‌شود، پس تلاش دوباره پیام تکراری نمی‌سازد. برای ارسال انبوه، خودتان هم سرعت را نگه دارید: پیش‌فرض ۳۰ پیام در ثانیه برای هر ربات و ۶۰ پیام در دقیقه برای هر گفت‌وگو.

## تنظیمات

</div>

```python
api = Client(
    token,
    timeout=30,          # ثانیه برای هر درخواست
    max_retries=3,
    language="fa",       # زبان متن خطاها: fa یا en
    base_url="https://api.eleza.me",
)

bot = Bot(api)           # یا Bot(token, timeout=30, ...)
```

<div dir="rtl">

پراکسی از متغیر محیطی `HTTPS_PROXY` خوانده می‌شود. کتابخانه همگام (sync) است؛ در برنامهٔ asyncio فراخوانی‌ها را با `asyncio.to_thread` اجرا کنید. برای مسیری که هنوز در SDK متد ندارد: `api.request("GET", "/bot/v1/…")`.

## آزمون‌ها

</div>

```bash
python -m unittest discover -s . -p "test_*.py" -t .
```

<div dir="rtl">

## مجوز

MIT — پروندهٔ [LICENSE](LICENSE) را ببینید.

</div>
