"""
Username Info Bot — DEEP LOGIC EDITION (v4.1 - FIXED)
+ Group me bilkul chup (koi reply nahi)
+ Force Join System (Enable/Disable, Channel, Invite Link)
+ Credit Management (Add/Remove/Set/Check User)
- Only Username & Numeric ID to Info (TG2Num API)
- Smart Fallback: Agar username resolve na ho toh Numeric ID maange
- Credit Safety: Sirf successful API call par credits deduct
- JSON storage (No MongoDB)
- Signup: 30 credits | Referral: 10 credits (dono ko) | Search: 10 credits
+ Safe dotenv import (crash-proof)
+ Atomic credit deductions
+ HTML-safe broadcast
"""

import os, sys, re, json, time, threading, html
import logging
from datetime import datetime, timedelta

# ---------- Safe dotenv import (optional) ----------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed — using system env vars
    pass
except Exception:
    pass

import requests
import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("username_info_bot")

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
BOT_USERNAME = os.getenv("BOT_USERNAME", "@YourBot")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "@admin")

TG2NUM_API_URL = os.getenv(
    "TG2NUM_API_URL",
    "https://tg2num-botadminshere.vercel.app/?id="
)
DATA_FILE = os.getenv("DATA_FILE", "data.json")

SEARCH_COST = int(os.getenv("SEARCH_COST", 10))
SIGNUP_BONUS = int(os.getenv("SIGNUP_BONUS", 30))
REFERRAL_BONUS = int(os.getenv("REFERRAL_BONUS", 10))

if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN missing in environment")
    sys.exit(1)

# ---------- All Button Texts ----------
ALL_BUTTONS = [
    "🔒 Username To Info", "🛒 Buy Credits", "👤 My Profile", "ℹ️ About",
    "👑 Admin Panel", "📊 Dashboard", "📢 Broadcast",
    "🔗 Force Join", "💰 Credit Manager",
    "➕ Add Credits", "➖ Remove Credits", "💰 Set Credits", "👤 Check User",
    "🔧 Set Channel", "🔗 Set Invite Link", "⚙️ Toggle Force Join",
    "🔙 Admin Menu", "🔙 Back to Menu"
]

# ---------- JSON Storage ----------
def _default_data():
    return {
        "users": {},
        "stats": {"total_searches": 0, "searches_today": 0, "last_date": ""},
        "settings": {
            "force_join": {
                "enabled": False,
                "channel": None,
                "channel_link": None
            }
        }
    }

def load_data():
    default = _default_data()
    if not os.path.exists(DATA_FILE):
        return default
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            raise ValueError("Root is not a dict")
        d.setdefault("users", {})
        d.setdefault("stats", default["stats"])
        d.setdefault("settings", {})
        d["settings"].setdefault("force_join", default["settings"]["force_join"])
        d["settings"]["force_join"].setdefault("enabled", False)
        d["settings"]["force_join"].setdefault("channel", None)
        d["settings"]["force_join"].setdefault("channel_link", None)
        return d
    except Exception as e:
        logger.error(f"Corrupt data.json, resetting... Error: {e}")
        return default

def save_data(data):
    try:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DATA_FILE)
    except Exception as e:
        logger.error(f"Save data error: {e}")

data = load_data()
users = data["users"]
stats = data["stats"]
settings = data["settings"]

# ---------- Thread Lock for data safety ----------
_data_lock = threading.RLock()

def get_user(uid):
    uid_str = str(uid)
    with _data_lock:
        if uid_str not in users:
            users[uid_str] = {
                "credits": SIGNUP_BONUS,
                "searches": 0,
                "referrals": 0,
                "referred_by": None,
                "joined_at": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat()
            }
            save_data(data)
        return users[uid_str]

def add_credits(uid, amount):
    uid_str = str(uid)
    with _data_lock:
        if uid_str not in users:
            get_user(uid)
        users[uid_str]["credits"] += amount
        if users[uid_str]["credits"] < 0:
            users[uid_str]["credits"] = 0
        save_data(data)

