"""The smallest bot: greets on Start and repeats what it is told. Long polling."""

from _common import token

from eleza_bot import Bot

bot = Bot(token())

me = bot.api.get_me()
print(f"Running as @{me['handle']} — press Ctrl+C to stop")

bot.api.set_commands({"start": "شروع", "help": "راهنما"})


@bot.on_start
def start(ctx):
    name = ctx.sender_name or "دوست من"
    ctx.reply(f"سلام {name}! هر چه بنویسی برایت تکرار می‌کنم.")


@bot.on_command("help")
def help_(ctx):
    ctx.reply("یک پیام متنی بفرست.")


@bot.on_text
def echo(ctx):
    ctx.reply_quoting(ctx.text)


@bot.on_message
def other(ctx):
    ctx.reply("فعلاً فقط متن را می‌فهمم.")


bot.run()
