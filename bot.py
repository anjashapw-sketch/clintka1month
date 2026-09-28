import json, requests, os, io
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# ==================== CONFIG ====================
BOT_TOKEN = "8880254603:AAGnk60QtbC6A85Xp26CkEqBr18fnIERHrQ"

# ---- Admins (2 admins) ----
ADMINS = [
    6727548057,        # Admin 1
    8027403165,        # <-- Admin 2 ki ID yahan daalo
]

DEFAULT_CREDITS = 500
USERS_FILE = "users.json"
COPYRIGHT = "\n\n| All Rights Reserved"
TZ_OFFSET_MIN = 330

# ---- Force Join: Multiple Channels (2 channels) ----
REQUIRED_CHANNELS = [
    {
        "id": -1004293285899,
        "link": "https://t.me/unkahi_lafzein",
        "name": "Channel 1"
    },
    {
        "id": -1001767836898,                        # <-- 2nd channel ID
        "link": "https://t.me/+j314LcJCJto3Nzk1",       # <-- 2nd channel link
        "name": "Channel 2"
    },
]

# ---- Force Join: Required Group ----
REQUIRED_GROUP = -1002398770559
GROUP_LINK = "https://t.me/PWXTOPPER"

# ---- Phone NUM API ----
NUM_API_URL = "https://reuters-memorabilia-insulin-disclose.trycloudflare.com/num"
NUM_API_KEY = "DADDY"

# ==================== TIME HELPER (IST) ====================
def now_ist_str():
    ist_time = datetime.now(timezone.utc) + timedelta(minutes=TZ_OFFSET_MIN)
    return ist_time.strftime("%Y-%m-%d %H:%M:%S IST")