def deduct_credits(uid, amount):
    """Atomic deduction with floor at 0"""
    uid_str = str(uid)
    with _data_lock:
        if uid_str not in users:
            return False
        current = users[uid_str].get("credits", 0)
        if current < amount:
            return False
        users[uid_str]["credits"] = current - amount
        save_data(data)
        return True

def get_credits(uid):
    return users.get(str(uid), {}).get("credits", 0)

def incr_searches(uid):
    uid_str = str(uid)
    today = datetime.now().strftime("%Y-%m-%d")
    with _data_lock:
        if uid_str in users:
            users[uid_str]["searches"] = users[uid_str].get("searches", 0) + 1
        if stats.get("last_date") != today:
            stats["last_date"] = today
            stats["searches_today"] = 0
        stats["total_searches"] = stats.get("total_searches", 0) + 1
        stats["searches_today"] = stats.get("searches_today", 0) + 1
        save_data(data)

def total_users(): return len(users)

def active_users_24h():
    cutoff = datetime.now() - timedelta(hours=24)
    count = 0
    for u in users.values():
        try:
            if datetime.fromisoformat(u.get("last_seen", "")) >= cutoff:
                count += 1
        except: pass
    return count

def total_searches(): return stats.get("total_searches", 0)

def searches_today():
    today = datetime.now().strftime("%Y-%m-%d")
    if stats.get("last_date") != today: return 0
    return stats.get("searches_today", 0)

# ---------- Referral Logic ----------
def handle_referral(new_uid, referrer_id):
    if new_uid == referrer_id: return False
    new_uid_str = str(new_uid)
    ref_str = str(referrer_id)
    with _data_lock:
        if new_uid_str not in users:
            get_user(new_uid)
        if users[new_uid_str].get("referred_by") is not None:
            return False
        users[new_uid_str]["referred_by"] = referrer_id
        add_credits(new_uid, REFERRAL_BONUS)
        if ref_str in users:
            add_credits(referrer_id, REFERRAL_BONUS)
            users[ref_str]["referrals"] = users[ref_str].get("referrals", 0) + 1
        else:
            get_user(referrer_id)
            add_credits(referrer_id, REFERRAL_BONUS)
            users[ref_str]["referrals"] = 1
        save_data(data)
        return True

# ---------- Bot Init ----------
bot = telebot.TeleBot(BOT_TOKEN)
try: bot.remove_webhook()
except: pass

# ---------- Rate Limiting ----------
_rate_lock = threading.Lock()
_last_call = {}
def rate_ok(uid):
    if uid == ADMIN_ID: return True
    now_t = time.time()
    with _rate_lock:
        if len(_last_call) > 10000:
            _last_call.clear()
        if uid in _last_call and now_t - _last_call[uid] < 1.2:
            return False
        _last_call[uid] = now_t
        return True

# ---------- HTML Escape Helper ----------
def esc(s):
    """Safely escape user/admin text for HTML parse mode"""
    if s is None: return ""
    return html.escape(str(s), quote=False)

