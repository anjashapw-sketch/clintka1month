"""
Username Info Bot — v9 FORCE JOIN FIRST
+ Force join prompt PEHLE (no welcome before verify)
+ Welcome message ONLY after verification
+ Multi-admin, env-driven force join, auto-install
"""

import os, sys, subprocess, time

# ============================================================
# AUTO-INSTALLER
# ============================================================
_PACKAGE_MAP = {
    "telebot": "pyTelegramBotAPI==4.14.0",
    "dotenv":  "python-dotenv==1.0.0",
}

def _ensure_modules():
    missing = []
    for mod_name, pkg_name in _PACKAGE_MAP.items():
        try:
            __import__(mod_name)
        except ImportError:
            missing.append((mod_name, pkg_name))

    if not missing:
        print("✅ All modules present", flush=True)
        return

    print(f"⚠️ Missing modules: {[m[0] for m in missing]}", flush=True)
    print("⏳ Auto-installing...", flush=True)

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    for mod_name, pkg_name in missing:
        print(f"📦 Installing {pkg_name}...", flush=True)
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir", pkg_name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            print(f"✅ Installed {pkg_name}", flush=True)
        except Exception as e:
            print(f"❌ Failed to install {pkg_name}: {e}", flush=True)
            sys.exit(1)

    for mod_name, _ in missing:
        try:
            __import__(mod_name)
        except ImportError:
            print(f"❌ {mod_name} still missing after install", flush=True)
            sys.exit(1)

_ensure_modules()
# ============================================================

import re, json, threading, html
import logging
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
except Exception:
    pass

import urllib.request
import urllib.error
import ssl

import telebot
from telebot.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("username_info_bot")

def _clean_env(key, default=""):
    val = os.getenv(key, default)
    if val is None:
        return default
    val = str(val).strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        val = val[1:-1]
    return val

# ---------- Config ----------
BOT_TOKEN = _clean_env("BOT_TOKEN")
BOT_USERNAME = _clean_env("BOT_USERNAME", "@YourBot")
ADMIN_USERNAME = _clean_env("ADMIN_USERNAME", "@admin")
TG2NUM_API_URL = _clean_env("TG2NUM_API_URL", "https://tg2num-botadminshere.vercel.app/?id=")
DATA_FILE = _clean_env("DATA_FILE", "data.json")

try:
    SEARCH_COST = int(_clean_env("SEARCH_COST", "10"))
    SIGNUP_BONUS = int(_clean_env("SIGNUP_BONUS", "30"))
    REFERRAL_BONUS = int(_clean_env("REFERRAL_BONUS", "10"))
except ValueError as e:
    logger.critical(f"❌ Invalid numeric config: {e}")
    sys.exit(1)

def _load_admin_ids():
    ids = []
    primary = _clean_env("ADMIN_ID", "")
    if primary:
        try:
            ids.append(int(primary))
        except ValueError:
            logger.warning(f"⚠️ Invalid ADMIN_ID: {primary}")
    for i in range(2, 11):
        v = _clean_env(f"ADMIN_ID_{i}", "")
        if v:
            try:
                uid = int(v)
                if uid not in ids:
                    ids.append(uid)
            except ValueError:
                logger.warning(f"⚠️ Invalid ADMIN_ID_{i}: {v}")
    return ids

ADMIN_IDS = _load_admin_ids()
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 0

def is_admin(uid):
    return uid in ADMIN_IDS

if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN missing")
    sys.exit(1)

# ---------- Force Join Env ----------
def _load_fj_env():
    raw = _clean_env("FORCE_JOIN_ENABLED", "false").lower()
    enabled = raw in ("true", "1", "yes", "on")
    channels = []
    for i in range(1, 11):
        cid = _clean_env(f"FORCE_JOIN_CHANNEL_{i}")
        link = _clean_env(f"FORCE_JOIN_LINK_{i}")
        if cid:
            if not link:
                link = f"https://t.me/{cid.lstrip('@')}" if cid.startswith("@") else ""
            channels.append({"channel": cid, "link": link})
    return enabled, channels

_FJ_ENABLED, _FJ_CHANNELS = _load_fj_env()

# ---------- SSL ----------
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

def http_get_json(url, timeout=15):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            status_code = resp.status
            raw = resp.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return status_code, None, f"Invalid JSON: {e}"
        return status_code, data, None
    except urllib.error.HTTPError as e:
        return e.code, None, f"HTTPError {e.code}"
    except urllib.error.URLError as e:
        return 0, None, f"URLError: {e.reason}"
    except Exception as e:
        return 0, None, f"Unexpected: {e}"