# ==================== SAFE USER STORAGE ====================
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_users():
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(USERS, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save users.json: {e}")

USERS = load_users()

def ensure_user(chat_id):
    sid = str(chat_id)
    if sid not in USERS:
        USERS[sid] = {
            "credits": DEFAULT_CREDITS,
            "joined_at": now_ist_str(),
            "last_used_at": None,
            "searches": 0
        }
        save_users()
    return USERS[sid]

def consume_credit(chat_id):
    """Deduct 1 credit + bump usage in a single save."""
    u = ensure_user(chat_id)
    u["credits"] = max(0, u["credits"] - 1)
    u["searches"] += 1
    u["last_used_at"] = now_ist_str()
    save_users()

# ==================== FORCE JOIN CHECKER ====================
async def check_joined_status(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        # Check all channels
        for ch in REQUIRED_CHANNELS:
            ch_member = await context.bot.get_chat_member(chat_id=int(ch["id"]), user_id=user_id)
            if ch_member.status in ['left', 'kicked']:
                return False

        # Check group
        grp_member = await context.bot.get_chat_member(chat_id=int(REQUIRED_GROUP), user_id=user_id)
        if grp_member.status in ['left', 'kicked']:
            return False

        return True
    except Exception as e:
        print(f"[CRITICAL] Force-join check failed for {user_id}: {e}")
        return False

async def send_join_prompt(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    keyboard = []
    for i, ch in enumerate(REQUIRED_CHANNELS, 1):
        keyboard.append([InlineKeyboardButton(f"📢 Join {ch.get('name', f'Channel {i}')}", url=ch["link"])])
    keyboard.append([InlineKeyboardButton("💬 Join Group", url=GROUP_LINK)])
    keyboard.append([InlineKeyboardButton("✅ Verify", callback_data="check_join")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = (
        f"⚠️ **Pehle saare Channels aur Group join karo, phir Verify dabao.**\n\n"
        f"Bot use karne ke liye humare channels aur group ko join karna zaroori hai.{COPYRIGHT}"
    )
    await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup, parse_mode="Markdown")

# ==================== VERIFY CALLBACK ====================
async def verify_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.from_user.id

    joined = await check_joined_status(context, chat_id)

    if joined:
        await query.answer("✅ Verification Successful!", show_alert=True)
        try:
            await query.message.edit_text(
                "✅ Verification successful! Ab aap `/start` dabakar bot commands use kar sakte hain."
            )
        except Exception:
            pass
    else:
        await query.answer("❌ Aapne abhi tak saare Channels aur Group join nahi kiye hain!", show_alert=True)

# ==================== START COMMAND ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in ADMINS:
        if not await check_joined_status(context, chat_id):
            await send_join_prompt(context, chat_id)
            return

    u = ensure_user(chat_id)

    if chat_id in ADMINS:
        total_users = len(USERS)
        total_credits = sum([int(x.get("credits", 0)) for x in USERS.values()])
        admin_info = f"""👑 Admin Panel

📊 Total Users: {total_users}
💰 Total Credits: {total_credits}

⚙️ Commands:
📱 /num <number>
🆔 /aadhar <number>
💸 /gst <number>
💳 /addcredits <user_id> <amount>
💳 /subcredits <user_id> <amount>
👥 /users
📂 /exportusers
📂 /exportjson
📢 /broadcast <message>
{COPYRIGHT}"""
        await context.bot.send_message(chat_id=chat_id, text=admin_info)
    else:
        user_info = f"""👋 Welcome to OSINT Bot

💳 Balance: {u['credits']} credits
🗓️ Joined: {u['joined_at']}
🔎 Searches: {u['searches']}

Commands:
📱 /num <number>
🆔 /aadhar <number>
💸 /gst <number>
💳 /balance
🆔 /myid
{COPYRIGHT}"""
        await context.bot.send_message(chat_id=chat_id, text=user_info)

# ==================== NUM COMMAND (New API) ====================
async def num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in ADMINS:
        if not await check_joined_status(context, chat_id):
            await send_join_prompt(context, chat_id)
            return

    u = ensure_user(chat_id)

    if not context.args:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Usage: /num <number>{COPYRIGHT}")
        return

    if chat_id not in ADMINS and u["credits"] <= 0:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Not enough credits.{COPYRIGHT}")
        return

    number = context.args[0].strip()
    await context.bot.send_message(chat_id=chat_id, text=f"🔍 Searching Phone Number...\n\n📱 Number: {number}{COPYRIGHT}")

    url = f"{NUM_API_URL}?number={number}&key={NUM_API_KEY}"

    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ API Error\n\nStatus Code: {response.status_code}{COPYRIGHT}"
            )
            return

        api_data = response.json()

        # ---- API success check ----
        if not api_data.get("success"):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ API Error\n\n{api_data.get('credit', 'Unknown error')}{COPYRIGHT}"
            )
            return

        if not api_data.get("found"):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ No records found for {number}{COPYRIGHT}"
            )
            if chat_id not in ADMINS:
                consume_credit(chat_id)
            return

        records = api_data.get("result", [])
        res_text = f"✅ Phone Lookup Results\n\n"
        res_text += f"📱 Phone: {number}\n"
        res_text += f"⏰ Time: {now_ist_str()}\n"
        res_text += f"📊 Total Records: {len(records)}\n"
        res_text += f"💳 Credits Used: 1\n\n"

        key_map = {
            "name": "👤 Name",
            "mobile": "📞 Mobile",
            "alt_mobile": "📱 Alt Mobile",
            "father_name": "👨‍👦 Father",
            "address": "🏠 Address",
            "circle": "📡 Circle",
            "email": "📧 Email",
            "aadhaar": "🆔 Aadhaar",   # redact karenge
        }

        for idx, item in enumerate(records, 1):
            res_text += f"━ Record {idx} ━\n"
            if isinstance(item, dict):
                for k, v in item.items():
                    if v is None or str(v).strip() == "":
                        continue
                    k_lower = str(k).lower()
                    if k_lower in key_map:
                        label = key_map[k_lower]
                        if k_lower == "aadhaar":
                            res_text += f"{label}: [Aadhaar Redacted]\n"
                        else:
                            res_text += f"{label}: {v}\n"
                    else:
                        res_text += f"🔹 {str(k).capitalize()}: {v}\n"
            else:
                res_text += f"🔹 Data: {item}\n"
            res_text += "\n"

        res_text += COPYRIGHT
        if chat_id not in ADMINS:
            consume_credit(chat_id)

        # Telegram message limit 4096 — cut if needed
        if len(res_text) > 4000:
            res_text = res_text[:3950] + f"\n\n... (truncated){COPYRIGHT}"

        await context.bot.send_message(chat_id=chat_id, text=res_text.strip())

    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Phone Lookup Failed\n\nError: {str(e)}{COPYRIGHT}"
        )