# ---------- Animation Class ----------
class AnimMsg:
    def __init__(self, cid, *frames, interval=0.5, reply_to=None):
        self.cid = cid; self.frames = list(frames); self.interval = interval
        self.mid = None; self._stop = threading.Event(); self._t = None
        self._reply = reply_to; self._deleted = False
        self._edit_lock = threading.Lock()

    def start(self):
        try:
            kw = {"parse_mode": "HTML"}
            if self._reply: kw["reply_to_message_id"] = self._reply
            m = bot.send_message(self.cid, self.frames[0], **kw)
            self.mid = m.message_id
            self._t = threading.Thread(target=self._run, daemon=True)
            self._t.start()
            return True
        except: return False

    def _run(self):
        i = 1; last_text = self.frames[0] if self.frames else ""
        while not self._stop.is_set():
            if self._deleted or self.mid is None: return
            text = self.frames[i % len(self.frames)]
            if text != last_text:
                try:
                    with self._edit_lock:
                        if self._deleted or self.mid is None: return
                        bot.edit_message_text(text, self.cid, self.mid, parse_mode="HTML")
                    last_text = text
                except Exception as e:
                    if "not modified" not in str(e).lower():
                        time.sleep(0.5)
            i += 1
            w = 0
            while w < self.interval:
                if self._stop.is_set(): return
                time.sleep(0.08); w += 0.08

    def stop(self):
        self._stop.set()
        if self._t:
            try: self._t.join(timeout=2)
            except: pass

    def edit(self, text, mark=None, parse_mode=None):
        with self._edit_lock:
            if self._deleted or self.mid is None:
                try: bot.send_message(self.cid, text, parse_mode="HTML", reply_markup=mark)
                except: pass
                return
            try:
                bot.edit_message_text(text, self.cid, self.mid, parse_mode="HTML", reply_markup=mark)
            except Exception as e:
                if "not modified" in str(e).lower():
                    try: bot.edit_message_reply_markup(self.cid, self.mid, reply_markup=mark)
                    except: pass
                    return
                try:
                    m = bot.send_message(self.cid, text, parse_mode="HTML", reply_markup=mark)
                    self.mid = m.message_id
                except: pass

    def delete(self):
        self.stop(); self._deleted = True
        if self.mid is None: return
        try: bot.delete_message(self.cid, self.mid)
        except: pass

def progress_bar(pct, width=12):
    pct = max(0, min(100, int(pct)))
    filled = int(width * pct / 100)
    return "▰" * filled + "▱" * (width - filled) + f" {pct}%"

def build_search_frames(prefix="🔒 <b>Username Lookup</b>"):
    frames = []
    for i, pct in enumerate(range(0, 100, 10)):
        frames.append(f"⏳ {prefix}\n<code>{progress_bar(pct)}</code>")
    frames.append(f"✅ {prefix}\n<code>{progress_bar(100)}</code>")
    return frames

# ================= FORCE JOIN DEEP LOGIC =================
def is_user_joined(uid):
    fj = settings.get("force_join", {})
    if not fj.get("enabled") or not fj.get("channel"):
        return True
    if uid == ADMIN_ID:
        return True
    try:
        member = bot.get_chat_member(fj["channel"], uid)
        if member.status in ("member", "administrator", "creator"):
            return True
        if getattr(member, "status", "") == "restricted" and getattr(member, "is_member", False):
            return True
        return False
    except Exception as e:
        logger.warning(f"ForceJoin check failed for {uid}: {e} — failing OPEN")
        return True

def build_join_kb():
    fj = settings.get("force_join", {})
    channel = fj.get("channel") or ""
    link = fj.get("channel_link") or f"https://t.me/{str(channel).lstrip('@')}"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📢 Join Channel", url=link))
    kb.add(InlineKeyboardButton("✅ I've Joined", callback_data="check_join"))
    return kb

def ensure_joined(uid, cid, reply_to=None):
    if is_user_joined(uid):
        return True
    try:
        bot.send_message(
            cid,
            "⚠️ <b>Force Join Required</b>\n\n"
            "Bot use karne se pehle channel join karein.\n"
            "Join karne ke baad <b>✅ I've Joined</b> button dabayein.",
            parse_mode="HTML",
            reply_markup=build_join_kb(),
            reply_to_message_id=reply_to
        )
    except Exception as e:
        logger.error(f"ensure_joined send error: {e}")
    return False

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def cb_check_join(c):
    uid = c.from_user.id
    if is_user_joined(uid):
        try: bot.delete_message(c.message.chat.id, c.message.message_id)
        except: pass
        bot.answer_callback_query(c.id, "✅ Verified! Ab bot use kar sakte hain.", show_alert=True)
        try:
            bot.send_message(
                c.message.chat.id,
                "✅ <b>Verification Successful!</b>\nAb aap username/ID search kar sakte hain.",
                parse_mode="HTML",
                reply_markup=main_kb(uid)
            )
        except: pass
    else:
        bot.answer_callback_query(c.id, "❌ Aapne abhi channel join nahi kiya!", show_alert=True)

