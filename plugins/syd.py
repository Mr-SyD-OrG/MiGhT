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

syyydtg_map = {
    'Eng': 'English', 'English': 'English',
    'Hin': 'Hindi', 'Hindi': 'Hindi',
    'Tam': 'Tamil', 'Tamil': 'Tamil',
    'Tel': 'Telugu', 'Telugu': 'Telugu',
    'Kan': 'Kannada', 'Kannada': 'Kannada',
    'Mal': 'Malayalam', 'Malayalam': 'Malayalam',
    'Mar': 'Marathi', 'Marathi': 'Marathi',
    'Ben': 'Bengali', 'Bengali': 'Bengali',
    'Ind': 'Indonesian', 'Indonesian': 'Indonesian',
    'Pun': 'Punjabi', 'Punjabi': 'Punjabi',
    'Urd': 'Urdu', 'Urdu': 'Urdu',
    'Guj': 'Gujarati', 'Gujarati': 'Gujarati',
    'Bhoj': 'Bhojpuri', 'Bhojpuri': 'Bhojpuri',
    'Ori': 'Odia', 'Odia': 'Odia',
    'Ass': 'Assamese', 'Assamese': 'Assamese',
    'San': 'Sanskrit', 'Sanskrit': 'Sanskrit',
    'Sin': 'Sinhala', 'Sinhala': 'Sinhala',
    'Ara': 'Arabic', 'Arabic': 'Arabic',
    'Fre': 'French', 'French': 'French',
    'Spa': 'Spanish', 'Spanish': 'Spanish',
    'Por': 'Portuguese', 'Portuguese': 'Portuguese',
    'Ger': 'German', 'German': 'German',
    'Rus': 'Russian', 'Russian': 'Russian',
    'Jap': 'Japanese', 'Japanese': 'Japanese',
    'Jpn': 'Japanese',
    'Kor': 'Korean', 'Korean': 'Korean',
    'Ita': 'Italian', 'Italian': 'Italian',
    'Chi': 'Chinese', 'Chinese': 'Chinese',
    'Man': 'Mandarin', 'Mandarin': 'Mandarin',
    'Tha': 'Thai', 'Thai': 'Thai',
    'Vie': 'Vietnamese', 'Vietnamese': 'Vietnamese',
    'Fil': 'Filipino', 'Filipino': 'Filipino',
    'Tur': 'Turkish', 'Turkish': 'Turkish',
    'Swe': 'Swedish', 'Swedish': 'Swedish',
    'Nor': 'Norwegian', 'Norwegian': 'Norwegian',
    'Dan': 'Danish', 'Danish': 'Danish',
    'Pol': 'Polish', 'Polish': 'Polish',
    'Gre': 'Greek', 'Greek': 'Greek',
    'Heb': 'Hebrew', 'Hebrew': 'Hebrew',
    'Cze': 'Czech', 'Czech': 'Czech',
    'Hun': 'Hungarian', 'Hungarian': 'Hungarian',
    'Fin': 'Finnish', 'Finnish': 'Finnish',
    'Ned': 'Dutch', 'Dutch': 'Dutch',
    'Rom': 'Romanian', 'Romanian': 'Romanian',
    'Bul': 'Bulgarian', 'Bulgarian': 'Bulgarian',
    'Ukr': 'Ukrainian', 'Ukrainian': 'Ukrainian',
    'Cro': 'Croatian', 'Croatian': 'Croatian',
    'Slv': 'Slovenian', 'Slovenian': 'Slovenian',
    'Ser': 'Serbian', 'Serbian': 'Serbian',
    'Afr': 'Afrikaans', 'Afrikaans': 'Afrikaans',
    'Lat': 'Latin', 'Latin': 'Latin'
}

def detect_language(text: str):
    found = []

    for short, full in syyydtg_map.items():
        if re.search(rf"\b{re.escape(short)}\b", text, re.I):
            if full not in found:   # ✅ avoid duplicates (e.g. Jap + Jpn)
                found.append(full)

    return found if found else ["Unknown"]

def clean_title(text: str):
    # remove brackets
    text = re.sub(r"\[.*?\]|\(.*?\)", "", text)

    # remove quality, platform, codec
    text = re.sub(
        r"\b(720p|1080p|2160p|4k|nf|web|webrip|bluray|hdr|x264|x265|hevc|aac)\b",
        "",
        text,
        flags=re.I
    )

    # remove release groups & tags
    text = re.sub(
        r"\b(erai-raws|subsplease|horriblesubs|yts|rarbg|syd)\b",
        "",
        text,
        flags=re.I
    )

    # remove trailing junk like "-" "_"
    text = re.sub(r"[-_]+$", "", text)

    # collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip()

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
            
import time

