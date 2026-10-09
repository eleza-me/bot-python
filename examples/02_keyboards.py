"""Inline buttons with callbacks, editing the message in place, and a reply keyboard."""

from _common import token

from eleza_bot import Bot, Button, InlineKeyboard, ReplyKeyboard, Text

CITIES = {"thr": "تهران", "syz": "شیراز", "tbz": "تبریز", "mhd": "مشهد"}

bot = Bot(token())


def city_keyboard() -> InlineKeyboard:
    buttons = [Button.callback(name, f"city:{code}") for code, name in CITIES.items()]
    return InlineKeyboard().grid(buttons, per_row=2).row(Button.url("سایت الزا", "https://eleza.me"))


@bot.on_start
def start(ctx):
    ctx.reply("یک شهر انتخاب کن:", reply_markup=city_keyboard())


@bot.on_callback("city:*")  # callback_data is "city:<code>"
def city(ctx):
    name = CITIES.get(ctx.callback_data[len("city:"):])
    if name is None:
        ctx.answer("این شهر را نمی‌شناسم", alert=True)
        return
    ctx.answer(f"{name} انتخاب شد")
    ctx.edit_message(
        Text("شهر شما: ").bold(name),
        reply_markup=InlineKeyboard().row(Button.callback("تغییر", "change")),
    )


@bot.on_callback("change")
def change(ctx):
    ctx.answer()
    ctx.edit_message("یک شهر انتخاب کن:", reply_markup=city_keyboard())


# A reply keyboard: its buttons send their text as ordinary messages.
@bot.on_command("menu")
def menu(ctx):
    keyboard = ReplyKeyboard().row("امروز", "این هفته").row("بستن منو").resize().placeholder("یکی را انتخاب کن")
    ctx.reply("چه کاری انجام دهم؟", reply_markup=keyboard)


@bot.on_text(pattern=r"^بستن منو$")
def close_menu(ctx):
    ctx.reply("منو بسته شد.", reply_markup=ReplyKeyboard.remove())


@bot.on_text
def choice(ctx):
    ctx.reply("انتخاب شما: " + ctx.text)


bot.run()