# ---------- Keyboards ----------
def main_kb(uid):
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("🔒 Username To Info"), KeyboardButton("🛒 Buy Credits"))
    if uid == ADMIN_ID:
        kb.row(KeyboardButton("👤 My Profile"), KeyboardButton("👑 Admin Panel"))
    else:
        kb.row(KeyboardButton("👤 My Profile"), KeyboardButton("ℹ️ About"))
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("📊 Dashboard"), KeyboardButton("📢 Broadcast"))
    kb.row(KeyboardButton("🔗 Force Join"), KeyboardButton("💰 Credit Manager"))
    kb.row(KeyboardButton("🔙 Back to Menu"))
    return kb

def force_join_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("🔧 Set Channel"), KeyboardButton("🔗 Set Invite Link"))
    kb.row(KeyboardButton("⚙️ Toggle Force Join"))
    kb.row(KeyboardButton("🔙 Admin Menu"))
    return kb

def credit_mgr_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("➕ Add Credits"), KeyboardButton("➖ Remove Credits"))
    kb.row(KeyboardButton("💰 Set Credits"), KeyboardButton("👤 Check User"))
    kb.row(KeyboardButton("🔙 Admin Menu"))
    return kb

def force_join_status_text():
    fj = settings.get("force_join", {})
    status = "🟢 ENABLED" if fj.get("enabled") else "🔴 DISABLED"
    channel = fj.get("channel") or "— Not set —"
    link = fj.get("channel_link") or "— Not set —"
    return (
        f"🔗 <b>Force Join Settings</b>\n\n"
        f"Status: <b>{status}</b>\n"
        f"Channel: <code>{esc(channel)}</code>\n"
        f"Invite Link: <code>{esc(link)}</code>\n\n"
        f"<i>Note: Bot ko channel me admin hona chahiye warna verification fail hoga.</i>"
    )

# ================= CORE: USERNAME & ID LOOKUP =================
def process_tg2num(uid, cid, query, reply_to=None):
    query = query.strip()
    if not query:
        bot.send_message(cid, "❌ Invalid input.", reply_to_message_id=reply_to); return

    if not ensure_joined(uid, cid, reply_to):
        return

    is_admin = (uid == ADMIN_ID)

    if not is_admin and get_credits(uid) < SEARCH_COST:
        bot.send_message(
            cid,
            f"⚠️ Not enough credits.\n🔎 Cost: {SEARCH_COST}\n"
            f"💎 Yours: {get_credits(uid)}\n\n🛒 Contact {esc(ADMIN_USERNAME)}",
            reply_to_message_id=reply_to
        )
        return

    frames = build_search_frames()
    am = AnimMsg(cid, *frames, interval=0.3, reply_to=reply_to)
    am.start()

    tg_id = None
    display_name = query

    if query.isdigit():
        tg_id = query
        display_name = f"ID: {tg_id}"
    else:
        username_clean = query.lstrip('@')
        display_name = f"@{username_clean}"
        try:
            chat = bot.get_chat(f"@{username_clean}")
            tg_id = chat.id
        except Exception:
            am.stop()
            am.edit(
                f"❌ <b>Could not resolve {esc(display_name)}</b>\n\n"
                f"Telegram bots cannot directly convert random public usernames to IDs (Privacy Policy).\n\n"
                f"💡 <b>Solution:</b>\n"
                f"Please provide the <b>Numeric Telegram ID</b> instead.\n"
                f"Example: <code>5339638465</code>\n\n"
                f"<i>(You can get a user's ID by asking them to message @userinfobot)</i>"
            )
            return

    try:
        resp = requests.get(f"{TG2NUM_API_URL}{tg_id}", timeout=15)
        if resp.status_code != 200:
            am.stop(); am.edit(f"⚠️ API Error ({resp.status_code})"); return
        api_data = resp.json()
    except Exception as e:
        logger.error(f"TG2Num API error: {e}")
        am.stop(); am.edit("⚠️ API Unreachable"); return

    if api_data.get("success") and api_data.get("result"):
        r = api_data["result"]
        number = r.get("number", "N/A")
        country = r.get("country", "N/A")
        country_code = r.get("country_code", "N/A")

        text = (
            f"✅ <b>Result for {esc(display_name)}</b>\n\n"
            f"🆔 <b>Telegram ID:</b> <code>{esc(tg_id)}</code>\n"
            f"📞 <b>Number:</b> <code>{esc(country_code)}{esc(number)}</code>\n"
            f"🌍 <b>Country:</b> {esc(country)}\n"
        )

        # Only deduct if API actually returned data AND user is not admin
        if not is_admin:
            if deduct_credits(uid, SEARCH_COST):
                text += f"\n💎 Credits left: {get_credits(uid)}"
            else:
                # Edge case: credits dried between check and deduct
                am.stop(); am.delete()
                bot.send_message(
                    cid,
                    "⚠️ Credits deduction failed (balance too low). Please try again.",
                    reply_to_message_id=reply_to
                )
                return
        incr_searches(uid)

        am.stop(); am.delete()
        bot.send_message(cid, text, parse_mode='HTML', reply_to_message_id=reply_to)
    else:
        am.stop()
        am.edit(f"😔 No data found for {esc(display_name)}.")

