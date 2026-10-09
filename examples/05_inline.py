"""Inline mode: people type "@your_bot something" in any chat and pick a result.
Turn it on first: /setinline in @BotFather.
"""

from urllib.parse import quote

from _common import token

from eleza_bot import Bot, Button, InlineKeyboard, InlineResult, Text

bot = Bot(token())


@bot.on_inline_query
def search(ctx):
    query = ctx.query.strip()
    if not query:
        ctx.answer_inline([])
        return
    url = "https://www.google.com/search?q=" + quote(query)
    ctx.answer_inline([
        InlineResult.article("upper", "حروف بزرگ", query.upper()).description(query.upper()),
        InlineResult.article("bold", "پررنگ", Text().bold(query)).description("متن را پررنگ می‌فرستد"),
        InlineResult.article("search", "جست‌وجو", Text("جست‌وجو برای ").link(query, url))
        .keyboard(InlineKeyboard().row(Button.url("باز کردن", url))),
    ], cache_time=60)


@bot.on_start
def start(ctx):
    ctx.reply("در هر گفت‌وگویی نام من را با @ بنویس و بعدش یک متن.")


bot.run(allowed_updates=["inline_query", "user.started_bot"])
