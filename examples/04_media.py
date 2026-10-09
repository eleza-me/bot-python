"""Sends a photo and a document to a chat.

    python examples/04_media.py <chat id> photo.jpg report.pdf

The chat id comes from an update (ctx.chat_id): a bot can write only to
people who started it.
"""

import os
import sys

from _common import token

from eleza_bot import ApiError, ChatAction, Client, InputFile

if len(sys.argv) < 3:
    sys.exit("usage: python 04_media.py <chat id> <photo> [document]")
chat_id, photo = sys.argv[1], sys.argv[2]
document = sys.argv[3] if len(sys.argv) > 3 else None

api = Client(token())

try:
    api.send_chat_action(chat_id, ChatAction.UPLOADING_PHOTO)

    # Upload and send in one call…
    sent = api.send_photo(chat_id, InputFile.from_path(photo), text="یک عکس")
    print(f"photo sent as message #{sent['seq']}")

    if document:
        # …or upload once and reuse the media id for many chats.
        media_id = api.upload_file(InputFile.from_path(document), "file")
        sent = api.send_file(chat_id, media_id, text=os.path.basename(document))
        print(f"document sent as message #{sent['seq']} (media {media_id})")
except ApiError as e:
    if e.cannot_write:
        sys.exit("This person has not started the bot, or has blocked it.")
    raise