# ================= HANDLERS =================
@bot.message_handler(commands=['start'])
def cmd_start(m):
    # 🔥 STRICT GUARD: Group me bilkul chup raho
    if m.chat.type != 'private':
        return

    uid = m.from_user.id

    if ' ' in m.text:
        parts = m.text.split()
        if len(parts) > 1 and parts[1].startswith('ref_'):
            try:
                referrer_id = int(parts[1].replace('ref_', ''))
                if handle_referral(uid, referrer_id):
                    try: bot.send_message(referrer_id, f"🎉 New referral! +{REFERRAL_BONUS} credits")
                    except: pass
            except: pass

    user = get_user(uid)
    user["last_seen"] = datetime.now().isoformat()
    save_data(data)

    credits_display = '♾️' if uid == ADMIN_ID else get_credits(uid)
    bot.reply_to(
        m,
        f"👋 <b>Welcome!</b>\n\n"
        f"Main Telegram Username ya Numeric ID ki info nikalta hoon.\n\n"
        f"🔒 Cost: {SEARCH_COST} credits per lookup\n"
        f"💎 Your credits: {credits_display}\n\n"
        f"Send a username (e.g., <code>@username</code>) or Numeric ID "
        f"(e.g., <code>5339638465</code>) to begin.\n"
        f"🛒 To buy credits, contact {esc(ADMIN_USERNAME)}",
        parse_mode='HTML',
        reply_markup=main_kb(uid)
    )

    if not is_user_joined(uid):
        ensure_joined(uid, m.chat.id)

@bot.message_handler(func=lambda m: m.text == "🔒 Username To Info" and m.chat.type == 'private')
def btn_username(m):
    if not ensure_joined(m.from_user.id, m.chat.id, m.message_id):
        return
    bot.reply_to(m, "Send a Telegram Username (with or without @) or Numeric ID:")

@bot.message_handler(func=lambda m: m.text == "👤 My Profile" and m.chat.type == 'private')
def btn_profile(m):
    uid = m.from_user.id
    user = get_user(uid)
    user["last_seen"] = datetime.now().isoformat()
    save_data(data)
    credits_display = '♾️' if uid == ADMIN_ID else user.get('credits', 0)
    bot.reply_to(
        m,
        f"👤 <b>Your Profile</b>\n\n"
        f"🆔 <code>{uid}</code>\n"
        f"💎 Credits: <b>{credits_display}</b>\n"
        f"🔍 Searches: {user.get('searches', 0)}\n"
        f"👥 Referrals: {user.get('referrals', 0)}",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda m: m.text == "🛒 Buy Credits" and m.chat.type == 'private')