ALL_BUTTONS = [
    "🔒 Username To Info", "🛒 Buy Credits", "👤 My Profile", "ℹ️ About",
    "👑 Admin Panel", "📊 Dashboard", "📢 Broadcast",
    "🔗 Force Join", "💰 Credit Manager",
    "➕ Add Credits", "➖ Remove Credits", "💰 Set Credits", "👤 Check User",
    "🔙 Admin Menu", "🔙 Back to Menu"
]

# ---------- Data ----------
def _default_data():
    return {
        "users": {},
        "stats": {"total_searches": 0, "searches_today": 0, "last_date": ""},
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
        if "settings" in d:
            d["settings"].pop("force_join", None)
        return d
    except Exception as e:
        logger.error(f"Corrupt data.json, resetting... Error: {e}")
        return default

def save_data(d):
    try:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DATA_FILE)
    except Exception as e:
        logger.error(f"Save data error: {e}")

data = load_data()
users = data["users"]
stats = data["stats"]

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

bot = telebot.TeleBot(BOT_TOKEN)
try: bot.remove_webhook()
except: pass

_rate_lock = threading.Lock()
_last_call = {}
def rate_ok(uid):
    if is_admin(uid): return True
    now_t = time.time()
    with _rate_lock:
        if len(_last_call) > 10000:
            _last_call.clear()
        if uid in _last_call and now_t - _last_call[uid] < 1.2:
            return False
        _last_call[uid] = now_t
        return True

def esc(s):
    if s is None: return ""
    return html.escape(str(s), quote=False)

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

# ============================================================
# FORCE JOIN
# ============================================================
_FJ_ACTIVE = False
_FJ_VALID_CHANNELS = []
_FJ_INVALID_CHANNELS = []

def _validate_fj_channels_startup():
    global _FJ_ACTIVE, _FJ_VALID_CHANNELS, _FJ_INVALID_CHANNELS

    if not _FJ_ENABLED:
        _FJ_ACTIVE = False
        logger.info("🔓 Force Join: DISABLED (env)")
        return

    if not _FJ_CHANNELS:
        _FJ_ACTIVE = False
        logger.warning("🔓 Force Join: DISABLED (no channels)")
        return

    try:
        bot_me = bot.get_me()
    except Exception as e:
        logger.error(f"❌ Cannot get bot info: {e}")
        _FJ_ACTIVE = False
        return

    valid, invalid = [], []
    for ch in _FJ_CHANNELS:
        cid = ch.get("channel")
        try:
            member = bot.get_chat_member(cid, bot_me.id)
            status = getattr(member, "status", "")
            if status in ("administrator", "creator"):
                valid.append(ch)
                logger.info(f"   ✅ {cid} — bot is {status}")
            else:
                invalid.append(ch)
                logger.warning(f"   ❌ {cid} — bot is '{status}' (must be admin)")
        except Exception as e:
            invalid.append(ch)
            logger.warning(f"   ❌ {cid} — ERROR: {e}")

    _FJ_VALID_CHANNELS = valid
    _FJ_INVALID_CHANNELS = invalid

    if valid:
        _FJ_ACTIVE = True
        logger.info(f"🔒 Force Join: ENABLED — {len(valid)} channel(s) active")
    else:
        _FJ_ACTIVE = False
        logger.warning(f"🔒 Force Join: DISABLED — bot not admin in any channel")

def get_fj_active_channels():
    return _FJ_VALID_CHANNELS

def is_user_joined(uid):
    if not _FJ_ACTIVE:
        return True
    if is_admin(uid):
        return True
    channels = get_fj_active_channels()
    if not channels:
        return True

    for ch in channels:
        cid = ch.get("channel")
        if not cid:
            continue
        try:
            member = bot.get_chat_member(cid, uid)
            status = getattr(member, "status", "")
            if status in ("member", "administrator", "creator"):
                continue
            if status == "restricted" and getattr(member, "is_member", False):
                continue
            return False
        except Exception as e:
            logger.warning(f"FJ check error uid={uid} ch={cid}: {e}")
            return False
    return True

def build_join_kb():
    channels = get_fj_active_channels()
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(channels[:10], 1):
        link = ch.get("link") or ""
        if link:
            kb.add(InlineKeyboardButton(f"📢 Join Channel {i}", url=link))
        else:
            kb.add(InlineKeyboardButton(f"📢 Channel {i} (no link)", callback_data="noop"))
    kb.add(InlineKeyboardButton("✅ I've Joined All", callback_data="check_join"))
    return kb