# ==================== AADHAR COMMAND ====================
async def aadhar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in ADMINS and not await check_joined_status(context, chat_id):
        await send_join_prompt(context, chat_id)
        return

    u = ensure_user(chat_id)

    if not context.args:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Usage: /aadhar <query>{COPYRIGHT}")
        return

    if chat_id not in ADMINS and u["credits"] <= 0:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Not enough credits.{COPYRIGHT}")
        return

    query_val = context.args[0]
    await context.bot.send_message(chat_id=chat_id, text=f"🔍 Searching Aadhar Database...\n\n🆔 Query: {query_val}{COPYRIGHT}")

    url = f"{NUM_API_URL}?number={query_val}&key={NUM_API_KEY}"

    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            api_data = response.json()

            if not api_data.get("success"):
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ API Error\n\n{api_data.get('credit', 'Unknown error')}{COPYRIGHT}"
                )
                return

            if not api_data.get("found"):
                await context.bot.send_message(chat_id=chat_id, text=f"❌ No records found for {query_val}{COPYRIGHT}")
                if chat_id not in ADMINS:
                    consume_credit(chat_id)
                return

            records = api_data.get("result", [])
            res_text = f"🆔 Aadhar Lookup Results\n\n"
            res_text += f"🆔 Query: {query_val}\n"
            res_text += f"⏰ Time: {now_ist_str()}\n"
            res_text += f"📊 Total Records: {len(records)}\n\n"

            key_map = {
                "name": "👤 Name",
                "mobile": "📞 Mobile",
                "alt_mobile": "📱 Alt Mobile",
                "father_name": "👨‍👦 Father",
                "address": "🏠 Address",
                "circle": "📡 Circle",
                "email": "📧 Email",
                "aadhaar": "🆔 Aadhaar",
            }

            for idx, item in enumerate(records, 1):
                res_text += f"━ Record {idx} ━\n"
                if isinstance(item, dict):
                    for k, v in item.items():
                        if v is None or str(v).strip() == "":
                            continue
                        k_lower = str(k).lower()
                        if k_lower in key_map:
                            label = key_map[k_lower]
                            if k_lower == "aadhaar":
                                res_text += f"{label}: [Aadhaar Redacted]\n"
                            else:
                                res_text += f"{label}: {v}\n"
                        else:
                            res_text += f"🔹 {str(k).capitalize()}: {v}\n"
                else:
                    res_text += f"🔹 Data: {item}\n"
                res_text += "\n"

            res_text += COPYRIGHT
            if chat_id not in ADMINS:
                consume_credit(chat_id)

            if len(res_text) > 4000:
                res_text = res_text[:3950] + f"\n\n... (truncated){COPYRIGHT}"

            await context.bot.send_message(chat_id=chat_id, text=res_text.strip())
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ API Error\n\nStatus Code: {response.status_code}{COPYRIGHT}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Aadhar Lookup Failed\n\nError: {str(e)}{COPYRIGHT}")

# ==================== GST COMMAND ====================
async def gst(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in ADMINS and not await check_joined_status(context, chat_id):
        await send_join_prompt(context, chat_id)
        return

    u = ensure_user(chat_id)

    if not context.args:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Usage: /gst <number>{COPYRIGHT}")
        return

    if chat_id not in ADMINS and u["credits"] <= 0:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Not enough credits.{COPYRIGHT}")
        return

    gstnum = context.args[0].upper().strip()
    await context.bot.send_message(chat_id=chat_id, text=f"🔍 Searching GST Number...\n\n💸 GST: {gstnum}{COPYRIGHT}")

    url = f"https://gstlookup.hideme.eu.org/?gstNumber={gstnum}"

    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 200:
            api_data = response.json()
            res_text = f"💸 GST Lookup Results\n\nGST: {gstnum}\n\n"
            if isinstance(api_data, dict):
                for k, v in api_data.items():
                    res_text += f"🔹 {str(k).capitalize()}: {v}\n"
            else:
                res_text += str(api_data)

            res_text += COPYRIGHT
            if chat_id not in ADMINS:
                consume_credit(chat_id)
            await context.bot.send_message(chat_id=chat_id, text=res_text.strip())
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ API Error\n\nStatus Code: {response.status_code}{COPYRIGHT}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ GST Lookup Failed\n\nError: {str(e)}{COPYRIGHT}")

# ==================== OTHER COMMANDS ====================
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    u = ensure_user(chat_id)
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"💳 Balance Information\n\n"
            f"🆔 User ID: {chat_id}\n"
            f"💰 Credits: {u['credits']}\n"
            f"🔎 Total Searches: {u['searches']}\n"
            f"🕒 Last Used: {u['last_used_at'] or 'Never'}\n"
            f"🗓️ Joined: {u['joined_at']}{COPYRIGHT}"
        )
    )

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🆔 User Information\n\n"
            f"User ID: {chat_id}\n"
            f"User Type: {'Admin 👑' if chat_id in ADMINS else 'User 👤'}\n"
            f"Time: {now_ist_str()}{COPYRIGHT}"
        )
    )