def btn_buy(m):
    bot.reply_to(
        m,
        f"🛒 <b>Buy Credits</b>\n\nContact: {esc(ADMIN_USERNAME)}\n\n"
        f"💎 1 search = {SEARCH_COST} credits",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ About" and m.chat.type == 'private')
def btn_about(m):
    bot.reply_to(m, f"ℹ️ Username Info Bot\n{esc(BOT_USERNAME)}")

# ---------- Admin Panel (DM only) ----------
@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_admin(m):
    bot.reply_to(m, "👑 <b>Admin Panel</b>", parse_mode='HTML', reply_markup=admin_kb())

@bot.message_handler(func=lambda m: m.text == "📊 Dashboard" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_dashboard(m):
    fj = settings.get("force_join", {})
    txt = (
        f"📊 <b>Dashboard</b>\n\n"
        f"👥 Total Users: <b>{total_users()}</b>\n"
        f"🔥 Active (24h): <b>{active_users_24h()}</b>\n"
        f"🔍 Total Searches: <b>{total_searches()}</b>\n"
        f"📅 Searches Today: <b>{searches_today()}</b>\n\n"
        f"🔗 Force Join: <b>{'🟢 ON' if fj.get('enabled') else '🔴 OFF'}</b>"
    )
    bot.reply_to(m, txt, parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_broadcast(m):
    msg = bot.reply_to(m, "Send the message to broadcast to all users:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(m):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Broadcast cancelled."); return
    text = m.text
    if not text: return

    # Escape text for HTML to avoid parse errors
    safe_text = esc(text)

    success = 0
    for uid_str in list(users.keys()):
        try:
            bot.send_message(int(uid_str), safe_text, parse_mode='HTML')
            success += 1
            time.sleep(0.05)
        except: pass
    bot.reply_to(m, f"✅ Broadcast sent to {success}/{len(users)} users.")

@bot.message_handler(func=lambda m: m.text == "🔙 Back to Menu" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_back(m):
    bot.reply_to(m, "🏠 Main Menu", reply_markup=main_kb(ADMIN_ID))

# ================= FORCE JOIN ADMIN HANDLERS =================
@bot.message_handler(func=lambda m: m.text == "🔗 Force Join" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_force_join(m):
    bot.reply_to(m, force_join_status_text(), parse_mode='HTML', reply_markup=force_join_kb())

@bot.message_handler(func=lambda m: m.text == "🔧 Set Channel" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_set_channel(m):
    msg = bot.reply_to(
        m,
        "Send the channel username (e.g. <code>@mychannel</code>) or channel ID "
        "(e.g. <code>-1001234567890</code>).",
        parse_mode='HTML'
    )
    bot.register_next_step_handler(msg, do_set_channel)

def do_set_channel(m):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=force_join_kb()); return
    val = m.text.strip()
    if not (val.startswith("@") or val.lstrip("-").isdigit()):
        bot.reply_to(m, "❌ Invalid format. Use @username or numeric channel ID.")
        return
    try:
        chat = bot.get_chat(val)
        settings["force_join"]["channel"] = val
        if not settings["force_join"].get("channel_link"):
            if chat.username:
                settings["force_join"]["channel_link"] = f"https://t.me/{chat.username}"
        save_data(data)
        bot.reply_to(
            m,
            f"✅ Channel set to <code>{esc(val)}</code>\n"
            f"📛 Title: {esc(chat.title or '')}\n"
            f"🔗 Link: {esc(str(settings['force_join'].get('channel_link') or '—'))}",
            parse_mode='HTML', reply_markup=force_join_kb()
        )
    except Exception as e:
        bot.reply_to(
            m,
            f"❌ Could not access channel: <code>{esc(str(e))}</code>\n\n"
            f"Make sure bot is added as admin in that channel.",
            parse_mode='HTML'
        )

@bot.message_handler(func=lambda m: m.text == "🔗 Set Invite Link" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_set_link(m):
    msg = bot.reply_to(m, "Send the invite link (e.g. <code>https://t.me/+AbCdEf123</code>):", parse_mode='HTML')
    bot.register_next_step_handler(msg, do_set_link)

def do_set_link(m):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=force_join_kb()); return
    val = m.text.strip()
    if not val.startswith("http"):
        bot.reply_to(m, "❌ Invalid link. Must start with http/https.")
        return
    settings["force_join"]["channel_link"] = val
    save_data(data)
    bot.reply_to(m, f"✅ Invite link saved:\n<code>{esc(val)}</code>", parse_mode='HTML', reply_markup=force_join_kb())

@bot.message_handler(func=lambda m: m.text == "⚙️ Toggle Force Join" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_toggle_fj(m):
    fj = settings["force_join"]
    if not fj.get("channel"):
        bot.reply_to(m, "⚠️ Pehle channel set karein (🔧 Set Channel).", reply_markup=force_join_kb())
        return
    fj["enabled"] = not fj.get("enabled", False)
    save_data(data)
    bot.reply_to(
        m,
        f"{'🟢 Force Join ENABLED' if fj['enabled'] else '🔴 Force Join DISABLED'}",
        reply_markup=force_join_kb()
    )

# ================= CREDIT MANAGER ADMIN HANDLERS =================
@bot.message_handler(func=lambda m: m.text == "💰 Credit Manager" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_credit_mgr(m):
    bot.reply_to(m, "💰 <b>Credit Manager</b>\n\nChoose an action:", parse_mode='HTML', reply_markup=credit_mgr_kb())

@bot.message_handler(func=lambda m: m.text == "➕ Add Credits" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_add_credits(m):
    msg = bot.reply_to(m, "Send User ID to add credits to:")
    bot.register_next_step_handler(msg, ask_amount_add)

def ask_amount_add(m):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=credit_mgr_kb()); return
    txt = m.text.strip()
    if not txt.lstrip("-").isdigit():
        bot.reply_to(m, "❌ Invalid User ID.", reply_markup=credit_mgr_kb()); return
    target = int(txt)
    msg = bot.reply_to(m, f"User: <code>{target}</code>\nSend amount to <b>ADD</b>:", parse_mode='HTML')
    bot.register_next_step_handler(msg, do_add_credits, target)

def do_add_credits(m, target):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=credit_mgr_kb()); return
    try:
        amount = int(m.text.strip())
        if amount <= 0: raise ValueError
    except:
        bot.reply_to(m, "❌ Invalid amount.", reply_markup=credit_mgr_kb()); return
    get_user(target)
    add_credits(target, amount)
    new_bal = get_credits(target)
    bot.reply_to(
        m,
        f"✅ Added <b>{amount}</b> credits to <code>{target}</code>\n"
        f"💎 New balance: <b>{new_bal}</b>",
        parse_mode='HTML', reply_markup=credit_mgr_kb()
    )
    try:
        bot.send_message(
            target,
            f"🎁 Admin ne aapko <b>{amount}</b> credits diye!\n💎 Balance: <b>{new_bal}</b>",
            parse_mode='HTML'
        )
    except: pass

@bot.message_handler(func=lambda m: m.text == "➖ Remove Credits" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_remove_credits(m):
    msg = bot.reply_to(m, "Send User ID to remove credits from:")
    bot.register_next_step_handler(msg, ask_amount_remove)

def ask_amount_remove(m):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=credit_mgr_kb()); return
    txt = m.text.strip()
    if not txt.lstrip("-").isdigit():
        bot.reply_to(m, "❌ Invalid User ID.", reply_markup=credit_mgr_kb()); return
    target = int(txt)
    msg = bot.reply_to(m, f"User: <code>{target}</code>\nSend amount to <b>REMOVE</b>:", parse_mode='HTML')
    bot.register_next_step_handler(msg, do_remove_credits, target)

def do_remove_credits(m, target):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=credit_mgr_kb()); return
    try:
        amount = int(m.text.strip())
        if amount <= 0: raise ValueError
    except:
        bot.reply_to(m, "❌ Invalid amount.", reply_markup=credit_mgr_kb()); return
    get_user(target)
    add_credits(target, -amount)
    new_bal = get_credits(target)
    bot.reply_to(
        m,
        f"✅ Removed <b>{amount}</b> credits from <code>{target}</code>\n"
        f"💎 New balance: <b>{new_bal}</b>",
        parse_mode='HTML', reply_markup=credit_mgr_kb()
    )

@bot.message_handler(func=lambda m: m.text == "💰 Set Credits" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_set_credits(m):
    msg = bot.reply_to(m, "Send User ID to set credits for:")
    bot.register_next_step_handler(msg, ask_amount_set)

def ask_amount_set(m):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=credit_mgr_kb()); return
    txt = m.text.strip()
    if not txt.lstrip("-").isdigit():
        bot.reply_to(m, "❌ Invalid User ID.", reply_markup=credit_mgr_kb()); return
    target = int(txt)
    msg = bot.reply_to(m, f"User: <code>{target}</code>\nSend new credit value:", parse_mode='HTML')
    bot.register_next_step_handler(msg, do_set_credits, target)

def do_set_credits(m, target):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=credit_mgr_kb()); return
    try:
        value = int(m.text.strip())
        if value < 0: raise ValueError
    except:
        bot.reply_to(m, "❌ Invalid value.", reply_markup=credit_mgr_kb()); return
    get_user(target)
    with _data_lock:
        users[str(target)]["credits"] = value
        save_data(data)
    bot.reply_to(
        m,
        f"✅ Set <code>{target}</code> credits to <b>{value}</b>",
        parse_mode='HTML', reply_markup=credit_mgr_kb()
    )

@bot.message_handler(func=lambda m: m.text == "👤 Check User" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_check_user(m):
    msg = bot.reply_to(m, "Send User ID to check:")
    bot.register_next_step_handler(msg, do_check_user)

def do_check_user(m):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Cancelled.", reply_markup=credit_mgr_kb()); return
    txt = m.text.strip()
    if not txt.lstrip("-").isdigit():
        bot.reply_to(m, "❌ Invalid User ID.", reply_markup=credit_mgr_kb()); return
    target = int(txt)
    u = users.get(str(target))
    if not u:
        bot.reply_to(
            m,
            f"❌ User <code>{target}</code> not found in database.",
            parse_mode='HTML', reply_markup=credit_mgr_kb()
        )
        return
    txt_out = (
        f"👤 <b>User Info</b>\n\n"
        f"🆔 <code>{target}</code>\n"
        f"💎 Credits: <b>{u.get('credits', 0)}</b>\n"
        f"🔍 Searches: {u.get('searches', 0)}\n"
        f"👥 Referrals: {u.get('referrals', 0)}\n"
        f"👤 Referred by: <code>{u.get('referred_by') or '—'}</code>\n"
        f"📅 Joined: {u.get('joined_at', '')[:19]}\n"
        f"🕐 Last seen: {u.get('last_seen', '')[:19]}"
    )
    bot.reply_to(m, txt_out, parse_mode='HTML', reply_markup=credit_mgr_kb())

@bot.message_handler(func=lambda m: m.text == "🔙 Admin Menu" and m.from_user.id == ADMIN_ID and m.chat.type == 'private')
def btn_admin_menu(m):
    bot.reply_to(m, "👑 <b>Admin Panel</b>", parse_mode='HTML', reply_markup=admin_kb())

# ================= PRIVATE CHAT HANDLER (MAIN LOOKUP) =================
@bot.message_handler(func=lambda m: m.chat.type == 'private' and m.content_type == 'text' and not m.text.startswith('/'))
def private_text_handler(m):
    uid = m.from_user.id
    text = m.text.strip()

    if text in ALL_BUTTONS:
        return

    if not rate_ok(uid): return

    if not ensure_joined(uid, m.chat.id, m.message_id):
        return

    if re.match(r'^@?[a-zA-Z0-9_]{5,32}$', text) or text.isdigit():
        process_tg2num(uid, m.chat.id, text, m.message_id)
        return

    bot.reply_to(
        m,
        "❌ Invalid input. Send a valid Telegram Username (e.g., @username) "
        "or Numeric ID (e.g., 5339638465)."
    )

# ================= ENTRY =================
if __name__ == "__main__":
    logger.info("🚀 Bot starting (DEEP LOGIC EDITION v4.1 FIXED)...")
    logger.info(f"👑 Admin ID: {ADMIN_ID}")
    logger.info(f"📞 Admin contact: {ADMIN_USERNAME}")
    logger.info(f"🔗 Force Join: {'ON' if settings['force_join'].get('enabled') else 'OFF'}")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.critical(f"Crashed: {e}")