def send_force_join_prompt(cid, uid, reply_to=None):
    """Send ONLY force join prompt"""
    channels = get_fj_active_channels()
    if not channels:
        return False
    try:
        bot.send_message(
            cid,
            f"⚠️ <b>Force Join Required</b>\n\n"
            f"Bot use karne se pehle <b>{len(channels)}</b> channels join karein:\n\n"
            f"Join karne ke baad <b>✅ I've Joined All</b> button dabayein.",
            parse_mode="HTML",
            reply_markup=build_join_kb(),
            reply_to_message_id=reply_to
        )
        return True
    except Exception as e:
        logger.error(f"force_join prompt error: {e}")
        return False

def ensure_joined(uid, cid, reply_to=None):
    """Returns True if user can proceed, False if force join prompt sent"""
    if is_user_joined(uid):
        return True
    send_force_join_prompt(cid, uid, reply_to)
    return False

def build_welcome_text(uid):
    """Full welcome text — sent ONLY after verification (or if no FJ)"""
    credits_display = '♾️' if is_admin(uid) else get_credits(uid)
    return (
        f"👋 <b>Welcome!</b>\n\n"
        f"Main Telegram Username ya Numeric ID ki info nikalta hoon.\n\n"
        f"🔒 Cost: {SEARCH_COST} credits per lookup\n"
        f"💎 Your credits: {credits_display}\n\n"
        f"Send a username (e.g., <code>@username</code>) or Numeric ID "
        f"(e.g., <code>5339638465</code>) to begin.\n"
        f"🛒 To buy credits, contact {esc(ADMIN_USERNAME)}"
    )

def send_welcome(cid, uid, reply_to=None):
    """Send full welcome + main keyboard"""
    try:
        kw = {"parse_mode": "HTML", "reply_markup": main_kb(uid)}
        if reply_to: kw["reply_to_message_id"] = reply_to
        bot.send_message(cid, build_welcome_text(uid), **kw)
    except Exception as e:
        logger.error(f"send_welcome error: {e}")

# ---------- Keyboards ----------
def main_kb(uid):
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("🔒 Username To Info"), KeyboardButton("🛒 Buy Credits"))
    if is_admin(uid):
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

def credit_mgr_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("➕ Add Credits"), KeyboardButton("➖ Remove Credits"))
    kb.row(KeyboardButton("💰 Set Credits"), KeyboardButton("👤 Check User"))
    kb.row(KeyboardButton("🔙 Admin Menu"))
    return kb

def force_join_status_text():
    lines = [
        f"🔗 <b>Force Join Status</b>",
        f"",
        f"Env Enabled: <b>{_FJ_ENABLED}</b>",
        f"Runtime Active: <b>{_FJ_ACTIVE}</b>",
        f"",
    ]
    if _FJ_VALID_CHANNELS:
        lines.append(f"<b>✅ Active ({len(_FJ_VALID_CHANNELS)}):</b>")
        for i, ch in enumerate(_FJ_VALID_CHANNELS, 1):
            lines.append(f"  {i}. <code>{esc(ch.get('channel'))}</code>")
    else:
        lines.append("<i>No active channels</i>")

    if _FJ_INVALID_CHANNELS:
        lines.append(f"")
        lines.append(f"<b>❌ Invalid ({len(_FJ_INVALID_CHANNELS)}):</b>")
        for i, ch in enumerate(_FJ_INVALID_CHANNELS, 1):
            lines.append(f"  {i}. <code>{esc(ch.get('channel'))}</code>")

    return "\n".join(lines)

# ================= CALLBACK: check_join =================
@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def cb_check_join(c):
    uid = c.from_user.id
    cid = c.message.chat.id
    if is_user_joined(uid):
        # Delete force join message
        try: bot.delete_message(cid, c.message.message_id)
        except: pass
        bot.answer_callback_query(c.id, "✅ Verified! Ab bot use kar sakte hain.", show_alert=True)
        # ⭐ NOW send welcome message (AFTER verify)
        send_welcome(cid, uid)
    else:
        # Show missing channels
        channels = get_fj_active_channels()
        missing = []
        for ch in channels:
            cid_ch = ch.get("channel")
            try:
                member = bot.get_chat_member(cid_ch, uid)
                status = getattr(member, "status", "")
                if status not in ("member", "administrator", "creator"):
                    missing.append(ch.get("link") or str(cid_ch))
            except:
                missing.append(ch.get("link") or str(cid_ch))

        if missing:
            txt = "❌ Ye join nahi kiye:\n" + "\n".join(f"• {m}" for m in missing[:5])
        else:
            txt = "❌ Kuch channels join nahi kiye!"
        bot.answer_callback_query(c.id, txt, show_alert=True)