async def new_file(client, file_name: str):
    clean = file_name.replace(".", " ").replace("_", " ").strip()
    langs = detect_language(clean)   
    language = ", ".join(langs)

    # ---------------- ✅ SERIES DETECT ----------------
    s_match = re.search(
        r"(?P<name>.*?)(S(?P<season>\d{1,2})E(?P<ep>\d{1,2}))",
        clean,
        re.I
    )

    if s_match:
        raw_name = s_match.group("name").replace("-", " ")
        name = clean_title(raw_name)
        season = s_match.group("season").zfill(2)
        ep = int(s_match.group("ep"))

        # ✅ CLEAN KEY (NO DASH)
        key = f"{name.lower().replace('-', '')}_s{season}"

        prev = await db.get(key)

        now = int(time.time())

        # ✅ FIRST EPISODE OR FORCED RESEND (LANGUAGE CHANGE)
        if (
            not prev or
            prev.get("language") != language
        ):
            search_key = f"{name} S{season}E{str(ep).zfill(2)}"
            search_key = search_key.replace(" ", "_").replace("-", "")

            button = InlineKeyboardMarkup(
                [[InlineKeyboardButton(
                    "🔎 Search",
                    url=f"https://t.me/{temp.U_NAME}?start=search-{search_key}"
                )]]
            )

            txt = (
                f"{name.translate(str.maketrans({'a':'ᴀ','b':'ʙ','e':'ꫀ','s':'ꜱ','x':'x'}))}\n"
                f"S{season}E{str(ep).zfill(2)}\n"
                f"<blockquote>🔊 {language}</blockquote>"
            )

            m = await client.send_message(SYD_UPDATE, txt, reply_markup=button)

            await db.save({
                "key": key,
                "name": name,
                "season": season,
                "start_ep": ep,
                "last_ep": ep,
                "msg_id": m.id,
                "language": language,
                "created_at": now
            })
            return

        start = prev["start_ep"]
        old_last = prev["last_ep"]
        created_at = prev.get("created_at", now)
        if ep < start:
            new_start = ep
            search_key = f"{name} S{season}".replace(" ", "_")
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🔎 Search", url=f"https://t.me/{temp.U_NAME}?start=search-{search_key}")]])
            new_txt = f"{name} S{season}\nE{new_start:02d}-E{old_last:02d}\n<blockquote>🔊 {language}</blockquote>"

            try:
                await client.edit_message_text(SYD_UPDATE, prev["msg_id"], new_txt, reply_markup=btn)
                await db.update(key, {"start_ep": new_start})
            except:
                m = await client.send_message(SYD_UPDATE, new_txt, reply_markup=btn)
                await db.update(key, {"msg_id": m.id, "start_ep": new_start})
                return
        if ep > old_last:
            can_edit = (now - created_at) < 86400
            search_key = f"{name} S{season}".replace(" ", "_").replace("-", "")
            button = InlineKeyboardMarkup(
                [[InlineKeyboardButton(
                    "🔎 Search",
                    url=f"https://t.me/{temp.U_NAME}?start=search-{search_key}"
                )]]
            )
            new_txt = (
                f"{name} S{season}\n"
                f"E{str(start).zfill(2)}-E{str(ep).zfill(2)}\n"
                f"<blockquote>🔊 {language}</blockquote>"
            )
            if can_edit:
                await client.edit_message_text(
                    SYD_UPDATE,
                    prev["msg_id"],
                    new_txt,
                    reply_markup=button
                )
            else:
                m = await client.send_message(SYD_UPDATE, new_txt, reply_markup=button)
                prev["msg_id"] = m.id
                prev["created_at"] = now

            await db.update(key, {
                "last_ep": ep,
                "msg_id": prev["msg_id"],
                "created_at": prev["created_at"],
                "language": language
            })
            return

        return  

    m_match = re.search(r"(?P<title>.*?)(19\d{2}|20\d{2})", clean)
    if m_match:
        raw_movie = m_match.group(0).replace("-", " ")
        movie_name = clean_title(raw_movie)
        key = movie_name.lower().replace("-", "")
        prev = await db.get(key)
        # ✅ RESEND IF LANGUAGE CHANGED
        if prev and prev.get("language") == language:
            return
        search_key = movie_name.replace(" ", "_").replace("-", "")
        button = InlineKeyboardMarkup(
            [[InlineKeyboardButton(
                "🔎 Search",
                url=f"https://t.me/{temp.U_NAME}?start=search-{search_key}"
            )]]
        )
        txt = (
            f"{movie_name.translate(str.maketrans({'a':'ᴀ','b':'ʙ','e':'ꫀ','s':'ꜱ','x':'x'}))}\n"
            f"<blockquote>🔊 {language}</blockquote>"
        )
        await client.send_message(SYD_UPDATE, txt, reply_markup=button)
        await db.save({
            "key": key,
            "type": "movie",
            "name": movie_name,
            "language": language,
            "created_at": int(time.time())
        })


@Client.on_message(filters.command("clear_updates") & filters.user(ADMINS))
async def clear_updates_cmd(client, message):
    try:
        result = await db.updates.delete_many({})
        await message.reply_text(
            f"✅ All update data cleared!\n\n"
            f"🗑 Deleted records: `{result.deleted_count}`"
        )
    except Exception as e:
        await message.reply_text(f"❌ Failed to clear data:\n`{e}`")