async def addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        return
    if len(context.args) < 2:
        return await context.bot.send_message(chat_id=chat_id, text=f"❌ Usage: /addcredits <user_id> <amount>{COPYRIGHT}")
    uid, amt = context.args
    if uid not in USERS:
        return await context.bot.send_message(chat_id=chat_id, text=f"❌ User {uid} not found{COPYRIGHT}")
    try:
        amt = int(amt)
        if amt <= 0:
            return await context.bot.send_message(chat_id=chat_id, text=f"❌ Amount positive hona chahiye{COPYRIGHT}")
        USERS[uid]["credits"] += amt
        save_users()
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Added {amt} credits to {uid}. New balance: {USERS[uid]['credits']}{COPYRIGHT}")
    except ValueError:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Invalid amount{COPYRIGHT}")

async def subcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        return
    if len(context.args) < 2:
        return await context.bot.send_message(chat_id=chat_id, text=f"❌ Usage: /subcredits <user_id> <amount>{COPYRIGHT}")
    uid, amt = context.args
    if uid not in USERS:
        return await context.bot.send_message(chat_id=chat_id, text=f"❌ User {uid} not found{COPYRIGHT}")
    try:
        amt = int(amt)
        if amt <= 0:
            return await context.bot.send_message(chat_id=chat_id, text=f"❌ Amount positive hona chahiye{COPYRIGHT}")
        USERS[uid]["credits"] = max(0, USERS[uid]["credits"] - amt)
        save_users()
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Subtracted {amt} credits from {uid}. New balance: {USERS[uid]['credits']}{COPYRIGHT}")
    except ValueError:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Invalid amount{COPYRIGHT}")

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        return
    total_users = len(USERS)
    total_credits = sum([int(x.get("credits", 0)) for x in USERS.values()])
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"👥 Users List\n\n📊 Total Users: {total_users}\n💰 Total Credits: {total_credits}{COPYRIGHT}"
    )

async def exportusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        return
    if not os.path.exists(USERS_FILE):
        return await context.bot.send_message(chat_id=chat_id, text=f"❌ users.json not found{COPYRIGHT}")
    with open(USERS_FILE, "rb") as f:
        await context.bot.send_document(chat_id=chat_id, document=f, filename="users.json")

async def exportjson(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        return
    buf = io.BytesIO(json.dumps(USERS, indent=2).encode("utf-8"))
    buf.name = "users_export.json"
    await context.bot.send_document(chat_id=chat_id, document=buf)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ADMINS:
        return
    if not context.args:
        return await context.bot.send_message(chat_id=chat_id, text=f"❌ Usage: /broadcast <message>{COPYRIGHT}")
    msg = " ".join(context.args)
    ok, fail = 0, 0
    for uid in USERS.keys():
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 Broadcast:\n\n{msg}{COPYRIGHT}")
            ok += 1
        except Exception as e:
            print(f"[BC] Failed for {uid}: {e}")
            fail += 1
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ Broadcast Complete\n\n✅ Sent: {ok}\n❌ Failed: {fail}{COPYRIGHT}"
    )

# ==================== ERROR HANDLER ====================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"[ERROR] Update {update} caused error: {context.error}")

# ==================== MAIN ====================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("num", num))
    app.add_handler(CommandHandler("aadhar", aadhar))
    app.add_handler(CommandHandler("gst", gst))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("addcredits", addcredits))
    app.add_handler(CommandHandler("subcredits", subcredits))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("exportusers", exportusers))
    app.add_handler(CommandHandler("exportjson", exportjson))
    app.add_handler(CommandHandler("broadcast", broadcast))

    app.add_handler(CallbackQueryHandler(verify_button_handler, pattern="^check_join$"))
    app.add_error_handler(error_handler)

    print("🤖 Bot started successfully...")
    app.run_polling()

if __name__ == "__main__":
    main()
