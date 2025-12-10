import logging
import re
import asyncio
from utils import temp
from info import ADMINS
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()

SYD_UPDATE = -1003352207845


# Channel ID as an integer
INDEX_CHANNEL = [-1002498086501, -1003164435604, -1002901811032, -1003183027276, -1003137700522]
def get_file_name(message):
    if message.document:
        return message.document.file_name

    elif message.video:
        return message.video.file_name

    elif message.audio:
        return message.audio.file_name

    elif message.voice:
        return "voice_message.ogg"

    elif message.photo:
        return "photo.jpg"

    return None

@Client.on_message(filters.document | filters.audio | filters.video)
async def auto(bot, message):
    # Check if the message is from the specified channel
    if message.chat.id in INDEX_CHANNEL:
        # Log the received media for tracking purposes
        logger.info(f"Received {message.media.value} from {message.chat.title or message.chat.id}")

        # Check if the media attribute exists
        if message.media:
            # Extract the media type
            media_type = message.media.value
            media = getattr(message, media_type, None)

            if media:
                media.file_type = media_type
                media.caption = message.caption
                # Save the media file
                try:
                    aynav, vnay = await save_file(media)
                    
                    if aynav:
                        await new_file(bot, get_file_name(message))
                        logger.info("File successfully indexed and saved.")
                    elif vnay == 0:
                        logger.info("Duplicate file was skipped.")
                    elif vnay == 2:
                        logger.error("Error(index) occurred")
                    
                except Exception as e:
                    logger.exception("Failed to save file: %s", e)
                    await message.reply(f"An error occurred while processing the file: {e}")
            else:
                logger.warning("No media found in the message.")
        else:
            logger.warning("Message does not contain media.")
            
async def new_file(client, file_name: str):

    clean = file_name.replace(".", " ").replace("_", " ").strip()

    # ---------------- ✅ LANGUAGE ----------------
    langs = ["hindi", "english", "tamil", "telugu", "malayalam", "kannada"]
    language = "Unknown"
    for l in langs:
        if re.search(rf"\b{l}\b", clean, re.I):
            language = l.title()
            break

    # ---------------- ✅ SERIES DETECT ----------------
    s_match = re.search(
        r"(?P<name>.*?)(S(?P<season>\d{1,2})E(?P<ep>\d{1,2}))",
        clean,
        re.I
    )

    if s_match:
        name = s_match.group("name").strip()
        season = s_match.group("season").zfill(2)
        ep = int(s_match.group("ep"))

        key = f"{name}_S{season}"

        prev = await db.get(key)

        # ✅ FIRST EPISODE → NEW MESSAGE (WITH E01 IN BUTTON)
        if not prev:
            search_key = f"{name} S{season}E{str(ep).zfill(2)}".replace(" ", "_")

            button = InlineKeyboardMarkup(
                [[InlineKeyboardButton(
                    "🔎 Search",
                    url=f"https://t.me/{temp.U_NAME}?start=search_{search_key}"
                )]]
            )

            txt = (
                f"{name}\n"
                f"S{season}E{str(ep).zfill(2)}\n"
                f"🌐 {language}"
            )

            m = await client.send_message(SYD_UPDATE, txt, reply_markup=button)

            await update_db.save({
                "key": key,
                "name": name,
                "season": season,
                "start_ep": ep,
                "last_ep": ep,
                "msg_id": m.id
            })
            return

        # ✅ NEXT EPISODES → EDIT MESSAGE (FORMAT CHANGE + REMOVE E01 FROM BUTTON)
        start = prev["start_ep"]
        old_last = prev["last_ep"]

        if ep > old_last:
            # ✅ Button now only to SEASON (not E01)
            search_key = f"{name} S{season}".replace(" ", "_")

            button = InlineKeyboardMarkup(
                [[InlineKeyboardButton(
                    "🔎 Search",
                    url=f"https://t.me/{temp.U_NAME}?start=search_{search_key}"
                )]]
            )

            # ✅ NEW FORMAT YOU ASKED:
            # Vikings S01
            # E01-E03
            new_txt = (
                f"{name} S{season}\n"
                f"E{str(start).zfill(2)}-E{str(ep).zfill(2)}\n"
                f"🌐 {language}"
            )

            await client.edit_message_text(
                SYD_UPDATE,
                prev["msg_id"],
                new_txt,
                reply_markup=button
            )

            await db.update(key, {"last_ep": ep})
            return

        return  # ✅ Duplicate episode ignored

    # ---------------- ✅ MOVIE DETECT ----------------
    m_match = re.search(r"(?P<title>.*?)(19\d{2}|20\d{2})", clean)

    if m_match:
        movie_name = m_match.group(0).strip()
        key = movie_name.lower()

        # ✅ Skip if already sent
        if await db.get(key):
            return

        search_key = movie_name.replace(" ", "_")

        button = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                "🔎 Search",
                url=f"https://t.me/{temp.U_NAME}?start=search_{search_key}"
            )]]
        )

        txt = (
            f"{movie_name}\n"
            f"🌐 {language}"
        )

        await client.send_message(SYD_UPDATE, txt, reply_markup=button)

        await db.save({
            "key": key,
            "type": "movie",
            "name": movie_name
        })