@bot.callback_query_handler(func=lambda c: c.data == "noop")
def cb_noop(c):
    bot.answer_callback_query(c.id)

# ================= CORE LOOKUP =================
def process_tg2num(uid, cid, query, reply_to=None):
    query = query.strip()
    if not query:
        bot.send_message(cid, "❌ Invalid input.", reply_to_message_id=reply_to); return

    if not ensure_joined(uid, cid, reply_to):
        return

    user_is_admin = is_admin(uid)

    if not user_is_admin and get_credits(uid) < SEARCH_COST:
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

    api_url = f"{TG2NUM_API_URL}{tg_id}"
    status_code, api_data, err = http_get_json(api_url, timeout=15)

    if err or status_code == 0:
        logger.error(f"TG2Num error: {err}")
        am.stop(); am.edit(f"⚠️ API Unreachable\n<code>{esc(err or 'unknown')}</code>"); return

    if status_code != 200:
        logger.error(f"TG2Num HTTP {status_code}")
        am.stop(); am.edit(f"⚠️ API Error ({status_code})"); return

    if not isinstance(api_data, dict):
        am.stop(); am.edit("⚠️ API returned invalid data"); return

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

        if not user_is_admin:
            if deduct_credits(uid, SEARCH_COST):
                text += f"\n💎 Credits left: {get_credits(uid)}"
            else:
                am.stop(); am.delete()
                bot.send_message(
                    cid,
                    "⚠️ Credits deduction failed. Please try again.",
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
@bot.message_handler(commands=['id', 'myid', 'whoami'])
def cmd_id(m):
    if m.chat.type != 'private':
        return
    uid = m.from_user.id
    uname = m.from_user.username or "no_username"
    is_adm = "✅ YES" if is_admin(uid) else "❌ NO"
    try:
        is_fj = "✅ JOINED" if is_user_joined(uid) else "❌ NOT JOINED"
    except:
        is_fj = "⚠️ ERROR"
    admins_list = "\n".join(f"  {i}. <code>{a}</code>" for i, a in enumerate(ADMIN_IDS, 1)) or "  <i>none</i>"
    bot.reply_to(
        m,
        f"🆔 <b>Your Telegram Info</b>\n\n"
        f"<b>Your ID:</b> <code>{uid}</code>\n"
        f"<b>Username:</b> @{esc(uname)}\n"
        f"<b>Admin?:</b> {is_adm}\n"
        f"<b>Force Join:</b> {is_fj}\n"
        f"<b>FJ Active:</b> {_FJ_ACTIVE}\n\n"
        f"<b>Admins ({len(ADMIN_IDS)}):</b>\n{admins_list}",
        parse_mode='HTML'
    )

@bot.message_handler(commands=['fjdebug'])
def cmd_fjdebug(m):
    if not is_admin(m.from_user.id): return
    if m.chat.type != 'private': return
    bot.reply_to(m, force_join_status_text(), parse_mode='HTML')

@bot.message_handler(commands=['fjreload'])
def cmd_fjreload(m):
    if not is_admin(m.from_user.id): return
    if m.chat.type != 'private': return
    _validate_fj_channels_startup()
    bot.reply_to(m, "🔄 Reloaded.\n\n" + force_join_status_text(), parse_mode='HTML')

# ⭐⭐⭐ CRITICAL: /start with FORCE JOIN FIRST ⭐⭐⭐
@bot.message_handler(commands=['start'])
def cmd_start(m):
    if m.chat.type != 'private':
        return

    uid = m.from_user.id

    # Referral handling
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

    # ⭐ FORCE JOIN CHECK FIRST — send ONLY force join prompt
    if not is_user_joined(uid):
        # Only send force join prompt, NO welcome
        send_force_join_prompt(m.chat.id, uid)
        return

    # Force join passed (or not active) → send welcome
    send_welcome(m.chat.id, uid)

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
    credits_display = '♾️' if is_admin(uid) else user.get('credits', 0)
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
    if not ensure_joined(m.from_user.id, m.chat.id, m.message_id):
        return
    bot.reply_to(
        m,
        f"🛒 <b>Buy Credits</b>\n\nContact: {esc(ADMIN_USERNAME)}\n\n"
        f"💎 1 search = {SEARCH_COST} credits",
        parse_mode='HTML'
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ About" and m.chat.type == 'private')
def btn_about(m):
    bot.reply_to(m, f"ℹ️ Username Info Bot\n{esc(BOT_USERNAME)}")

@bot.message_handler(func=lambda m: m.text == "👑 Admin Panel" and m.chat.type == 'private' and is_admin(m.from_user.id))
def btn_admin(m):
    bot.reply_to(m, "👑 <b>Admin Panel</b>", parse_mode='HTML', reply_markup=admin_kb())

@bot.message_handler(func=lambda m: m.text == "📊 Dashboard" and m.chat.type == 'private' and is_admin(m.from_user.id))
def btn_dashboard(m):
    admins_list = "\n".join(f"  {i}. <code>{a}</code>" for i, a in enumerate(ADMIN_IDS, 1))
    txt = (
        f"📊 <b>Dashboard</b>\n\n"
        f"👥 Total Users: <b>{total_users()}</b>\n"
        f"🔥 Active (24h): <b>{active_users_24h()}</b>\n"
        f"🔍 Total Searches: <b>{total_searches()}</b>\n"
        f"📅 Searches Today: <b>{searches_today()}</b>\n\n"
        f"🔒 Force Join: <b>{'🟢 ON' if _FJ_ACTIVE else '🔴 OFF'}</b>\n"
        f"📢 Active Channels: <b>{len(_FJ_VALID_CHANNELS)}</b>\n\n"
        f"👑 Admins ({len(ADMIN_IDS)}):\n{admins_list}"
    )
    bot.reply_to(m, txt, parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and m.chat.type == 'private' and is_admin(m.from_user.id))
def btn_broadcast(m):
    msg = bot.reply_to(m, "Send the message to broadcast to all users:")
    bot.register_next_step_handler(msg, do_broadcast)

def do_broadcast(m):
    if m.text in ALL_BUTTONS:
        bot.reply_to(m, "❌ Broadcast cancelled."); return
    text = m.text
    if not text: return
    safe_text = esc(text)
    success = 0
    for uid_str in list(users.keys()):
        try:
            bot.send_message(int(uid_str), safe_text, parse_mode='HTML')
            success += 1
            time.sleep(0.05)
        except: pass
    bot.reply_to(m, f"✅ Broadcast sent to {success}/{len(users)} users.")

@bot.message_handler(func=lambda m: m.text == "🔙 Back to Menu" and m.chat.type == 'private' and is_admin(m.from_user.id))
def btn_back(m):
    bot.reply_to(m, "🏠 Main Menu", reply_markup=main_kb(m.from_user.id))

@bot.message_handler(func=lambda m: m.text == "🔗 Force Join" and m.chat.type == 'private' and is_admin(m.from_user.id))
def btn_force_join(m):
    bot.reply_to(m, force_join_status_text(), parse_mode='HTML')

@bot.message_handler(func=lambda m: m.text == "💰 Credit Manager" and m.chat.type == 'private' and is_admin(m.from_user.id))
def btn_credit_mgr(m):
    bot.reply_to(m, "💰 <b>Credit Manager</b>\n\nChoose an action:", parse_mode='HTML', reply_markup=credit_mgr_kb())

@bot.message_handler(func=lambda m: m.text == "➕ Add Credits" and m.chat.type == 'private' and is_admin(m.from_user.id))
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

@bot.message_handler(func=lambda m: m.text == "➖ Remove Credits" and m.chat.type == 'private' and is_admin(m.from_user.id))
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

@bot.message_handler(func=lambda m: m.text == "💰 Set Credits" and m.chat.type == 'private' and is_admin(m.from_user.id))
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

@bot.message_handler(func=lambda m: m.text == "👤 Check User" and m.chat.type == 'private' and is_admin(m.from_user.id))
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

@bot.message_handler(func=lambda m: m.text == "🔙 Admin Menu" and m.chat.type == 'private' and is_admin(m.from_user.id))
def btn_admin_menu(m):
    bot.reply_to(m, "👑 <b>Admin Panel</b>", parse_mode='HTML', reply_markup=admin_kb())

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
    logger.info("=" * 55)
    logger.info("🚀 STARTING BOT v9 FORCE JOIN FIRST")
    logger.info(f"👑 Total Admins: {len(ADMIN_IDS)}")
    for i, aid in enumerate(ADMIN_IDS, 1):
        logger.info(f"   [{i}] {aid}")
    logger.info(f"🔗 FORCE_JOIN_ENABLED (env): {_FJ_ENABLED}")
    logger.info(f"📢 FORCE_JOIN_CHANNELS (env): {len(_FJ_CHANNELS)}")
    logger.info("=" * 55)

    logger.info("🔍 Validating force join channels...")
    _validate_fj_channels_startup()
    logger.info(f"🔒 Force Join Runtime: {'ACTIVE' if _FJ_ACTIVE else 'INACTIVE'}")
    logger.info("=" * 55)

    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.critical(f"Crashed: {e}")
