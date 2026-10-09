"""Publishes on Eli as the bot and listens to what people do with the post.

    python examples/06_eli_post.py "متن پست" [image.jpg]
"""

import sys

from _common import token

from eleza_bot import Bot, InputFile, UpdateType

text = sys.argv[1] if len(sys.argv) > 1 else "سلام الی! #eleza"
image = sys.argv[2] if len(sys.argv) > 2 else None

bot = Bot(token())

media = None
if image:
    # Media of a post is uploaded with purpose "post".
    media = [{"id": bot.api.upload_file(InputFile.from_path(image), "image", "post"), "alt": text}]
created = bot.api.create_post(text, media=media)
print(f"published post {created['id']}" + (" (followers and profile only: the bot is not official)" if created.get("limited") else ""))


@bot.on(UpdateType.POST_REPLY_CREATED)
def replied(ctx):
    print(f"{ctx.sender_name or ctx.sender_id} replied: {(ctx.update.reply or {}).get('text', '')}")


@bot.on(UpdateType.POST_REACTION_CHANGED)
def reacted(ctx):
    print(f"reaction on {ctx.update.post_id}: {ctx.update.previous_reaction} → {ctx.update.reaction}")


@bot.on(UpdateType.FOLLOWER_ADDED)
def followed(ctx):
    print(f"new follower: {ctx.sender_name or ctx.sender_id}")


print("Listening for replies, reactions and followers — Ctrl+C to stop")
bot.run()
