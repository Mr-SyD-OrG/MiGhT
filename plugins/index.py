import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import ADMINS
from info import INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp
import re
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()


@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        return await query.answer("Cᴀɴᴄᴇʟʟɪɴɢ Iɴᴅᴇxɪɴɢ")
    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'Yᴏᴜʀ Suʙᴍɪꜱꜱɪᴏɴ Fᴏʀ Iɴᴅᴇxɪɴɢ {chat} Hᴀꜱ Bᴇᴇɴ Dᴇᴄʟɪɴᴇᴅ Bʏ Oᴜʀ Mᴏᴅᴇʀᴀᴛᴏʀꜱ.',
                               reply_to_message_id=int(lst_msg_id))
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Pʀᴏᴄᴇꜱꜱɪɴɢ...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
                               reply_to_message_id=int(lst_msg_id))
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


@Client.on_message((filters.forwarded | (filters.regex("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text ) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    if message.text:
        regex = re.compile("(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('Invalid link')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    elif message.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await message.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await message.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and iam not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [
            [
                InlineKeyboardButton('Yes',
                                     callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
            ],
            [
                InlineKeyboardButton('close', callback_data='close_data'),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>',
            reply_markup=reply_markup)

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure iam an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [
        [
            InlineKeyboardButton('Accept Index',
                                 callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],
        [
            InlineKeyboardButton('Reject Index',
                                 callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(LOG_CHANNEL,
                           f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
                           reply_markup=reply_markup)
    await message.reply('ThankYou For the Contribution, Wait For My Moderators to verify the files.')


@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
        except:
            return await message.reply("Skip number should be an integer.")
        await message.reply(f"Successfully set SKIP number as {skip}")
        temp.CURRENT = int(skip)
    else:
        await message.reply("Give me a skip number")

import asyncio
from typing import Any

# ---------- Worker / Queue helpers ----------
# Number of parallel DB writers
WORKER_COUNT = 15

async def _save_worker(worker_id: int, queue: asyncio.Queue, result_queue: asyncio.Queue):
    """
    Worker: takes (media,) items from queue, calls save_file(media),
    and pushes (aynav, vnay) result into result_queue.
    Exits when it receives None sentinel.
    """
    while True:
        item = await queue.get()
        if item is None:  # sentinel to stop worker
            queue.task_done()
            break
        media = item
        try:
            # Call the existing save_file function (unchanged)
            aynav, vnay = await save_file(media)
        except Exception as e:
            # If save_file crashes, translate to error tuple
            logger.exception(f"Worker {worker_id} save_file crashed: {e}")
            aynav, vnay = False, 2
        # Push the result so main loop can update counters and progress
        await result_queue.put((aynav, vnay))
        queue.task_done()
    # optionally push exit marker for result queue, but main will know when all tasks done
    return

# ---------- Updated index function ----------
async def index_files_to_db(lst_msg_id, chat, msg, bot):
    """
    This version keeps all pre-checks and media extraction as before,
    but enqueues 'media' objects to a queue which 15 workers consume and
    call save_file(media) in parallel.

    Progress:
      - queued_count: queue.qsize() shows waiting items
      - total_files: incremented when worker reports saved
    """
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0

    # Local queue and result queue
    queue: asyncio.Queue[Any] = asyncio.Queue()
    result_queue: asyncio.Queue[tuple] = asyncio.Queue()

    # Start workers
    workers = [asyncio.create_task(_save_worker(i, queue, result_queue)) for i in range(WORKER_COUNT)]

    # A task to consume results from result_queue and update counters
    async def result_consumer():
        nonlocal total_files, duplicate, errors
        while True:
            res = await result_queue.get()
            if res is None:
                result_queue.task_done()
                break
            aynav, vnay = res
            # Use the semantics you provided:
            # aynav: True/False (file saved flag)
            # vnay == 0 : saved
            # vnay == 1 : already saved (duplicate)
            # vnay == 2 : error
            try:
                if vnay == 0:
                    total_files += 1
                elif vnay == 1:
                    duplicate += 1
                elif vnay == 2:
                    errors += 1
            except Exception:
                logger.exception("Error updating counters from worker result")
            result_queue.task_done()

    consumer_task = asyncio.create_task(result_consumer())

    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False

            # We'll also refresh the status message periodically
            last_progress_edit = 0

            async for message in bot.iter_messages(chat, lst_msg_id, temp.CURRENT):
                if temp.CANCEL:
                    # stop producing more items
                    break

                current += 1

                # Regular UI update (every 500 messages as before)
                if current % 500 == 0:
                    can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                    reply = InlineKeyboardMarkup(can)
                    # Show both queued and saved counts
                    queued_count = queue.qsize()
                    await msg.edit_text(
                        text=(
                            f"Total messages fetched: <code>{current}</code>\n"
                            f"Queued for DB save: <code>{queued_count}</code>\n"
                            f"Total messages saved (real): <code>{total_files}</code>\n"
                            f"Duplicate Files Skipped: <code>{duplicate}</code>\n"
                            f"Deleted Messages Skipped: <code>{deleted}</code>\n"
                            f"Non-Media messages skipped: <code>{no_media + unsupported}</code>"
                            f"(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>"
                        ),
                        reply_markup=reply
                    )
                    last_progress_edit = current

                # exact same pre-checks as your original code
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                    unsupported += 1
                    continue

                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue

                # keep the same fields / transformations BEFORE enqueuing
                media.file_type = message.media.value
                media.caption = message.caption

                # ENQUEUE only the DB-write (save_file). All other work done.
                await queue.put(media)

            # Producer loop finished (either finished iteration or cancelled)
            # Wait until queue is fully processed by workers

            # send sentinel None per worker to stop them after queue drained
            await queue.join()   # wait until all queued items are processed

            # stop workers by sending None sentinel for each worker
            for _ in workers:
                await queue.put(None)

            # Wait for workers to exit
            await asyncio.gather(*workers, return_exceptions=True)

            # Now all workers done. Tell result consumer to stop:
            await result_queue.put(None)
            await result_queue.join()
            await consumer_task

        except Exception as e:
            logger.exception(e)
            await msg.edit(f'Error: {e}')
        else:
            # Final progress edit: include queued (should be 0) and final saved counts
            await msg.edit(
                f'Succesfully saved <code>{total_files}</code> to dataBase!\n'
                f'Duplicate Files Skipped: <code>{duplicate}</code>\n'
                f'Deleted Messages Skipped: <code>{deleted}</code>\n'
                f'Non-Media messages skipped: <code>{no_media + unsupported}</code>'
                f'(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>'
            )
            

async def index_fil_to_db(lst_msg_id, chat, msg, bot):
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    async with lock:
        try:
            current = temp.CURRENT
            temp.CANCEL = False
            async for message in bot.iter_messages(chat, lst_msg_id, temp.CURRENT):
                if temp.CANCEL:
                    await msg.edit(f"Successfully Cancelled!!\n\nSaved <code>{total_files}</code> files to dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>")
                    break
                current += 1
                if current % 500 == 0:
                    can = [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
                    reply = InlineKeyboardMarkup(can)
                    await msg.edit_text(
                        text=f"Total messages fetched: <code>{current}</code>\nTotal messages saved: <code>{total_files}</code>\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>",
                        reply_markup=reply)
                if message.empty:
                    deleted += 1
                    continue
                elif not message.media:
                    no_media += 1
                    continue
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                    unsupported += 1
                    continue
                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    continue
                media.file_type = message.media.value
                media.caption = message.caption
                aynav, vnay = await save_file(media)
                if aynav:
                    total_files += 1
                elif vnay == 0:
                    duplicate += 1
                elif vnay == 2:
                    errors += 1
        except Exception as e:
            logger.exception(e)
            await msg.edit(f'Error: {e}')
        else:
            await msg.edit(f'Succesfully saved <code>{total_files}</code> to dataBase!\nDuplicate Files Skipped: <code>{duplicate}</code>\nDeleted Messages Skipped: <code>{deleted}</code>\nNon-Media messages skipped: <code>{no_media + unsupported}</code>(Unsupported Media - `{unsupported}` )\nErrors Occurred: <code>{errors}</code>')
