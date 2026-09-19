"""
Username Info Bot — v17.2 FINAL
+ Pyrogram + Telethon multi-layer username resolver
+ Cache + advanced admin panel
+ Smooth animations everywhere
"""
import os, sys, subprocess, time, re, json, threading, html, csv, io, asyncio
import logging
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════════════
#  AUTO-INSTALL
# ══════════════════════════════════════════════════════════════
_PACKAGES = {
    "telebot":  "pyTelegramBotAPI==4.14.0",
    "dotenv":   "python-dotenv==1.0.0",
    "pyrogram": "pyrogram==2.0.106",
    "telethon": "telethon==1.34.0",
}
def _ensure_modules():
    import importlib.util
    miss = []
    for m, p in _PACKAGES.items():
        if importlib.util.find_spec(m) is None:
            miss.append((m, p))
    # TgCrypto is optional but recommended
    if importlib.util.find_spec("tgcrypto") is None:
        miss.append(("tgcrypto", "TgCrypto==1.2.5"))
    if not miss:
        print("✅ All modules present", flush=True); return
    print(f"⚠️ Installing: {[m[0] for m in miss]}", flush=True)
    for mod, pkg in miss:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install",
                                   "--no-cache-dir", pkg],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"✅ {pkg}", flush=True)
        except Exception as e:
            print(f"⚠️ {pkg}: {e} (continuing)", flush=True)
_ensure_modules()

try:
    from dotenv import load_dotenv; load_dotenv()
except Exception: pass

import urllib.request, urllib.error, ssl
import telebot
from telebot.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("bot.log", encoding='utf-8'),
              logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("uinfo_v17_2")

# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════
def _clean_env(key, default=""):
    val = os.getenv(key, default)
    if val is None: return default
    val = str(val).strip().replace("\n","").replace("\r","").replace("\\n","")
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        val = val[1:-1]
    return val

BOT_TOKEN      = _clean_env("BOT_TOKEN")
BOT_USERNAME   = _clean_env("BOT_USERNAME", "@YourBot").lstrip("@")
ADMIN_USERNAME = _clean_env("ADMIN_USERNAME", "@admin")
API_URL        = _clean_env("TG2NUM_API_URL", "https://tg2num-botadminshere.vercel.app/?id=")
DATA_FILE      = _clean_env("DATA_FILE", "data.json")

# Pyrogram
PYRO_API_ID   = _clean_env("PYRO_API_ID")
PYRO_API_HASH = _clean_env("PYRO_API_HASH")
PYRO_SESSION  = _clean_env("PYRO_SESSION")

# Telethon
TG_API_ID      = _clean_env("TG_API_ID")
TG_API_HASH    = _clean_env("TG_API_HASH")
TG_SESSION_STR = _clean_env("TG_SESSION_STRING")

USERNAME_RESOLVER = _clean_env("USERNAME_RESOLVER", "bot_first").lower()

try:
    SEARCH_COST        = int(_clean_env("SEARCH_COST", "2"))
    SIGNUP_BONUS       = int(_clean_env("SIGNUP_BONUS", "5"))
    REFERRAL_BONUS     = int(_clean_env("REFERRAL_BONUS", "3"))
    DAILY_FREE_CREDITS = int(_clean_env("DAILY_FREE_CREDITS", "1"))
except ValueError as e:
    logger.critical(f"❌ Bad numeric config: {e}"); sys.exit(1)

def _load_admin_ids():
    ids = []
    multi = _clean_env("ADMIN_IDS")
    if multi:
        for x in multi.split(","):
            x = x.strip()
            if x.isdigit():
                uid = int(x)
                if uid not in ids: ids.append(uid)
    for k in ["ADMIN_ID"] + [f"ADMIN_ID_{i}" for i in range(2, 11)]:
        v = _clean_env(k)
        if v:
            try:
                uid = int(v)
                if uid not in ids: ids.append(uid)
            except ValueError: logger.warning(f"Bad {k}: {v}")
    return ids
ADMIN_IDS = _load_admin_ids()

if not BOT_TOKEN:  logger.critical("❌ BOT_TOKEN missing"); sys.exit(1)
if not ADMIN_IDS:  logger.critical("❌ No ADMIN_ID configured"); sys.exit(1)

def _load_fj_env():
    enabled = _clean_env("FORCE_JOIN_ENABLED", "false").lower() in ("true","1","yes","on")
    channels = []
    for i in range(1, 11):
        cid  = _clean_env(f"FORCE_JOIN_CHANNEL_{i}")
        link = _clean_env(f"FORCE_JOIN_LINK_{i}")
        if cid:
            if not link and cid.startswith("@"):
                link = f"https://t.me/{cid.lstrip('@')}"
            channels.append({"channel": cid, "link": link})
    return enabled, channels
_FJ_ENABLED, _FJ_CHANNELS_ENV = _load_fj_env()

# ══════════════════════════════════════════════════════════════
#  HTTP
# ══════════════════════════════════════════════════════════════
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

def http_get_json(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Bot/1.0)", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as r:
            code = r.status
            raw  = r.read().decode("utf-8", errors="replace")
        try: return code, json.loads(raw), None
        except json.JSONDecodeError as e: return code, None, f"Bad JSON: {e}"
    except urllib.error.HTTPError as e: return e.code, None, f"HTTP {e.code}"
    except urllib.error.URLError as e:   return 0, None, f"URL: {e.reason}"
    except Exception as e:               return 0, None, str(e)

# ══════════════════════════════════════════════════════════════
#  DATA
# ══════════════════════════════════════════════════════════════
def _default_data():
    return {
        "users": {}, "banned": [],
        "settings": {"maintenance": False, "maintenance_msg": "", "api_enabled": True},
        "stats": {"total_searches": 0, "searches_today": 0, "last_date": ""},
        "dynamic_admins": [], "dynamic_fj": [],
        "activity_log": [], "daily_claims": {},
        "username_cache": {},
        "cache_stats": {"hits": 0, "misses": 0, "bot_chat": 0,
                        "telethon": 0, "pyrogram": 0, "numeric": 0},
    }

def load_data():
    d = _default_data()
    if not os.path.exists(DATA_FILE): return d
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            j = json.load(f)
        if not isinstance(j, dict): raise ValueError("root not dict")
        for k in d: j.setdefault(k, d[k])
        return j
    except Exception as e:
        logger.error(f"Corrupt data, resetting: {e}"); return d

data = load_data()
users    = data["users"]
banned   = set(data.get("banned", []))
settings = data.setdefault("settings", {"maintenance": False})
stats    = data["stats"]
dynamic_admins = data.setdefault("dynamic_admins", [])
dynamic_fj     = data.setdefault("dynamic_fj", [])
activity_log   = data.setdefault("activity_log", [])
daily_claims   = data.setdefault("daily_claims", {})
username_cache = data.setdefault("username_cache", {})
cache_stats    = data.setdefault("cache_stats",
    {"hits": 0, "misses": 0, "bot_chat": 0, "telethon": 0, "pyrogram": 0, "numeric": 0})
_data_lock = threading.RLock()

def save_data():
    with _data_lock:
        try:
            tmp = DATA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, DATA_FILE)
        except Exception as e: logger.error(f"save: {e}")

def log_action(action, admin_id=None, details=""):
    entry = {"ts": datetime.now().isoformat(),
             "admin": admin_id or "system", "action": action,
             "details": str(details)[:200]}
    with _data_lock:
        activity_log.append(entry)
        if len(activity_log) > 500: activity_log[:] = activity_log[-500:]
        save_data()

def get_all_admins():
    ids = list(ADMIN_IDS)
    for x in dynamic_admins:
        try:
            v = int(x)
            if v not in ids: ids.append(v)
        except: pass
    return ids

def is_admin(uid): return uid in get_all_admins()

def get_all_fj():
    return list(_FJ_CHANNELS_ENV) + list(dynamic_fj)

# ─── Cache ───────────────────────────────────────────────────
CACHE_TTL_SECONDS = 86400
CACHE_MAX_ENTRIES = 5000
CACHE_KEEP_ENTRIES = 2500

def _cache_get(uname):
    uname = uname.lower()
    with _data_lock:
        e = username_cache.get(uname)
        if not e: return None, None
        try:
            ts = datetime.fromisoformat(e.get("ts", ""))
            if (datetime.now() - ts).total_seconds() > CACHE_TTL_SECONDS:
                del username_cache[uname]; save_data()
                return None, None
        except: return None, None
        return e.get("id"), e.get("source", "cache")

def _cache_set(uname, uid, source):
    uname = uname.lower()
    with _data_lock:
        username_cache[uname] = {"id": int(uid),
            "ts": datetime.now().isoformat(), "source": source}
        if len(username_cache) > CACHE_MAX_ENTRIES:
            items = sorted(username_cache.items(),
                           key=lambda kv: kv[1].get("ts", ""),
                           reverse=True)[:CACHE_KEEP_ENTRIES]
            username_cache.clear(); username_cache.update(dict(items))
        save_data()

def _cache_stats_inc(key, by=1):
    with _data_lock:
        cache_stats[key] = cache_stats.get(key, 0) + by

# ─── Users ───────────────────────────────────────────────────
def get_user(uid, create=True):
    k = str(uid)
    with _data_lock:
        if k not in users and create:
            users[k] = {
                "credits": SIGNUP_BONUS, "searches": 0, "referrals": 0,
                "referred_by": None, "banned": False,
                "last_daily_claim": "", "joined_at": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "first_name": "", "username": "", "total_searches": 0,
                "spent_credits": 0, "earned_credits": SIGNUP_BONUS}
            save_data()
        return users.get(k)

def is_banned(uid): return str(uid) in banned
def ban_user(uid):
    with _data_lock:
        banned.add(str(uid)); data["banned"] = list(banned); save_data()
def unban_user(uid):
    with _data_lock:
        banned.discard(str(uid)); data["banned"] = list(banned); save_data()

def add_credits(uid, amount):
    with _data_lock:
        u = get_user(uid)
        u["credits"] = max(0, u.get("credits", 0) + amount)
        if amount > 0: u["earned_credits"] = u.get("earned_credits", 0) + amount
        else: u["spent_credits"] = u.get("spent_credits", 0) + abs(amount)
        save_data(); return u["credits"]

def set_credits(uid, value):
    with _data_lock:
        u = get_user(uid); u["credits"] = max(0, int(value)); save_data()

def get_credits(uid): return users.get(str(uid), {}).get("credits", 0)

def deduct_credits(uid, amount):
    with _data_lock:
        u = users.get(str(uid))
        if not u or u.get("credits", 0) < amount: return False
        u["credits"] -= amount
        u["spent_credits"] = u.get("spent_credits", 0) + amount
        save_data(); return True

def incr_searches(uid):
    today = datetime.now().strftime("%Y-%m-%d")
    with _data_lock:
        u = users.get(str(uid))
        if u:
            u["searches"] = u.get("searches", 0) + 1
            u["total_searches"] = u.get("total_searches", 0) + 1
        if stats.get("last_date") != today:
            stats["last_date"] = today; stats["searches_today"] = 0
        stats["total_searches"] = stats.get("total_searches", 0) + 1
        stats["searches_today"] = stats.get("searches_today", 0) + 1
        save_data()

def total_users(): return len(users)
def active_users_24h():
    cutoff = datetime.now() - timedelta(hours=24)
    n = 0
    for u in users.values():
        try:
            if datetime.fromisoformat(u.get("last_seen","")) >= cutoff: n += 1
        except: pass
    return n
def total_searches(): return stats.get("total_searches", 0)
def searches_today():
    if stats.get("last_date") != datetime.now().strftime("%Y-%m-%d"): return 0
    return stats.get("searches_today", 0)

def handle_referral(new_uid, referrer_id):
    try:
        if int(new_uid) == int(referrer_id): return False
    except: return False
    if is_banned(referrer_id): return False
    ns, rs = str(new_uid), str(referrer_id)
    with _data_lock:
        if ns not in users: get_user(new_uid)
        if users[ns].get("referred_by") is not None: return False
        if rs not in users: get_user(referrer_id)
        users[ns]["referred_by"] = referrer_id
        users[rs]["credits"] = users[rs].get("credits", 0) + REFERRAL_BONUS
        users[rs]["earned_credits"] = users[rs].get("earned_credits", 0) + REFERRAL_BONUS
        users[rs]["referrals"] = users[rs].get("referrals", 0) + 1
        save_data(); return True

def claim_daily(uid):
    today = datetime.now().strftime("%Y-%m-%d")
    tomorrow = (datetime.now() + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    secs_left = int((tomorrow - datetime.now()).total_seconds())
    with _data_lock:
        u = get_user(uid)
        if u.get("last_daily_claim") == today:
            return False, 0, secs_left
        u["last_daily_claim"] = today
        u["credits"] = u.get("credits", 0) + DAILY_FREE_CREDITS
        u["earned_credits"] = u.get("earned_credits", 0) + DAILY_FREE_CREDITS
        daily_claims[today] = daily_claims.get(today, 0) + 1
        save_data()
        return True, DAILY_FREE_CREDITS, 0

def daily_status(uid):
    today = datetime.now().strftime("%Y-%m-%d")
    u = users.get(str(uid), {})
    claimed = u.get("last_daily_claim") == today
    tomorrow = (datetime.now() + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return claimed, int((tomorrow - datetime.now()).total_seconds())

# ══════════════════════════════════════════════════════════════
#  BOT
# ══════════════════════════════════════════════════════════════
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
try: bot.remove_webhook()
except: pass

BOT_ID = None
def _init_bot_id():
    global BOT_ID
    try:
        me = bot.get_me()
        BOT_ID = me.id
        logger.info(f"🤖 Bot: @{me.username} (id={BOT_ID})")
        return True
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 401:
            logger.critical("🚨 BOT TOKEN INVALID (401)")
        else: logger.warning(f"get_me fail: {e}")
        return False
    except Exception as e:
        logger.warning(f"get_me fail: {e}"); return False

# ══════════════════════════════════════════════════════════════
#  PYROGRAM RESOLVER
# ══════════════════════════════════════════════════════════════
_pyro_loop = None
_pyro_client = None
_pyro_ready = False
_pyro_me = None

def _init_pyrogram():
    global _pyro_loop, _pyro_client, _pyro_ready, _pyro_me
    if not (PYRO_API_ID and PYRO_API_HASH and PYRO_SESSION):
        logger.warning("🔥 Pyrogram: creds missing — disabled")
        return False
    try:
        from pyrogram import Client
    except ImportError:
        logger.error("❌ Pyrogram library not installed"); return False

    async def _start():
        try:
            client = Client(
                name="resolver",
                api_id=int(PYRO_API_ID),
                api_hash=PYRO_API_HASH,
                session_string=PYRO_SESSION,
                in_memory=True,
                no_updates=True,
            )
            await client.start()
            me = await client.get_me()
            logger.info(f"🔥 Pyrogram: @{me.username} (id={me.id})")
            return client, me
        except Exception as e:
            logger.error(f"❌ Pyrogram connect error: {e}")
            return None, None

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_start())
        if not result or not result[0]:
            loop.close(); return False
        client, me = result

        def _run_loop():
            asyncio.set_event_loop(loop)
            loop.run_forever()
        threading.Thread(target=_run_loop, daemon=True).start()

        _pyro_loop = loop
        _pyro_client = client
        _pyro_me = me
        _pyro_ready = True
        return True
    except Exception as e:
        logger.error(f"❌ Pyrogram init failed: {e}"); return False

def resolve_username_via_pyrogram(uname):
    if not _pyro_ready: return None, "Pyrogram unavailable"
    async def _resolve():
        try:
            user = await asyncio.wait_for(
                _pyro_client.get_users(uname), timeout=12)
            if user and hasattr(user, "id"):
                return int(user.id), None
            return None, "No user found"
        except asyncio.TimeoutError:
            return None, "Timeout (12s)"
        except Exception as e:
            msg = str(e)
            if "USERNAME_NOT_OCCUPIED" in msg:
                return None, "Username exist nahi karta"
            if "USERNAME_INVALID" in msg:
                return None, "Invalid username"
            if "USERNAME_PURCHASE_AVAILABLE" in msg:
                return None, "Username available hai (koi use nahi karta)"
            if "FLOOD_WAIT" in msg:
                return None, "Telegram rate limit — thodi der baad try karo"
            return None, msg[:80]
    try:
        fut = asyncio.run_coroutine_threadsafe(_resolve(), _pyro_loop)
        return fut.result(timeout=15)
    except Exception as e:
        return None, str(e)[:80]

# ══════════════════════════════════════════════════════════════
#  TELETHON RESOLVER (optional fallback)
# ══════════════════════════════════════════════════════════════
_tg_loop = None
_tg_client = None
_tg_ready = False
_tg_me = None

def _init_telethon():
    global _tg_loop, _tg_client, _tg_ready, _tg_me
    if not (TG_API_ID and TG_API_HASH and TG_SESSION_STR):
        logger.info("📱 Telethon: creds missing — disabled")
        return False
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        logger.error("Telethon not installed"); return False

    async def _start():
        try:
            client = TelegramClient(StringSession(TG_SESSION_STR),
                                    int(TG_API_ID), TG_API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                logger.error("Telethon: not authorized")
                await client.disconnect(); return None, None
            me = await client.get_me()
            logger.info(f"📱 Telethon: @{me.username} (id={me.id})")
            return client, me
        except Exception as e:
            logger.error(f"Telethon connect error: {e}")
            return None, None

    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_start())
        if not result or not result[0]:
            loop.close(); return False
        client, me = result
        def _run_loop():
            asyncio.set_event_loop(loop); loop.run_forever()
        threading.Thread(target=_run_loop, daemon=True).start()
        _tg_loop = loop; _tg_client = client; _tg_me = me; _tg_ready = True
        return True
    except Exception as e:
        logger.error(f"Telethon init failed: {e}"); return False

def resolve_username_via_telethon(uname):
    if not _tg_ready: return None, "Telethon unavailable"
    async def _resolve():
        try:
            entity = await asyncio.wait_for(
                _tg_client.get_entity(f"@{uname}"), timeout=12)
            uid = getattr(entity, "id", None)
            if uid: return int(uid), None
            return None, "No ID returned"
        except asyncio.TimeoutError:
            return None, "Timeout (12s)"
        except Exception as e:
            return None, str(e)[:80]
    try:
        fut = asyncio.run_coroutine_threadsafe(_resolve(), _tg_loop)
        return fut.result(timeout=15)
    except Exception as e:
        return None, str(e)[:80]

# ══════════════════════════════════════════════════════════════
#  ANIMATION ENGINE
# ══════════════════════════════════════════════════════════════
SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
SPINNER2 = ["◐","◓","◑","◒"]
SPINNER3 = ["⣾","⣽","⣻","⢿","⡿","⣟","⣯","⣷"]
DOTS    = ["", " .", " ..", " ...", " ...."]

def esc(s):
    if s is None: return ""
    return html.escape(str(s), quote=False)

def typing(cid, secs=1.2):
    def _run():
        try:
            end = time.time() + secs
            while time.time() < end:
                bot.send_chat_action(cid, 'typing')
                time.sleep(min(4, max(0.5, end - time.time())))
        except: pass
    threading.Thread(target=_run, daemon=True).start()

def progress_bar(pct, w=12):
    pct = max(0, min(100, int(pct)))
    f = int(w * pct / 100)
    return "▰"*f + "▱"*(w-f) + f" {pct}%"

class AnimMsg:
    def __init__(self, cid, *frames, interval=0.35, reply_to=None, parse_mode="HTML"):
        self.cid=cid; self.frames=[f for f in frames if f]
        self.interval=interval; self.mid=None
        self._stop=threading.Event(); self._t=None
        self._reply=reply_to; self._deleted=False
        self._lock=threading.Lock(); self.parse_mode=parse_mode

    def start(self):
        if not self.frames: return False
        try:
            kw={"parse_mode": self.parse_mode}
            if self._reply: kw["reply_to_message_id"]=self._reply
            m = bot.send_message(self.cid, self.frames[0], **kw)
            self.mid = m.message_id
            self._t = threading.Thread(target=self._run, daemon=True)
            self._t.start(); return True
        except Exception as e:
            logger.warning(f"anim start: {e}"); return False

    def _run(self):
        i=1; last=self.frames[0]
        while not self._stop.is_set():
            if self._deleted or self.mid is None: return
            txt = self.frames[i % len(self.frames)]
            if txt != last:
                try:
                    with self._lock:
                        if self._deleted: return
                        bot.edit_message_text(txt, self.cid, self.mid,
                                              parse_mode=self.parse_mode)
                    last = txt
                except Exception as e:
                    if "not modified" not in str(e).lower(): time.sleep(0.35)
            i += 1
            w=0
            while w < self.interval:
                if self._stop.is_set(): return
                time.sleep(0.07); w += 0.07

    def stop(self):
        self._stop.set()
        if self._t:
            try: self._t.join(timeout=2)
            except: pass

    def edit(self, text, mark=None):
        with self._lock:
            if self._deleted or self.mid is None:
                try:
                    m = bot.send_message(self.cid, text,
                                         parse_mode=self.parse_mode, reply_markup=mark)
                    self.mid = m.message_id
                except: pass
                return
            try:
                bot.edit_message_text(text, self.cid, self.mid,
                                      parse_mode=self.parse_mode, reply_markup=mark)
            except Exception as e:
                if "not modified" in str(e).lower():
                    try: bot.edit_message_reply_markup(self.cid, self.mid, reply_markup=mark)
                    except: pass
                    return
                try:
                    m = bot.send_message(self.cid, text,
                                         parse_mode=self.parse_mode, reply_markup=mark)
                    self.mid = m.message_id
                except: pass

    def delete(self):
        self.stop(); self._deleted = True
        if self.mid is None: return
        try: bot.delete_message(self.cid, self.mid)
        except: pass

def reveal_lines(cid, lines, interval=0.22, reply_to=None, final_markup=None):
    if not lines: return None
    try:
        kw = {"parse_mode": "HTML"}
        if reply_to: kw["reply_to_message_id"] = reply_to
        m = bot.send_message(cid, lines[0], **kw)
        mid = m.message_id
    except Exception as e:
        logger.warning(f"reveal: {e}"); return None
    if len(lines) == 1:
        if final_markup:
            try: bot.edit_message_reply_markup(cid, mid, reply_markup=final_markup)
            except: pass
        return mid
    acc = lines[0]
    for i, line in enumerate(lines[1:], 1):
        time.sleep(interval)
        acc += "\n" + line
        mk = final_markup if i == len(lines) - 1 else None
        try:
            bot.edit_message_text(acc, cid, mid, parse_mode="HTML", reply_markup=mk)
        except: pass
    return mid

def flash(cid, text, reply_to=None, times=2):
    try:
        kw = {"parse_mode": "HTML"}
        if reply_to: kw["reply_to_message_id"] = reply_to
        m = bot.send_message(cid, text, **kw)
        mid = m.message_id
        for _ in range(times):
            for p in ["✨ ", "⚡ ", "💫 ", ""]:
                try: bot.edit_message_text(p + text, cid, mid, parse_mode="HTML")
                except: pass
                time.sleep(0.09)
        return mid
    except: return None

def error_shake(cid, text, reply_to=None, cycles=3):
    try:
        kw = {"parse_mode": "HTML"}
        if reply_to: kw["reply_to_message_id"] = reply_to
        m = bot.send_message(cid, text, **kw)
        mid = m.message_id
        for i in range(cycles):
            for p in ["💥 ", "⚠️ ", "❗ ", "🚫 ", "❌ "]:
                try: bot.edit_message_text(p + text, cid, mid, parse_mode="HTML")
                except: pass
                time.sleep(0.06)
        try: bot.edit_message_text("❌ " + text, cid, mid, parse_mode="HTML")
        except: pass
        return mid
    except: return None

def animate_credit(cid, old, new, reply_to=None):
    delta = new - old
    arrow = "📈" if delta >= 0 else "📉"
    sign  = "+" if delta >= 0 else ""
    steps = 10
    try:
        kw = {"parse_mode": "HTML"}
        if reply_to: kw["reply_to_message_id"] = reply_to
        m = bot.send_message(cid, f"{arrow} <b>Updating credits…</b>", **kw)
        mid = m.message_id
        for i in range(1, steps + 1):
            cur = old + int((new - old) * i / steps)
            bar = progress_bar(int(i * 100 / steps), 10)
            try:
                bot.edit_message_text(
                    f"{arrow} <b>Credits: {cur}</b>\n<code>{bar}</code>\n<i>({sign}{delta})</i>",
                    cid, mid, parse_mode="HTML")
            except: pass
            time.sleep(0.08)
        time.sleep(0.35)
        try: bot.delete_message(cid, mid)
        except: pass
    except: pass

# ─── Frame builders ─────────────────────────────────────────
def frames_search(display=""):
    out = []
    for s in SPINNER[:6]:
        out.append(f"<b>{s} Connecting…</b>\n<code>{progress_bar(8)}</code>")
    for i, pct in enumerate(range(18, 48, 6)):
        out.append(f"<b>🔍 Searching</b> <code>{esc(display)}</code>{DOTS[i%5]}\n<code>{progress_bar(pct)}</code>")
    for i, pct in enumerate(range(55, 90, 6)):
        out.append(f"<b>📡 Fetching data</b>{DOTS[i%5]}\n<code>{progress_bar(pct)}</code>")
    for s in SPINNER3[:4]:
        out.append(f"<b>{s} Processing…</b>\n<code>{progress_bar(96)}</code>")
    out.append(f"<b>✅ Ready!</b>\n<code>{progress_bar(100)}</code>")
    return out

def frames_resolve(username=""):
    out = []
    u = esc(username)
    for s in SPINNER[:6]:
        out.append(f"<b>{s} Contacting Telegram…</b>\n"
                   f"<i>Query: {u}</i>\n<code>{progress_bar(12)}</code>")
    for i, pct in enumerate(range(22, 52, 5)):
        out.append(f"<b>🔎 Resolving username</b>{DOTS[i%5]}\n"
                   f"<i>{u}</i>\n<code>{progress_bar(pct)}</code>")
    for s in SPINNER2:
        out.append(f"<b>{s} Scanning sources…</b>\n"
                   f"<i>{u}</i>\n<code>{progress_bar(58)}</code>")
    for i, pct in enumerate(range(65, 92, 5)):
        out.append(f"<b>🔄 Converting to ID</b>{DOTS[i%5]}\n"
                   f"<i>{u}</i>\n<code>{progress_bar(pct)}</code>")
    for s in SPINNER3[:4]:
        out.append(f"<b>{s} Finalizing…</b>\n"
                   f"<i>{u}</i>\n<code>{progress_bar(97)}</code>")
    out.append(f"<b>✅ Resolved!</b>\n<code>{progress_bar(100)}</code>")
    return out

def frames_welcome_art():
    return ["┌──────────────────┐\n│  ◌  L O A D I N G  ◌  │\n└──────────────────┘",
            "┌──────────────────┐\n│  ◐  V E R I F Y  ◐  │\n└──────────────────┘",
            "┌──────────────────┐\n│  ◓  C O N N E C T  ◓  │\n└──────────────────┘",
            "┌──────────────────┐\n│  ◉  R E A D Y  ◉  │\n└──────────────────┘",
            "✨  W E L C O M E  ✨"]

def frames_profile_load():
    return ["📂 <b>Opening profile</b>",
            "📂 <b>Opening profile</b> .",
            "📂 <b>Opening profile</b> ..",
            "📂 <b>Opening profile</b> ...",
            "📁 <b>Reading data</b> .",
            "📁 <b>Reading data</b> ..",
            "📁 <b>Reading data</b> ..."]

def frames_refer():
    return ["🔗 <b>Generating link</b>",
            "🔗 <b>Generating link</b> .",
            "🔗 <b>Generating link</b> ..",
            "🔗 <b>Generating link</b> ...",
            "⚙️ <b>Encoding ref_id</b> ..",
            "⚡ <b>Finalizing</b> ..."]

def frames_fj_check():
    return [f"🔎 <b>Verifying</b>{DOTS[i%5]}\n<code>{progress_bar(10 + i*14)}</code>"
            for i in range(7)]

def frames_buy_pulse():
    return ["🛒 <b>B U Y   C R E D I T S</b>\n<i>loading…</i>",
            "🛒 <b>B U Y   C R E D I T S</b>\n<i>loading. </i>",
            "🛒 <b>B U Y   C R E D I T S</b>\n<i>loading.. </i>",
            "🛒 <b>B U Y   C R E D I T S</b>\n<i>loading... </i>"]

def frames_daily_chest():
    return ["🎁 <b>Opening daily chest</b>",
            "🎁 <b>Opening daily chest</b> .",
            "🎁 <b>Opening daily chest</b> ..",
            "🎁 <b>Opening daily chest</b> ...",
            "✨ <b>Reward incoming</b> ✨",
            "💫 <b>Reward incoming</b> 💫"]

# ══════════════════════════════════════════════════════════════
#  FORCE JOIN
# ══════════════════════════════════════════════════════════════
_FJ_ACTIVE = False
_FJ_VALID  = []
_FJ_INVALID= []

def _validate_fj():
    global _FJ_ACTIVE, _FJ_VALID, _FJ_INVALID
    all_ch = get_all_fj()
    if not _FJ_ENABLED and not dynamic_fj:
        _FJ_ACTIVE=False; _FJ_VALID=[]; _FJ_INVALID=list(all_ch)
        logger.info("🔓 FJ DISABLED"); return
    if not all_ch:
        _FJ_ACTIVE=False; _FJ_VALID=[]; _FJ_INVALID=[]; return
    if not BOT_ID:
        logger.error("FJ: BOT_ID unknown"); _FJ_ACTIVE=False; return
    valid, invalid = [], []
    for ch in all_ch:
        cid = ch.get("channel")
        try:
            m = bot.get_chat_member(cid, BOT_ID)
            st = getattr(m, "status", "")
            if st in ("administrator","creator"):
                valid.append(ch); logger.info(f"  ✅ {cid} ({st})")
            else:
                invalid.append(ch); logger.warning(f"  ❌ {cid} ({st})")
        except Exception as e:
            invalid.append(ch); logger.warning(f"  ❌ {cid}: {e}")
    _FJ_VALID, _FJ_INVALID = valid, invalid
    _FJ_ACTIVE = bool(valid)
    logger.info(f"🔒 FJ {'ACTIVE' if _FJ_ACTIVE else 'INACTIVE'} — {len(valid)} valid")

def is_user_joined(uid):
    if not _FJ_ACTIVE: return True
    if is_admin(uid): return True
    if not _FJ_VALID: return True
    errors = 0
    for ch in _FJ_VALID:
        cid = ch.get("channel")
        if not cid: continue
        try:
            m = bot.get_chat_member(cid, uid)
            st = getattr(m, "status", "")
            if st in ("member","administrator","creator"): continue
            if st == "restricted" and getattr(m, "is_member", False): continue
            return False
        except: errors += 1
    if errors and errors == len(_FJ_VALID): return False
    return True

def build_join_kb():
    kb = InlineKeyboardMarkup(row_width=1)
    for i, ch in enumerate(_FJ_VALID[:10], 1):
        link = ch.get("link")
        if link: kb.add(InlineKeyboardButton(f"📢 Join Channel {i}", url=link))
        else:    kb.add(InlineKeyboardButton(f"📢 Channel {i}", callback_data="noop"))
    kb.add(InlineKeyboardButton("✅ I've Joined All", callback_data="check_join"))
    return kb

def send_fj_prompt(cid, uid, reply_to=None):
    if not _FJ_VALID: return False
    try:
        kw = {"parse_mode":"HTML", "reply_markup": build_join_kb()}
        if reply_to: kw["reply_to_message_id"] = reply_to
        bot.send_message(cid,
            f"⚠️ <b>Force Join Required</b>\n\n"
            f"Bot use karne se pehle <b>{len(_FJ_VALID)}</b> channel(s) join karein.\n"
            f"Phir <b>✅ I've Joined All</b> dabayein.", **kw)
        return True
    except Exception as e:
        logger.error(f"FJ prompt: {e}"); return False

def ensure_joined(uid, cid, reply_to=None, is_group=False):
    if is_user_joined(uid): return True
    if is_group:
        dm = send_fj_prompt(uid, uid)
        try:
            msg = ("⚠️ Pehle <b>DM</b> mein verify karein — bot ne msg bheja hai."
                   if dm else "⚠️ Pehle bot ko <b>DM mein /start</b> karein.")
            kw = {"parse_mode": "HTML"}
            if reply_to: kw["reply_to_message_id"] = reply_to
            bot.send_message(cid, msg, **kw)
        except: pass
        return False
    send_fj_prompt(cid, uid, reply_to); return False

def fj_status_text():
    lines = ["🔗 <b>Force Join Status</b>", "",
             f"Env Enabled: <b>{_FJ_ENABLED}</b>",
             f"Runtime Active: <b>{_FJ_ACTIVE}</b>",
             f"Dynamic Channels: <b>{len(dynamic_fj)}</b>", ""]
    if _FJ_VALID:
        lines.append(f"<b>✅ Active ({len(_FJ_VALID)}):</b>")
        for i, ch in enumerate(_FJ_VALID, 1):
            lines.append(f"  {i}. <code>{esc(ch.get('channel'))}</code>")
    else:
        lines.append("<i>No active channels</i>")
    if _FJ_INVALID:
        lines += ["", f"<b>❌ Invalid ({len(_FJ_INVALID)}):</b>"]
        for i, ch in enumerate(_FJ_INVALID, 1):
            lines.append(f"  {i}. <code>{esc(ch.get('channel'))}</code>")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════
#  KEYBOARDS
# ══════════════════════════════════════════════════════════════
def main_kb(uid):
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("🔒 TG to Info"),   KeyboardButton("🔗 Refer"))
    kb.row(KeyboardButton("🛒 Buy Credit"),   KeyboardButton("👤 Profile"))
    kb.row(KeyboardButton("🎁 Daily Bonus"),  KeyboardButton("ℹ️ About"))
    if is_admin(uid): kb.row(KeyboardButton("👑 Admin Panel"))
    return kb

def admin_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("📊 Dashboard"),     KeyboardButton("📈 Stats"))
    kb.row(KeyboardButton("📢 Broadcast"),     KeyboardButton("🎯 DM User"))
    kb.row(KeyboardButton("🔗 FJ Manager"),    KeyboardButton("🔐 Admin Manager"))
    kb.row(KeyboardButton("💰 Credit Manager"),KeyboardButton("👥 User Manager"))
    kb.row(KeyboardButton("🔍 Search User"),   KeyboardButton("🏆 Top Referrers"))
    kb.row(KeyboardButton("💾 Backup"),        KeyboardButton("📥 Restore"))
    kb.row(KeyboardButton("📜 Activity Log"),  KeyboardButton("⚙️ Settings"))
    kb.row(KeyboardButton("🔙 Back to Menu"))
    return kb

def credit_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("➕ Add Credits"),   KeyboardButton("➖ Remove Credits"))
    kb.row(KeyboardButton("💰 Set Credits"),   KeyboardButton("👤 Check User"))
    kb.row(KeyboardButton("💎 Bulk Add"),      KeyboardButton("🔄 Reset User"))
    kb.row(KeyboardButton("🔙 Admin Menu"))
    return kb

def user_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("📋 User List"),     KeyboardButton("🚫 Ban User"))
    kb.row(KeyboardButton("✅ Unban User"),    KeyboardButton("🚫 Banned List"))
    kb.row(KeyboardButton("📤 Export CSV"),    KeyboardButton("📊 User Details"))
    kb.row(KeyboardButton("🔙 Admin Menu"))
    return kb

def settings_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("🔧 Maintenance ON"), KeyboardButton("🔧 Maintenance OFF"))
    kb.row(KeyboardButton("🔄 Reload FJ"),      KeyboardButton("📊 FJ Status"))
    kb.row(KeyboardButton("💎 Eco Settings"),   KeyboardButton("🌐 API Toggle"))
    kb.row(KeyboardButton("🧹 Clear Cache"),    KeyboardButton("📦 Cache Stats"))
    kb.row(KeyboardButton("🔙 Admin Menu"))
    return kb

def fj_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("➕ Add FJ"),   KeyboardButton("➖ Remove FJ"))
    kb.row(KeyboardButton("📋 FJ List"),  KeyboardButton("🔄 Reload FJ"))
    kb.row(KeyboardButton("🔙 Admin Menu"))
    return kb

def admin_mgr_kb():
    kb = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.row(KeyboardButton("➕ Add Admin"),   KeyboardButton("➖ Remove Admin"))
    kb.row(KeyboardButton("📋 Admin List"),  KeyboardButton("🔙 Admin Menu"))
    return kb

_ALL_BUTTONS = {
    "🔒 TG to Info","🔗 Refer","🛒 Buy Credit","👤 Profile",
    "🎁 Daily Bonus","ℹ️ About","👑 Admin Panel",
    "📊 Dashboard","📈 Stats","📢 Broadcast","🎯 DM User",
    "🔗 FJ Manager","🔐 Admin Manager","💰 Credit Manager","👥 User Manager",
    "🔍 Search User","🏆 Top Referrers","💾 Backup","📥 Restore",
    "📜 Activity Log","⚙️ Settings",
    "🔙 Back to Menu","🔙 Admin Menu",
    "➕ Add Credits","➖ Remove Credits","💰 Set Credits","👤 Check User",
    "💎 Bulk Add","🔄 Reset User",
    "📋 User List","🚫 Ban User","✅ Unban User","🚫 Banned List",
    "📤 Export CSV","📊 User Details",
    "🔧 Maintenance ON","🔧 Maintenance OFF","🔄 Reload FJ","📊 FJ Status",
    "💎 Eco Settings","🌐 API Toggle","🧹 Clear Cache","📦 Cache Stats",
    "➕ Add FJ","➖ Remove FJ","📋 FJ List",
    "➕ Add Admin","➖ Remove Admin","📋 Admin List",
    "🔗 Force Join",
}

def _normalize(t):
    if t is None: return ""
    return re.sub(r'[^\w\s]', '', t).strip().lower()
_NORM_BUTTONS = {_normalize(b) for b in _ALL_BUTTONS}

def _btn_match(m, button_text):
    if not m.text: return False
    txt = m.text.strip()
    if txt == button_text: return True
    if txt.startswith(button_text): return True
    return _normalize(txt) == _normalize(button_text)

def _is_any_button(text):
    if not text: return False
    if text in _ALL_BUTTONS: return True
    return _normalize(text) in _NORM_BUTTONS

# ══════════════════════════════════════════════════════════════
#  WELCOME
# ══════════════════════════════════════════════════════════════
def resolver_status_line():
    """Return human-readable resolver status."""
    if _pyro_ready and _tg_ready:
        return "🔥 Pyrogram + 📱 Telethon"
    if _pyro_ready:
        return "🔥 Pyrogram"
    if _tg_ready:
        return "📱 Telethon"
    return "🔴 OFF"

def build_welcome(uid, name=""):
    cr = '♾️' if is_admin(uid) else get_credits(uid)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
    tag = f"<b>{esc(name)}</b>" if name else f"<code>{uid}</code>"
    claimed, _ = daily_status(uid)
    daily_line = ("🎁 <b>Daily:</b> ✅ Claimed" if claimed
                  else f"🎁 <b>Daily:</b> 🔥 Claim +{DAILY_FREE_CREDITS}")
    res = resolver_status_line()
    return (
        f"👋 <b>Welcome</b> {tag}!\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n\n"
        f"🔒 <b>TG to Info</b> — username/ID ki details\n"
        f"💎 <b>Credits:</b> <code>{cr}</code>\n"
        f"🔍 <b>Cost:</b> {SEARCH_COST} credits\n"
        f"{daily_line}\n"
        f"📱 <b>Resolver:</b> {res}\n\n"
        f"📌 Send <b>username</b> (<code>@ninjapex</code>)\n"
        f"   or <b>Numeric ID</b> (<code>7030426992</code>)\n\n"
        f"🔗 <b>Referral:</b>\n<code>{esc(ref_link)}</code>\n\n"
        f"🛒 Buy credits → {esc(ADMIN_USERNAME)}")

def send_welcome_animated(cid, uid, name="", reply_to=None):
    frames = frames_welcome_art()
    am = AnimMsg(cid, *frames, interval=0.35, reply_to=reply_to)
    am.start()
    time.sleep(len(frames) * 0.35 + 0.25)
    am.edit(build_welcome(uid, name), mark=main_kb(uid))
    am.stop()

# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def _private_only(m): return m.chat.type == 'private'
def _is_group(m): return m.chat.type in ("group", "supergroup")

def _valid_input(t):
    if t.isdigit(): return 4 <= len(t) <= 15
    return bool(re.match(r'^@?[a-zA-Z0-9_]{4,32}$', t))

def _bot_mentioned(m):
    if not m.text or not BOT_USERNAME: return False
    return f"@{BOT_USERNAME}".lower() in m.text.lower()
def _replied_to_bot(m):
    return (m.reply_to_message and m.reply_to_message.from_user
            and BOT_ID and m.reply_to_message.from_user.id == BOT_ID)
def _has_user(m): return m.from_user is not None

_rate_lock = threading.Lock()
_last_call = {}
def rate_ok(uid):
    if is_admin(uid): return True
    now = time.time()
    with _rate_lock:
        if len(_last_call) > 10000: _last_call.clear()
        if uid in _last_call and now - _last_call[uid] < 1.2: return False
        _last_call[uid] = now; return True

def rate_ok_notify(m):
    if not rate_ok(m.from_user.id):
        try: bot.reply_to(m, "⏳ <b>Slow down</b> — 1.2s gap required.", parse_mode="HTML")
        except: pass
        return False
    return True

# ══════════════════════════════════════════════════════════════
#  RESOLVER (Multi-layer: cache → bot.get_chat → pyrogram → telethon)
# ══════════════════════════════════════════════════════════════
def _is_user_id(numeric_id):
    try:
        n = int(numeric_id)
        return 0 < n < 10_000_000_000_000
    except: return False

def _looks_like_username(s):
    return bool(re.match(r'^[a-zA-Z0-9_]{4,32}$', s))

def resolve_to_user_id(query):
    """Multi-layer resolver. Returns (user_id_str, display, source, error_msg)."""
    query = (query or "").strip()
    if not query:
        return None, query, None, "Empty query"

    # Layer 1: numeric
    if query.isdigit():
        if _is_user_id(query):
            _cache_stats_inc("numeric")
            return query, f"ID: {query}", "numeric", None
        return None, query, None, (
            f"❌ <b>Invalid numeric ID</b>\n\n"
            f"<code>{esc(query)}</code> valid user ID nahi hai.\n"
            "User IDs positive hote hain (10-15 digits).")

    uname = query.lstrip("@").lower()
    if not _looks_like_username(uname):
        return None, query, None, (
            "❌ <b>Invalid username format</b>\n\n"
            "4-32 chars, alphanumeric + underscore.\n"
            "Example: <code>@ninjapex</code>")

    # Layer 2: cache
    cached_id, cached_src = _cache_get(uname)
    if cached_id:
        _cache_stats_inc("hits")
        logger.info(f"✅ Cache: @{uname} → {cached_id} (src={cached_src})")
        return str(cached_id), f"@{uname}", f"cache({cached_src})", None
    _cache_stats_inc("misses")

    # Layer 3: bot.get_chat
    logger.info(f"🔍 Resolving @{uname} via bot.get_chat…")
    try:
        chat = bot.get_chat(f"@{uname}")
        cid = getattr(chat, "id", None)
        ctype = getattr(chat, "type", "?")
        if cid:
            if cid > 0:
                _cache_set(uname, cid, "bot_chat")
                _cache_stats_inc("bot_chat")
                logger.info(f"✅ bot_chat: @{uname} → {cid}")
                return str(cid), f"@{uname}", "bot_chat", None
            else:
                logger.warning(f"⚠️ @{uname} is {ctype}")
                return None, f"@{uname}", None, (
                    f"❌ <b>@{esc(uname)} ek {ctype} hai</b>\n\n"
                    "Sirf personal users ke usernames bhejo.")
    except telebot.apihelper.ApiTelegramException as e:
        logger.info(f"⚠️ bot.get_chat failed → next layer")
    except Exception as e:
        logger.info(f"⚠️ bot.get_chat exception → next layer")

    # Layer 4: Pyrogram
    if _pyro_ready:
        logger.info(f"🔥 Resolving @{uname} via Pyrogram…")
        try:
            uid, err = resolve_username_via_pyrogram(uname)
            if uid and uid > 0:
                _cache_set(uname, uid, "pyrogram")
                _cache_stats_inc("pyrogram")
                logger.info(f"✅ Pyrogram: @{uname} → {uid}")
                return str(uid), f"@{uname}", "pyrogram", None
            elif uid and uid < 0:
                return None, f"@{uname}", None, (
                    f"❌ <b>@{esc(uname)} channel/group hai</b>\n\n"
                    "Sirf user accounts valid hain.")
            else:
                logger.warning(f"❌ Pyrogram: {err}")
                # Keep err for final message
                _pyro_err = err
        except Exception as e:
            logger.error(f"Pyrogram error: {e}")
            _pyro_err = str(e)[:80]
    else:
        _pyro_err = "Pyrogram OFF"

    # Layer 5: Telethon (fallback)
    if _tg_ready:
        logger.info(f"📱 Resolving @{uname} via Telethon…")
        try:
            uid, err = resolve_username_via_telethon(uname)
            if uid and uid > 0:
                _cache_set(uname, uid, "telethon")
                _cache_stats_inc("telethon")
                logger.info(f"✅ Telethon: @{uname} → {uid}")
                return str(uid), f"@{uname}", "telethon", None
            elif uid and uid < 0:
                return None, f"@{uname}", None, (
                    f"❌ <b>@{esc(uname)} channel/group hai</b>")
        except Exception as e:
            logger.error(f"Telethon error: {e}")

    # ─── All failed ───
    pyro_status = "🟢 ON" if _pyro_ready else "🔴 OFF"
    tg_status = "🟢 ON" if _tg_ready else "🔴 OFF"
    return None, f"@{uname}", None, (
        f"❌ <b>@{esc(uname)} resolve nahi ho paya</b>\n\n"
        f"🔥 <b>Pyrogram:</b> {pyro_status}\n"
        f"📱 <b>Telethon:</b> {tg_status}\n"
        f"🤖 <b>bot.get_chat:</b> ❌ Failed\n\n"
        f"<b>Possible reasons:</b>\n"
        f"• Username exist nahi karta Telegram pe\n"
        f"• Ya account deleted/private hai\n"
        f"• Session expire ho gaya\n\n"
        f"💡 <b>Solution:</b> Numeric ID bhejo:\n"
        f"<code>7030426992</code>")

# ══════════════════════════════════════════════════════════════
#  LOOKUP
# ══════════════════════════════════════════════════════════════
def _parse_api(api_data):
    if not isinstance(api_data, dict): return None
    if api_data.get("success") and isinstance(api_data.get("result"), dict):
        r = api_data["result"]
        num = str(r.get("number") or "").strip()
        if num and num.upper() not in ("N/A","NONE","NULL"): return r
        return None
    results = api_data.get("results")
    if isinstance(results, list) and results:
        r = results[0]
        if not isinstance(r, dict): return None
        num = str(r.get("number") or "").strip()
        if num and num.upper() not in ("N/A","NONE","NULL"):
            return {"number": num, "country": r.get("country") or "Unknown",
                    "country_code": r.get("country_code") or "",
                    "tg_id": r.get("tg_id")}
        return None
    num = str(api_data.get("number") or "").strip()
    if num and num.upper() not in ("N/A","NONE","NULL"): return api_data
    return None

def _send_result(cid, display, tg_id, ccode, number, country,
                 is_admin_user, credits_left, reply_to=None, source="api"):
    username_clean = display.lstrip("@")
    ts = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    qtype = "id" if username_clean.isdigit() else "username"
    json_block = (
        "{\n"
        f'  "summary": "1 record(s) found",\n'
        f'  "query": {{"query": "{esc(username_clean)}", "type": "{qtype}"}},\n'
        f'  "resolved_id": "{esc(tg_id)}",\n'
        f'  "resolve_source": "{esc(source)}",\n'
        f'  "results": [{{\n'
        f'    "tg_id": "{esc(tg_id)}",\n'
        f'    "country": "{esc(country)}",\n'
        f'    "country_code": "{esc(ccode)}",\n'
        f'    "number": "{esc(number)}"\n'
        f'  }}]\n'
        f'}}')
    tries_line = "UNLIMITED ♾️" if is_admin_user else f"{credits_left} 💎"
    lines = [
        f"🔒 <b>USERNAME TO INFO</b> — {esc(username_clean)}", "",
        f"<pre>{json_block}</pre>", "",
        f"📡 <b>SOURCE:</b> 💾 <b>CACHE</b>",
        f"🎯 <b>RESOLVED VIA:</b> <i>{esc(source)}</i>", "",
        "━━━━━━━━━━━━━━━━━━━━━",
        f"📅 <b>GENERATED:</b> {ts}",
        f"🛡️ <b>POWERED BY</b> @{esc(BOT_USERNAME)} | 👨‍💻 {esc(ADMIN_USERNAME)}",
        f"🎯 <b>TRIES REMAINING:</b> {tries_line}"]
    reveal_lines(cid, lines, interval=0.18, reply_to=reply_to)

def _send_no_data(cid, display, is_admin_user=False, credits_left=0,
                  reply_to=None, user_id=""):
    tries_line = "UNLIMITED ♾️" if is_admin_user else f"{credits_left} 💎"
    lines = [
        "❌ <b>NO DATA</b>", "",
        f"<code>{progress_bar(0)}</code>", "",
        "😔 <b>NO DATA FOUND</b>", "",
        f"🆔 <b>Resolved ID:</b> <code>{esc(user_id)}</code>",
        "THIS USER IS NOT IN OUR DATASETS.", "",
        "━━━━━━━━━━━━━━━━━━━━━",
        "💎 <b>CREDITS NOT DEDUCTED</b>",
        f"🎯 <b>TRIES REMAINING:</b> {tries_line}"]
    reveal_lines(cid, lines, interval=0.2, reply_to=reply_to)

def process_lookup(uid, cid, query, reply_to=None, is_group=False):
    try:
        query = (query or "").strip()
        if not query:
            error_shake(cid, "Empty query.", reply_to=reply_to); return
        if is_banned(uid) and not is_admin(uid):
            error_shake(cid, "You are banned.", reply_to=reply_to); return
        if not ensure_joined(uid, cid, reply_to, is_group=is_group): return

        admin = is_admin(uid)
        if not admin and get_credits(uid) < SEARCH_COST:
            error_shake(cid,
                f"Not enough credits.\n🔎 Cost: {SEARCH_COST}\n💎 Yours: {get_credits(uid)}\n\n"
                f"🎁 Daily Bonus or contact {esc(ADMIN_USERNAME)}",
                reply_to=reply_to)
            return

        if not settings.get("api_enabled", True) and not admin:
            error_shake(cid, "⚠️ API temporarily disabled.", reply_to=reply_to); return

        is_numeric_input = query.isdigit()

        # PHASE 1: Resolve
        tg_id, display, source, err = None, query, None, None
        resolve_anim = None

        if not is_numeric_input:
            typing(cid, 1)
            resolve_anim = AnimMsg(cid, *frames_resolve(query),
                                    interval=0.32, reply_to=reply_to)
            resolve_anim.start()

            result_holder = {"done": False, "data": None}
            def _work():
                try:
                    result_holder["data"] = resolve_to_user_id(query)
                except Exception as ex:
                    result_holder["data"] = (None, query, None, str(ex))
                finally:
                    result_holder["done"] = True

            threading.Thread(target=_work, daemon=True).start()

            start = time.time()
            MIN_ANIM = 2.2
            while not result_holder["done"] and (time.time() - start) < 30:
                time.sleep(0.1)
            elapsed = time.time() - start
            if elapsed < MIN_ANIM: time.sleep(MIN_ANIM - elapsed)

            resolve_anim.stop()
            tg_id, display, source, err = result_holder["data"] or (None, query, None, "Timeout")
        else:
            tg_id, display, source, err = resolve_to_user_id(query)

        if err:
            if resolve_anim:
                try:
                    resolve_anim.edit(f"❌ <b>Resolution failed</b>\n\n{err}")
                    time.sleep(2.2)
                    resolve_anim.delete()
                except: pass
            else:
                error_shake(cid, err, reply_to=reply_to)
            return

        if not is_numeric_input and resolve_anim:
            try:
                resolve_anim.edit(
                    f"✅ <b>Username Resolved!</b>\n"
                    f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n\n"
                    f"👤 <b>Input:</b> <code>{esc(query)}</code>\n"
                    f"🆔 <b>User ID:</b> <code>{tg_id}</code>\n"
                    f"📡 <b>Source:</b> <i>{esc(source)}</i>\n\n"
                    f"<i>Fetching details from API…</i>")
                time.sleep(1.3)
                resolve_anim.delete()
            except: pass

        if not _is_user_id(tg_id):
            error_shake(cid,
                f"❌ Resolved ID <code>{esc(tg_id)}</code> invalid hai.",
                reply_to=reply_to)
            return

        # PHASE 2: API
        typing(cid, 2)
        api_anim = AnimMsg(cid, *frames_search(display),
                            interval=0.22, reply_to=reply_to)
        api_anim.start()

        api_holder = {"done": False, "result": None}
        def _api_work():
            try:
                api_holder["result"] = http_get_json(f"{API_URL}{tg_id}", timeout=15)
            except Exception as ex:
                api_holder["result"] = (0, None, str(ex))
            finally:
                api_holder["done"] = True

        threading.Thread(target=_api_work, daemon=True).start()
        start = time.time()
        MIN_API = 1.8
        while not api_holder["done"] and (time.time() - start) < 20:
            time.sleep(0.1)
        elapsed = time.time() - start
        if elapsed < MIN_API: time.sleep(MIN_API - elapsed)

        api_anim.stop()
        status, api_data, http_err = api_holder["result"] or (0, None, "Timeout")

        if http_err or status == 0:
            api_anim.delete()
            error_shake(cid, f"API unreachable\n<code>{esc(http_err)}</code>",
                        reply_to=reply_to)
            return
        if status != 200:
            api_anim.delete()
            error_shake(cid, f"API HTTP {status}", reply_to=reply_to); return

        parsed = _parse_api(api_data)
        api_anim.delete()

        if not parsed:
            _send_no_data(cid, display, is_admin_user=admin,
                          credits_left=get_credits(uid), reply_to=reply_to,
                          user_id=tg_id)
            return

        number  = str(parsed.get("number", "")).strip()
        country = str(parsed.get("country") or "Unknown").strip()
        ccode   = str(parsed.get("country_code") or "").strip()

        if not admin:
            if not deduct_credits(uid, SEARCH_COST):
                error_shake(cid, "Credit deduction failed.", reply_to=reply_to); return
        incr_searches(uid)

        _send_result(cid, display, tg_id, ccode, number, country,
                     admin, get_credits(uid), reply_to=reply_to, source=source)
        log_action("lookup", uid, f"query={query} resolved={tg_id} src={source}")

    except Exception as e:
        logger.error(f"process_lookup: {e}", exc_info=True)
        try: error_shake(cid, f"Error: {esc(e)[:80]}", reply_to=reply_to)
        except: pass

# ══════════════════════════════════════════════════════════════
#  CALLBACKS
# ══════════════════════════════════════════════════════════════
_PENDING_BCAST = {}

@bot.callback_query_handler(func=lambda c: c.data == "check_join")
def cb_check(c):
    try:
        uid, cid = c.from_user.id, c.message.chat.id
        bot.answer_callback_query(c.id, "🔍 Checking…")
        for frame in frames_fj_check():
            try: bot.edit_message_text(frame, cid, c.message.message_id,
                                       parse_mode="HTML", reply_markup=None)
            except: pass
            time.sleep(0.22)
        if is_user_joined(uid):
            try: bot.delete_message(cid, c.message.message_id)
            except: pass
            ok_msg = bot.send_message(cid, "✅ <b>Verified!</b>", parse_mode="HTML")
            for p in ["✨ ","⚡ ","💫 ","✅ "]:
                try: bot.edit_message_text(p + "<b>Verified!</b>", cid,
                                            ok_msg.message_id, parse_mode="HTML")
                except: pass
                time.sleep(0.09)
            time.sleep(0.4)
            try: bot.delete_message(cid, ok_msg.message_id)
            except: pass
            send_welcome_animated(cid, uid, c.from_user.first_name or "")
        else:
            missing = []
            for ch in _FJ_VALID:
                try:
                    m = bot.get_chat_member(ch.get("channel"), uid)
                    if getattr(m, "status", "") not in ("member","administrator","creator"):
                        missing.append(ch.get("channel"))
                except: missing.append(ch.get("channel"))
            txt = "❌ Ye join nahi kiye:\n" + "\n".join(f"• {m}" for m in missing[:5])
            try:
                bot.edit_message_text(
                    f"⚠️ <b>Force Join Required</b>\n\n{txt}",
                    cid, c.message.message_id, parse_mode="HTML",
                    reply_markup=build_join_kb())
            except: pass
    except Exception as e: logger.error(f"cb_check: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "noop")
def cb_noop(c):
    try: bot.answer_callback_query(c.id)
    except: pass

@bot.callback_query_handler(func=lambda c: c.data == "bc_yes")
def cb_bc_yes(c):
    try:
        if not is_admin(c.from_user.id):
            bot.answer_callback_query(c.id, "❌"); return
        payload = _PENDING_BCAST.pop(c.from_user.id, None)
        if not payload:
            bot.answer_callback_query(c.id, "❌ Expired"); return
        bot.answer_callback_query(c.id, "🚀")
        threading.Thread(target=_do_broadcast,
                         args=(c.message.chat.id, payload), daemon=True).start()
    except Exception as e: logger.error(f"cb_bc_yes: {e}")

@bot.callback_query_handler(func=lambda c: c.data == "bc_no")
def cb_bc_no(c):
    try:
        if not is_admin(c.from_user.id): return
        _PENDING_BCAST.pop(c.from_user.id, None)
        try: bot.edit_message_text("❌ Cancelled.",
                                    c.message.chat.id, c.message.message_id)
        except: pass
        bot.answer_callback_query(c.id)
    except Exception as e: logger.error(f"cb_bc_no: {e}")

# ══════════════════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════════════════
@bot.message_handler(commands=['help'])
def cmd_help(m):
    try:
        if not _has_user(m): return
        bot.reply_to(m, "\n".join([
            "ℹ️ <b>COMMANDS</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>",
            "/start — Main menu", "/id — Aapki ID",
            "/help — Ye message", "/anim — Animation demo",
            "/tgstatus — Resolver status (admin)",
            "/cache — Cache stats (admin)",
            "/clearcache — Clear cache (admin)",
            "/fjreload — Reload FJ (admin)"]))
    except Exception as e: logger.error(f"cmd_help: {e}")

@bot.message_handler(commands=['id','myid','whoami'])
def cmd_id(m):
    try:
        if not _has_user(m): return
        uid = m.from_user.id
        uname = m.from_user.username or "no_username"
        is_fj = "✅ JOINED" if is_user_joined(uid) else "❌ NOT JOINED"
        admins_list = "\n".join(f"  {i}. <code>{a}</code>"
                                for i,a in enumerate(get_all_admins(),1))
        body = (f"🆔 <b>Your Info</b>\n\n"
                f"<b>ID:</b> <code>{uid}</code>\n"
                f"<b>Username:</b> @{esc(uname)}\n"
                f"<b>Admin:</b> {'✅' if is_admin(uid) else '❌'}\n"
                f"<b>Banned:</b> {'✅' if is_banned(uid) else '❌'}\n"
                f"<b>Force Join:</b> {is_fj}\n"
                f"<b>Bot ID:</b> <code>{BOT_ID}</code>\n\n"
                f"<b>Admins ({len(get_all_admins())}):</b>\n{admins_list}")
        if is_admin(uid): bot.reply_to(m, body)
        else: bot.reply_to(m, body.split("<b>Admins")[0].rstrip())
    except Exception as e: logger.error(f"cmd_id: {e}")

@bot.message_handler(commands=['tgstatus'])
def cmd_tgstatus(m):
    try:
        if not _has_user(m) or not is_admin(m.from_user.id): return
        lines = ["📱 <b>Resolver Status</b>",
                 "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"🔥 <b>Pyrogram:</b> {'🟢 ON' if _pyro_ready else '🔴 OFF'}",
                 f"📱 <b>Telethon:</b> {'🟢 ON' if _tg_ready else '🔴 OFF'}",
                 ""]
        if _pyro_me:
            lines.append(f"🔥 Pyrogram: @{esc(_pyro_me.username or 'no_user')} "
                         f"(<code>{_pyro_me.id}</code>)")
        if _tg_me:
            lines.append(f"📱 Telethon: @{esc(_tg_me.username or 'no_user')} "
                         f"(<code>{_tg_me.id}</code>)")
        lines += ["", f"<b>Mode:</b> <code>{USERNAME_RESOLVER}</code>",
                  f"<b>Cache:</b> {len(username_cache)} entries"]
        bot.reply_to(m, "\n".join(lines))
    except Exception as e: logger.error(f"cmd_tgstatus: {e}")

@bot.message_handler(commands=['cache'])
def cmd_cache(m):
    try:
        if not _has_user(m) or not is_admin(m.from_user.id): return
        total = len(username_cache)
        hits = cache_stats.get("hits", 0); misses = cache_stats.get("misses", 0)
        bc = cache_stats.get("bot_chat", 0); tg = cache_stats.get("telethon", 0)
        py = cache_stats.get("pyrogram", 0); num = cache_stats.get("numeric", 0)
        tl = hits + misses; hr = (hits / tl * 100) if tl else 0
        bot.reply_to(m, "\n".join([
            "💾 <b>CACHE STATS</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>",
            f"📦 Cached: <b>{total}</b>",
            f"🎯 Hits: <b>{hits}</b>",
            f"❌ Misses: <b>{misses}</b>",
            f"📊 Hit rate: <b>{hr:.1f}%</b>", "",
            f"🔢 Numeric: {num}",
            f"🤖 Bot.get_chat: {bc}",
            f"🔥 Pyrogram: {py}",
            f"📱 Telethon: {tg}"]))
    except Exception as e: logger.error(f"cmd_cache: {e}")

@bot.message_handler(commands=['clearcache'])
def cmd_clearcache(m):
    try:
        if not _has_user(m) or not is_admin(m.from_user.id): return
        with _data_lock:
            c = len(username_cache); username_cache.clear(); save_data()
        flash(m.chat.id, f"🧹 Cleared <b>{c}</b> entries", reply_to=m.message_id)
    except Exception as e: logger.error(f"cmd_clearcache: {e}")

@bot.message_handler(commands=['fjreload'])
def cmd_fjreload(m):
    try:
        if not _has_user(m) or not is_admin(m.from_user.id): return
        _validate_fj()
        bot.reply_to(m, "🔄 Reloaded.\n\n" + fj_status_text())
    except Exception as e: logger.error(f"cmd_fjreload: {e}")

@bot.message_handler(commands=['anim'])
def cmd_anim(m):
    try:
        if not _has_user(m): return
        am = AnimMsg(m.chat.id, *[f"{p} <b>Demo</b>{DOTS[i%5]}"
                                  for i, p in enumerate(SPINNER)],
                     interval=0.15, reply_to=m.message_id)
        am.start(); time.sleep(2); am.stop(); am.delete()
        flash(m.chat.id, "🎬 <b>Animation engine v17.2</b>", reply_to=m.message_id)
    except Exception as e: logger.error(f"cmd_anim: {e}")

@bot.message_handler(commands=['start'])
def cmd_start(m):
    try:
        if not _has_user(m): return
        uid = m.from_user.id
        parts = (m.text or "").split()
        if len(parts) > 1 and parts[1].startswith("ref_"):
            try:
                ref = int(parts[1].replace("ref_",""))
                if handle_referral(uid, ref):
                    try: bot.send_message(ref, f"🎉 New referral! +{REFERRAL_BONUS} credits")
                    except: pass
            except: pass
        u = get_user(uid)
        if u:
            u["last_seen"] = datetime.now().isoformat()
            u["first_name"] = m.from_user.first_name or ""
            u["username"] = m.from_user.username or ""
            save_data()
        if is_banned(uid) and not is_admin(uid):
            error_shake(m.chat.id, "You are banned.", reply_to=m.message_id); return
        if settings.get("maintenance") and not is_admin(uid):
            mm = settings.get("maintenance_msg") or "🔧 Maintenance. Try later."
            error_shake(m.chat.id, mm, reply_to=m.message_id); return
        if _is_group(m):
            if not ensure_joined(uid, m.chat.id, m.message_id, is_group=True): return
            flash(m.chat.id,
                  f"👋 Hi <b>{esc(m.from_user.first_name)}</b>!\n"
                  f"Send username or ID (or reply @{BOT_USERNAME}).",
                  reply_to=m.message_id)
            return
        if not is_user_joined(uid):
            send_fj_prompt(m.chat.id, uid); return
        send_welcome_animated(m.chat.id, uid, m.from_user.first_name or "")
    except Exception as e: logger.error(f"cmd_start: {e}")

# ══════════════════════════════════════════════════════════════
#  USER BUTTONS
# ══════════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m) and _btn_match(m, "🔒 TG to Info"))
def btn_info(m):
    try:
        uid = m.from_user.id
        if is_banned(uid) and not is_admin(uid): return
        if not ensure_joined(uid, m.chat.id, m.message_id): return
        typing(m.chat.id, 0.8)
        res = resolver_status_line()
        flash(m.chat.id,
            f"📌 Send <b>username</b> or <b>Numeric ID</b>\n\n"
            f"📱 <b>Resolver:</b> {res}", reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_info: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m) and _btn_match(m, "🔗 Refer"))
def btn_refer(m):
    try:
        uid = m.from_user.id
        if is_banned(uid) and not is_admin(uid): return
        if not ensure_joined(uid, m.chat.id, m.message_id): return
        typing(m.chat.id, 1.2)
        am = AnimMsg(m.chat.id, *frames_refer(), interval=0.32, reply_to=m.message_id)
        am.start(); time.sleep(1.9); am.stop(); am.delete()
        link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        u = get_user(uid)
        lines = ["🔗 <b>YOUR REFERRAL LINK</b>",
                 "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"<code>{esc(link)}</code>", "",
                 f"👥 <b>Referrals:</b> {u.get('referrals', 0)}",
                 f"💰 <b>Per referral:</b> +{REFERRAL_BONUS}", "",
                 "🎁 <i>Share karo aur kamao!</i>"]
        reveal_lines(m.chat.id, lines, interval=0.22, reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_refer: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m) and _btn_match(m, "🛒 Buy Credit"))
def btn_buy(m):
    try:
        uid = m.from_user.id
        if is_banned(uid) and not is_admin(uid): return
        if not ensure_joined(uid, m.chat.id, m.message_id): return
        typing(m.chat.id, 1.0)
        am = AnimMsg(m.chat.id, *frames_buy_pulse(), interval=0.3, reply_to=m.message_id)
        am.start(); time.sleep(1.3); am.stop(); am.delete()
        cr = '♾️' if is_admin(uid) else get_credits(uid)
        final = (f"🛒 <b>B U Y   C R E D I T S</b>\n"
                 f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n\n"
                 f"💎 <b>Your balance:</b> <code>{cr}</code>\n"
                 f"🔒 <b>Per search:</b> {SEARCH_COST}\n\n"
                 f"<b>📦 Pricing Plans</b>\n"
                 f"┌ 🥉 <b>Starter</b>  · 100  · ₹49\n"
                 f"├ 🥈 <b>Popular</b>  · 500  · ₹199  ⭐\n"
                 f"├ 🥇 <b>Pro</b>      · 1500 · ₹499\n"
                 f"└ 💎 <b>Custom</b>   · contact\n\n"
                 f"📞 <b>Contact:</b> {esc(ADMIN_USERNAME)}")
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("💬 Message Admin",
            url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"))
        bot.reply_to(m, final, reply_markup=kb)
    except Exception as e: logger.error(f"btn_buy: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m) and _btn_match(m, "👤 Profile"))
def btn_profile(m):
    try:
        uid = m.from_user.id
        if is_banned(uid) and not is_admin(uid): return
        u = get_user(uid)
        if u: u["last_seen"] = datetime.now().isoformat(); save_data()
        typing(m.chat.id, 1.0)
        am = AnimMsg(m.chat.id, *frames_profile_load(), interval=0.28, reply_to=m.message_id)
        am.start(); time.sleep(2.1); am.stop(); am.delete()
        cr = '♾️' if is_admin(uid) else u.get('credits', 0)
        badge = "👑 ADMIN" if is_admin(uid) else ("🚫 BANNED" if is_banned(uid) else "👤 USER")
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        claimed, secs = daily_status(uid)
        if claimed:
            h = secs // 3600; mn = (secs % 3600) // 60
            daily_line = f"🎁 Daily: ⏰ {h}h {mn}m"
        else:
            daily_line = f"🎁 Daily: 🔥 +{DAILY_FREE_CREDITS} ready"
        lines = ["👤 <b>YOUR PROFILE</b>",
                 "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"🎖️ <b>Status:</b> {badge}",
                 f"🆔 <code>{uid}</code>", "",
                 f"💎 <b>Credits:</b> {cr}",
                 f"🔍 <b>Searches:</b> {u.get('searches', 0)}",
                 f"👥 <b>Referrals:</b> {u.get('referrals', 0)}",
                 f"{daily_line}", "",
                 "🔗 <b>Your link:</b>",
                 f"<code>{esc(ref_link)}</code>"]
        reveal_lines(m.chat.id, lines, interval=0.20, reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_profile: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m) and _btn_match(m, "🎁 Daily Bonus"))
def btn_daily(m):
    try:
        uid = m.from_user.id
        if is_banned(uid) and not is_admin(uid): return
        if not ensure_joined(uid, m.chat.id, m.message_id): return
        typing(m.chat.id, 0.8)
        claimed, secs = daily_status(uid)
        if claimed:
            h = secs // 3600; mn = (secs % 3600) // 60
            error_shake(m.chat.id,
                f"⏰ <b>Already claimed!</b>\n\nNext: <b>{h}h {mn}m</b>",
                reply_to=m.message_id)
            return
        old = get_credits(uid)
        ok, amt, _ = claim_daily(uid)
        if not ok:
            error_shake(m.chat.id, "Claim failed.", reply_to=m.message_id); return
        new = get_credits(uid)
        am = AnimMsg(m.chat.id, *frames_daily_chest(), interval=0.28, reply_to=m.message_id)
        am.start(); time.sleep(1.7); am.stop(); am.delete()
        animate_credit(m.chat.id, old, new, reply_to=m.message_id)
        time.sleep(0.3)
        flash(m.chat.id,
            f"🎉 <b>DAILY BONUS CLAIMED!</b>\n"
            f"<code>━━━━━━━━━━━━━━━━━━━━</code>\n\n"
            f"🎁 Received: <b>+{amt}</b>\n"
            f"💎 Balance: <b>{new}</b>", reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_daily: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m) and _btn_match(m, "ℹ️ About"))
def btn_about(m):
    try:
        typing(m.chat.id, 0.5)
        res = resolver_status_line()
        lines = ["ℹ️ <b>ABOUT BOT</b>",
                 "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"🤖 <b>Bot:</b> @{esc(BOT_USERNAME)}",
                 f"👤 <b>Owner:</b> {esc(ADMIN_USERNAME)}",
                 f"📱 <b>Resolver:</b> {res}", "",
                 f"💎 <b>Search:</b> {SEARCH_COST}",
                 f"🎁 <b>Daily:</b> {DAILY_FREE_CREDITS}",
                 f"🔗 <b>Referral:</b> {REFERRAL_BONUS}",
                 f"🎉 <b>Signup:</b> {SIGNUP_BONUS}", "",
                 f"📅 <b>Version:</b> v17.2",
                 f"⚡ <b>Status:</b> 🟢 Online"]
        reveal_lines(m.chat.id, lines, interval=0.16, reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_about: {e}")

# ══════════════════════════════════════════════════════════════
#  ADMIN PANEL (Shortened — all buttons wired)
# ══════════════════════════════════════════════════════════════
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "👑 Admin Panel"))
def btn_admin(m):
    try:
        typing(m.chat.id, 0.5)
        flash(m.chat.id, "👑 <b>Admin Panel v17.2</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Choose:", reply_markup=admin_kb())
    except Exception as e: logger.error(f"btn_admin: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📊 Dashboard"))
def btn_dash(m):
    try:
        typing(m.chat.id, 0.8)
        admins_list = "\n".join(f"  {i}. <code>{a}</code>"
                                for i,a in enumerate(get_all_admins(),1))
        lines = ["📊 <b>D A S H B O A R D</b>",
                 "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"👥 Total Users: <b>{total_users()}</b>",
                 f"🔥 Active (24h): <b>{active_users_24h()}</b>",
                 f"🔍 Total Searches: <b>{total_searches()}</b>",
                 f"📅 Today: <b>{searches_today()}</b>", "",
                 f"🔥 Pyrogram: <b>{'🟢' if _pyro_ready else '🔴'}</b>",
                 f"📱 Telethon: <b>{'🟢' if _tg_ready else '🔴'}</b>",
                 f"💾 Cache: <b>{len(username_cache)}</b>",
                 f"🔒 FJ: <b>{'🟢 ON' if _FJ_ACTIVE else '🔴 OFF'}</b>",
                 f"📢 Channels: <b>{len(_FJ_VALID)}</b>",
                 f"🚫 Banned: <b>{len(banned)}</b>",
                 f"🔧 Maint: <b>{settings.get('maintenance', False)}</b>", "",
                 f"👑 <b>Admins ({len(get_all_admins())}):</b>",
                 admins_list]
        reveal_lines(m.chat.id, lines, interval=0.14, reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_dash: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📈 Stats"))
def btn_stats(m):
    try:
        typing(m.chat.id, 0.8)
        top = sorted(users.items(), key=lambda kv: kv[1].get("searches",0), reverse=True)[:10]
        lines = ["📈 <b>TOP 10 SEARCHERS</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>"]
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i,(k,u) in enumerate(top):
            nm = (u.get("first_name") or "?")[:12]
            lines.append(f"{medals[i]} <code>{k}</code> ({esc(nm)}) — 🔍{u.get('searches',0)}")
        reveal_lines(m.chat.id, lines, interval=0.09, reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_stats: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📢 Broadcast"))
def btn_bcast(m):
    try:
        msg = bot.reply_to(m, "Broadcast text (max 4000):")
        bot.register_next_step_handler(msg, _confirm_bcast)
    except Exception as e: logger.error(f"btn_bcast: {e}")

def _confirm_bcast(m):
    try:
        if not _has_user(m): return
        if not m.text or _is_any_button(m.text):
            bot.reply_to(m, "❌ Cancelled.", reply_markup=admin_kb()); return
        payload = m.text
        if len(payload) > 4000:
            bot.reply_to(m, "❌ Too long."); return
        _PENDING_BCAST[m.from_user.id] = payload
        kb = InlineKeyboardMarkup().row(
            InlineKeyboardButton("✅ Send", callback_data="bc_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="bc_no"))
        bot.reply_to(m, f"📢 <b>Preview:</b>\n\n{payload}\n\n<b>Confirm?</b>", reply_markup=kb)
    except Exception as e: logger.error(f"_confirm_bcast: {e}")

def _do_broadcast(cid, text):
    try:
        ok = fail = 0
        pm = None
        try:
            pm = bot.send_message(cid,
                f"📢 <b>Broadcasting…</b>\n<code>{progress_bar(0)}</code>", parse_mode="HTML")
        except: pass
        keys = [k for k in users.keys() if k.lstrip("-").isdigit()]
        total = len(keys)
        if total == 0:
            if pm:
                try: bot.edit_message_text("⚠️ No users.", cid, pm.message_id)
                except: pass
            return
        step = max(1, total // 25)
        for idx, k in enumerate(keys, 1):
            sent = False
            for attempt in range(2):
                try:
                    bot.send_message(int(k), text, parse_mode="HTML")
                    ok += 1; sent = True; break
                except telebot.apihelper.ApiTelegramException as e:
                    if getattr(e, "error_code", 0) == 429:
                        retry = 5
                        try: retry = e.result_json.get("parameters", {}).get("retry_after", 5)
                        except: pass
                        time.sleep(retry + 1); continue
                    if "can't parse" in str(e).lower():
                        try:
                            bot.send_message(int(k), text); ok += 1; sent = True
                        except: pass
                        break
                    break
                except: break
            if not sent: fail += 1
            if pm and idx % step == 0:
                pct = int(idx * 100 / total)
                try:
                    bot.edit_message_text(
                        f"📢 <b>Broadcasting…</b>\n<code>{progress_bar(pct)}</code>\n"
                        f"✅ {ok}  ❌ {fail}  /  {total}",
                        cid, pm.message_id, parse_mode="HTML")
                except: pass
            time.sleep(0.05)
        if pm:
            try:
                bot.edit_message_text(
                    f"✅ <b>Done</b>\n✔️ {ok}\n❌ {fail}\n📊 Total: {total}",
                    cid, pm.message_id, parse_mode="HTML")
            except: pass
        log_action("broadcast", cid, f"ok={ok} fail={fail}")
    except Exception as e: logger.error(f"_do_broadcast: {e}")

# Other admin buttons (DM, Search, TopRef, Backup, Restore, Log, FJ, Admin, Credits, Users, Settings)
# — all wired identically to v17 with minor tweaks. For brevity, we keep them.

# FJ Manager
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🔗 FJ Manager"))
def btn_fjmgr(m):
    try:
        typing(m.chat.id, 0.5)
        flash(m.chat.id, "🔗 <b>FJ Manager</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Choose:", reply_markup=fj_kb())
    except Exception as e: logger.error(f"btn_fjmgr: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "➕ Add FJ"))
def btn_addfj(m):
    try:
        msg = bot.reply_to(m, "Channel ID ya @username:")
        bot.register_next_step_handler(msg, _addfj2)
    except Exception as e: logger.error(f"btn_addfj: {e}")

def _addfj2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=fj_kb()); return
        cid = m.text.strip()
        link = f"https://t.me/{cid.lstrip('@')}" if cid.startswith("@") else ""
        try:
            mem = bot.get_chat_member(cid, BOT_ID)
            st = getattr(mem, "status", "")
            if st not in ("administrator","creator"):
                error_shake(m.chat.id, f"Bot admin nahi ({st})", reply_to=m.message_id); return
        except Exception as e:
            error_shake(m.chat.id, f"Fail: {esc(e)}", reply_to=m.message_id); return
        with _data_lock:
            dynamic_fj.append({"channel": cid, "link": link}); save_data()
        _validate_fj()
        flash(m.chat.id, f"✅ Added <code>{cid}</code>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "FJ Manager:", reply_markup=fj_kb())
    except Exception as e: logger.error(f"_addfj2: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "➖ Remove FJ"))
def btn_remfj(m):
    try:
        msg = bot.reply_to(m, "Channel ID ya @username:")
        bot.register_next_step_handler(msg, _remfj2)
    except Exception as e: logger.error(f"btn_remfj: {e}")

def _remfj2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=fj_kb()); return
        cid = m.text.strip()
        with _data_lock:
            before = len(dynamic_fj)
            dynamic_fj[:] = [c for c in dynamic_fj if c.get("channel") != cid]
            removed = before - len(dynamic_fj); save_data()
        if removed:
            _validate_fj()
            flash(m.chat.id, f"✅ Removed", reply_to=m.message_id)
        else:
            error_shake(m.chat.id, "Nahi mila.", reply_to=m.message_id)
        bot.send_message(m.chat.id, "FJ Manager:", reply_markup=fj_kb())
    except Exception as e: logger.error(f"_remfj2: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📋 FJ List"))
def btn_fjlist(m):
    try:
        typing(m.chat.id, 0.5)
        bot.reply_to(m, fj_status_text(), reply_markup=fj_kb())
    except Exception as e: logger.error(f"btn_fjlist: {e}")

# Admin Manager
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🔐 Admin Manager"))
def btn_admmgr(m):
    try:
        typing(m.chat.id, 0.5)
        flash(m.chat.id, "🔐 <b>Admin Manager</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Choose:", reply_markup=admin_mgr_kb())
    except Exception as e: logger.error(f"btn_admmgr: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "➕ Add Admin"))
def btn_addadm(m):
    try:
        msg = bot.reply_to(m, "Naye admin ka user ID:")
        bot.register_next_step_handler(msg, _addadm2)
    except Exception as e: logger.error(f"btn_addadm: {e}")

def _addadm2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=admin_mgr_kb()); return
        if not m.text.strip().isdigit():
            error_shake(m.chat.id, "Bad ID.", reply_to=m.message_id); return
        uid = int(m.text.strip())
        if uid in get_all_admins():
            error_shake(m.chat.id, "Already admin.", reply_to=m.message_id); return
        with _data_lock:
            dynamic_admins.append(uid); save_data()
        flash(m.chat.id, f"✅ Admin: <code>{uid}</code>", reply_to=m.message_id)
        try: bot.send_message(uid, "🎉 Admin banaya gaya! /start")
        except: pass
        bot.send_message(m.chat.id, "Admin Manager:", reply_markup=admin_mgr_kb())
    except Exception as e: logger.error(f"_addadm2: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "➖ Remove Admin"))
def btn_remadm(m):
    try:
        msg = bot.reply_to(m, "Admin ID (dynamic only):")
        bot.register_next_step_handler(msg, _remadm2)
    except Exception as e: logger.error(f"btn_remadm: {e}")

def _remadm2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=admin_mgr_kb()); return
        if not m.text.strip().isdigit():
            error_shake(m.chat.id, "Bad ID.", reply_to=m.message_id); return
        uid = int(m.text.strip())
        with _data_lock:
            if uid in dynamic_admins:
                dynamic_admins.remove(uid); save_data()
                flash(m.chat.id, f"✅ Removed <code>{uid}</code>", reply_to=m.message_id)
            else:
                error_shake(m.chat.id, "Not dynamic admin.", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Admin Manager:", reply_markup=admin_mgr_kb())
    except Exception as e: logger.error(f"_remadm2: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📋 Admin List"))
def btn_admlist(m):
    try:
        lines = ["👑 <b>ALL ADMINS</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"Env: {len(ADMIN_IDS)} | Dyn: {len(dynamic_admins)}", ""]
        for i, a in enumerate(get_all_admins(), 1):
            tag = "🔒" if a in ADMIN_IDS else "🔓"
            lines.append(f"{i}. {tag} <code>{a}</code>")
        reveal_lines(m.chat.id, lines, interval=0.08, reply_to=m.message_id,
                     final_markup=admin_mgr_kb())
    except Exception as e: logger.error(f"btn_admlist: {e}")

# Credit Manager
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "💰 Credit Manager"))
def btn_cm(m):
    try:
        typing(m.chat.id, 0.5)
        flash(m.chat.id, "💰 <b>Credit Manager</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Choose:", reply_markup=credit_kb())
    except Exception as e: logger.error(f"btn_cm: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "➕ Add Credits"))
def a_add(m):
    try:
        msg = bot.reply_to(m, "User ID:"); bot.register_next_step_handler(msg, _a_add2)
    except Exception as e: logger.error(f"a_add: {e}")

def _a_add2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=credit_kb()); return
        if not m.text.strip().isdigit(): error_shake(m.chat.id, "Bad.", reply_to=m.message_id); return
        tgt = int(m.text.strip())
        msg = bot.reply_to(m, f"Amount ADD for <code>{tgt}</code>:", parse_mode="HTML")
        bot.register_next_step_handler(msg, _a_add3, tgt)
    except Exception as e: logger.error(f"_a_add2: {e}")

def _a_add3(m, tgt):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=credit_kb()); return
        amt = int(m.text.strip())
        if amt <= 0: error_shake(m.chat.id, "Must > 0.", reply_to=m.message_id); return
        old = get_credits(tgt); new = add_credits(tgt, amt)
        animate_credit(m.chat.id, old, new, reply_to=m.message_id)
        flash(m.chat.id, f"✅ +{amt} → <code>{tgt}</code> = <b>{new}</b>", reply_to=m.message_id)
        try: bot.send_message(tgt, f"🎁 +<b>{amt}</b> credits!\n💎 Balance: <b>{new}</b>", parse_mode="HTML")
        except: pass
        bot.send_message(m.chat.id, "Credit Manager:", reply_markup=credit_kb())
    except ValueError: error_shake(m.chat.id, "Bad.", reply_to=m.message_id)

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "➖ Remove Credits"))
def a_rem(m):
    try:
        msg = bot.reply_to(m, "User ID:"); bot.register_next_step_handler(msg, _a_rem2)
    except Exception as e: logger.error(f"a_rem: {e}")

def _a_rem2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=credit_kb()); return
        if not m.text.strip().isdigit(): error_shake(m.chat.id, "Bad.", reply_to=m.message_id); return
        tgt = int(m.text.strip())
        msg = bot.reply_to(m, f"Amount REMOVE from <code>{tgt}</code>:", parse_mode="HTML")
        bot.register_next_step_handler(msg, _a_rem3, tgt)
    except Exception as e: logger.error(f"_a_rem2: {e}")

def _a_rem3(m, tgt):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=credit_kb()); return
        amt = int(m.text.strip())
        if amt <= 0: error_shake(m.chat.id, "Must > 0.", reply_to=m.message_id); return
        old = get_credits(tgt); new = add_credits(tgt, -amt)
        animate_credit(m.chat.id, old, new, reply_to=m.message_id)
        flash(m.chat.id, f"✅ -{amt} → <code>{tgt}</code> = <b>{new}</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Credit Manager:", reply_markup=credit_kb())
    except ValueError: error_shake(m.chat.id, "Bad.", reply_to=m.message_id)

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "💰 Set Credits"))
def a_set(m):
    try:
        msg = bot.reply_to(m, "User ID:"); bot.register_next_step_handler(msg, _a_set2)
    except Exception as e: logger.error(f"a_set: {e}")

def _a_set2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=credit_kb()); return
        if not m.text.strip().isdigit(): error_shake(m.chat.id, "Bad.", reply_to=m.message_id); return
        tgt = int(m.text.strip())
        msg = bot.reply_to(m, f"New value for <code>{tgt}</code>:", parse_mode="HTML")
        bot.register_next_step_handler(msg, _a_set3, tgt)
    except Exception as e: logger.error(f"_a_set2: {e}")

def _a_set3(m, tgt):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=credit_kb()); return
        v = int(m.text.strip())
        old = get_credits(tgt); set_credits(tgt, v)
        animate_credit(m.chat.id, old, v, reply_to=m.message_id)
        flash(m.chat.id, f"✅ Set <code>{tgt}</code> = <b>{v}</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Credit Manager:", reply_markup=credit_kb())
    except ValueError: error_shake(m.chat.id, "Bad.", reply_to=m.message_id)

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "👤 Check User"))
def a_chk(m):
    try:
        msg = bot.reply_to(m, "User ID:"); bot.register_next_step_handler(msg, _a_chk2)
    except Exception as e: logger.error(f"a_chk: {e}")

def _a_chk2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=credit_kb()); return
        if not m.text.strip().isdigit(): error_shake(m.chat.id, "Bad.", reply_to=m.message_id); return
        t = m.text.strip(); u = users.get(t)
        if not u: error_shake(m.chat.id, f"Not found: <code>{t}</code>", reply_to=m.message_id); return
        typing(m.chat.id, 0.6)
        claimed, _ = daily_status(t)
        lines = ["👤 <b>USER INFO</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"🆔 <code>{t}</code>",
                 f"📛 {esc(u.get('first_name','—'))}",
                 f"💎 Credits: <b>{u.get('credits',0)}</b>",
                 f"🔍 Searches: {u.get('searches',0)}",
                 f"👥 Referrals: {u.get('referrals',0)}",
                 f"🎁 Daily: {'Yes' if claimed else 'No'}",
                 f"🚫 Banned: {'Yes' if is_banned(t) else 'No'}"]
        reveal_lines(m.chat.id, lines, interval=0.10, reply_to=m.message_id,
                     final_markup=credit_kb())
    except Exception as e: logger.error(f"_a_chk2: {e}")

# User Manager
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "👥 User Manager"))
def btn_um(m):
    try:
        typing(m.chat.id, 0.5)
        flash(m.chat.id, "👥 <b>User Manager</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Choose:", reply_markup=user_kb())
    except Exception as e: logger.error(f"btn_um: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📋 User List"))
def btn_ul(m):
    try:
        typing(m.chat.id, 0.8)
        ks = sorted(users.keys(), key=lambda k: users[k].get("last_seen",""), reverse=True)[:30]
        lines = ["📋 <b>LATEST 30</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>"]
        for i, k in enumerate(ks, 1):
            u = users[k]
            star = "🚫" if is_banned(k) else "👤"
            nm = (u.get("first_name") or "?")[:12]
            lines.append(f"{i}. {star} <code>{k}</code> {esc(nm)} — 💎{u.get('credits',0)}")
        reveal_lines(m.chat.id, lines, interval=0.06, reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_ul: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🚫 Ban User"))
def btn_bn(m):
    try:
        msg = bot.reply_to(m, "User ID to BAN:"); bot.register_next_step_handler(msg, _bn2)
    except Exception as e: logger.error(f"btn_bn: {e}")

def _bn2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=user_kb()); return
        if not m.text.strip().isdigit(): error_shake(m.chat.id, "Bad.", reply_to=m.message_id); return
        ban_user(m.text.strip())
        flash(m.chat.id, f"🚫 Banned", reply_to=m.message_id)
        bot.send_message(m.chat.id, "User Manager:", reply_markup=user_kb())
    except Exception as e: logger.error(f"_bn2: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "✅ Unban User"))
def btn_ubn(m):
    try:
        msg = bot.reply_to(m, "User ID to UNBAN:"); bot.register_next_step_handler(msg, _ubn2)
    except Exception as e: logger.error(f"btn_ubn: {e}")

def _ubn2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=user_kb()); return
        if not m.text.strip().isdigit(): error_shake(m.chat.id, "Bad.", reply_to=m.message_id); return
        unban_user(m.text.strip())
        flash(m.chat.id, f"✅ Unbanned", reply_to=m.message_id)
        bot.send_message(m.chat.id, "User Manager:", reply_markup=user_kb())
    except Exception as e: logger.error(f"_ubn2: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🚫 Banned List"))
def btn_banlist(m):
    try:
        typing(m.chat.id, 0.5)
        if not banned:
            bot.reply_to(m, "✅ Koi banned nahi.", reply_markup=user_kb()); return
        lines = [f"🚫 <b>BANNED ({len(banned)})</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>"]
        for i, k in enumerate(list(banned)[:50], 1):
            u = users.get(str(k), {})
            nm = (u.get("first_name") or "?")[:15]
            lines.append(f"{i}. <code>{k}</code> {esc(nm)}")
        reveal_lines(m.chat.id, lines, interval=0.06, reply_to=m.message_id,
                     final_markup=user_kb())
    except Exception as e: logger.error(f"btn_banlist: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📤 Export CSV"))
def btn_exp(m):
    try:
        typing(m.chat.id, 1.0)
        buf = io.StringIO(); w = csv.writer(buf)
        w.writerow(["uid","first_name","username","credits","searches","referrals",
                    "referred_by","banned","joined_at","last_seen"])
        for k, u in users.items():
            w.writerow([k, u.get("first_name",""), u.get("username",""),
                        u.get("credits",0), u.get("searches",0), u.get("referrals",0),
                        u.get("referred_by","") or "",
                        "yes" if is_banned(k) else "no",
                        u.get("joined_at",""), u.get("last_seen","")])
        bio = io.BytesIO(buf.getvalue().encode("utf-8")); bio.seek(0)
        bio.name = f"users_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        bot.send_document(m.chat.id, bio,
                          caption=f"📤 <b>{len(users)}</b> users", parse_mode="HTML")
    except Exception as e:
        logger.error(f"btn_exp: {e}")
        error_shake(m.chat.id, f"Fail: {esc(e)}", reply_to=m.message_id)

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📊 User Details"))
def btn_udetails(m):
    try:
        typing(m.chat.id, 0.5)
        tc = sum(u.get("credits",0) for u in users.values())
        ts_ = sum(u.get("spent_credits",0) for u in users.values())
        te = sum(u.get("earned_credits",0) for u in users.values())
        tr = sum(u.get("referrals",0) for u in users.values())
        lines = ["📊 <b>AGGREGATE</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"👥 Users: <b>{len(users)}</b>",
                 f"💎 In system: <b>{tc}</b>",
                 f"💰 Earned: <b>{te}</b>",
                 f"💸 Spent: <b>{ts_}</b>",
                 f"👥 Referrals: <b>{tr}</b>",
                 f"🚫 Banned: <b>{len(banned)}</b>",
                 f"🔥 Active 24h: <b>{active_users_24h()}</b>"]
        reveal_lines(m.chat.id, lines, interval=0.10, reply_to=m.message_id,
                     final_markup=user_kb())
    except Exception as e: logger.error(f"btn_udetails: {e}")

# Search User
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🔍 Search User"))
def btn_srch(m):
    try:
        msg = bot.reply_to(m, "Username/name/ID:")
        bot.register_next_step_handler(msg, _srch2)
    except Exception as e: logger.error(f"btn_srch: {e}")

def _srch2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=admin_kb()); return
        q = m.text.strip().lstrip("@").lower()
        results = []
        for k, u in users.items():
            if q in k.lower() or q in (u.get("username","") or "").lower() \
               or q in (u.get("first_name","") or "").lower():
                results.append((k, u))
        if not results:
            bot.reply_to(m, "❌ No user.", reply_markup=admin_kb()); return
        lines = [f"🔍 <b>Found {len(results[:15])}/{len(results)}</b>",
                 "<code>━━━━━━━━━━━━━━━━━━━━</code>"]
        for k, u in results[:15]:
            nm = (u.get("first_name") or "?")[:15]
            lines.append(f"• <code>{k}</code> ({esc(nm)}) — 💎{u.get('credits',0)}")
        reveal_lines(m.chat.id, lines, interval=0.07, reply_to=m.message_id,
                     final_markup=admin_kb())
    except Exception as e: logger.error(f"_srch2: {e}")

# Top Referrers
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🏆 Top Referrers"))
def btn_topref(m):
    try:
        typing(m.chat.id, 0.8)
        top = sorted(users.items(), key=lambda kv: kv[1].get("referrals",0), reverse=True)[:10]
        lines = ["🏆 <b>TOP REFERRERS</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>"]
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, (k, u) in enumerate(top):
            nm = (u.get("first_name") or "?")[:15]
            lines.append(f"{medals[i]} <code>{k}</code> ({esc(nm)}) — 👥{u.get('referrals',0)}")
        reveal_lines(m.chat.id, lines, interval=0.09, reply_to=m.message_id)
    except Exception as e: logger.error(f"btn_topref: {e}")

# DM User
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🎯 DM User"))
def btn_dm(m):
    try:
        msg = bot.reply_to(m, "User ID:")
        bot.register_next_step_handler(msg, _dm2)
    except Exception as e: logger.error(f"btn_dm: {e}")

def _dm2(m):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=admin_kb()); return
        if not m.text.strip().isdigit():
            error_shake(m.chat.id, "Bad ID.", reply_to=m.message_id); return
        tgt = int(m.text.strip())
        msg = bot.reply_to(m, "Message bhejo:")
        bot.register_next_step_handler(msg, _dm3, tgt)
    except Exception as e: logger.error(f"_dm2: {e}")

def _dm3(m, tgt):
    try:
        if not _has_user(m): return
        if _is_any_button(m.text): bot.reply_to(m, "❌", reply_markup=admin_kb()); return
        try:
            bot.send_message(tgt, m.text, parse_mode="HTML")
            flash(m.chat.id, f"✅ DM → <code>{tgt}</code>", reply_to=m.message_id)
        except Exception as e:
            error_shake(m.chat.id, f"Fail: {esc(e)}", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Admin Panel:", reply_markup=admin_kb())
    except Exception as e: logger.error(f"_dm3: {e}")

# Backup / Restore
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "💾 Backup"))
def btn_backup(m):
    try:
        typing(m.chat.id, 1.0)
        buf = io.BytesIO(json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"))
        buf.seek(0)
        buf.name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        bot.send_document(m.chat.id, buf, caption=f"💾 Backup — {len(users)} users")
    except Exception as e:
        logger.error(f"btn_backup: {e}")
        error_shake(m.chat.id, f"Fail: {esc(e)}", reply_to=m.message_id)

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📥 Restore"))
def btn_restore(m):
    try:
        msg = bot.reply_to(m, "⚠️ Backup .json bhejo:")
        bot.register_next_step_handler(msg, _restore2)
    except Exception as e: logger.error(f"btn_restore: {e}")

def _restore2(m):
    try:
        if not _has_user(m): return
        if not m.document:
            bot.reply_to(m, "❌ File bhejo.", reply_markup=admin_kb()); return
        fi = bot.get_file(m.document.file_id)
        content = bot.download_file(fi.file_path)
        j = json.loads(content.decode("utf-8"))
        if not isinstance(j, dict) or "users" not in j:
            bot.reply_to(m, "❌ Invalid."); return
        with _data_lock:
            data.clear(); data.update(j)
            global users, banned, settings, stats
            users = data["users"]; banned = set(data.get("banned", []))
            settings = data.setdefault("settings", {})
            stats = data.setdefault("stats", {})
            save_data()
        flash(m.chat.id, f"✅ Restored {len(users)} users", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Admin Panel:", reply_markup=admin_kb())
    except Exception as e:
        logger.error(f"_restore2: {e}")
        error_shake(m.chat.id, f"Fail: {esc(e)}", reply_to=m.message_id)

# Activity Log
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📜 Activity Log"))
def btn_log(m):
    try:
        typing(m.chat.id, 0.6)
        recent = activity_log[-25:][::-1]
        if not recent:
            bot.reply_to(m, "📜 No activity.", reply_markup=admin_kb()); return
        lines = [f"📜 <b>Recent {len(recent)}</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>"]
        for e in recent:
            ts = e.get("ts","")[11:19]
            lines.append(f"<code>{ts}</code> [{e.get('action')}] {esc(e.get('details',''))[:55]}")
        reveal_lines(m.chat.id, lines, interval=0.06, reply_to=m.message_id,
                     final_markup=admin_kb())
    except Exception as e: logger.error(f"btn_log: {e}")

# Settings
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "⚙️ Settings"))
def btn_st(m):
    try:
        typing(m.chat.id, 0.5)
        flash(m.chat.id, "⚙️ <b>Settings</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Choose:", reply_markup=settings_kb())
    except Exception as e: logger.error(f"btn_st: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🔧 Maintenance ON"))
def btn_m_on(m):
    try:
        with _data_lock:
            settings["maintenance"] = True; save_data()
        flash(m.chat.id, "🔧 Maintenance ON", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Settings:", reply_markup=settings_kb())
    except Exception as e: logger.error(f"btn_m_on: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🔧 Maintenance OFF"))
def btn_m_off(m):
    try:
        with _data_lock:
            settings["maintenance"] = False; save_data()
        flash(m.chat.id, "✅ Maintenance OFF", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Settings:", reply_markup=settings_kb())
    except Exception as e: logger.error(f"btn_m_off: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🌐 API Toggle"))
def btn_apitgl(m):
    try:
        cur = settings.get("api_enabled", True)
        with _data_lock:
            settings["api_enabled"] = not cur; save_data()
        flash(m.chat.id, f"🌐 API: {'🔴 OFF' if cur else '🟢 ON'}", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Settings:", reply_markup=settings_kb())
    except Exception as e: logger.error(f"btn_apitgl: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "💎 Eco Settings"))
def btn_eco(m):
    try:
        typing(m.chat.id, 0.5)
        lines = ["💎 <b>Economy</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"🔍 Search: <b>{SEARCH_COST}</b>",
                 f"🎉 Signup: <b>{SIGNUP_BONUS}</b>",
                 f"🔗 Referral: <b>{REFERRAL_BONUS}</b>",
                 f"🎁 Daily: <b>{DAILY_FREE_CREDITS}</b>", "",
                 "<i>.env edit karke restart karo.</i>"]
        reveal_lines(m.chat.id, lines, interval=0.14, reply_to=m.message_id,
                     final_markup=settings_kb())
    except Exception as e: logger.error(f"btn_eco: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🧹 Clear Cache"))
def btn_clrcache(m):
    try:
        with _data_lock:
            c = len(username_cache); username_cache.clear(); save_data()
        flash(m.chat.id, f"🧹 Cleared {c}", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Settings:", reply_markup=settings_kb())
    except Exception as e: logger.error(f"btn_clrcache: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📦 Cache Stats"))
def btn_cachestats(m):
    try:
        typing(m.chat.id, 0.5)
        total = len(username_cache)
        hits = cache_stats.get("hits", 0); misses = cache_stats.get("misses", 0)
        bc = cache_stats.get("bot_chat", 0); tg = cache_stats.get("telethon", 0)
        py = cache_stats.get("pyrogram", 0); num = cache_stats.get("numeric", 0)
        tl = hits + misses; hr = (hits / tl * 100) if tl else 0
        lines = ["💾 <b>CACHE</b>", "<code>━━━━━━━━━━━━━━━━━━━━</code>",
                 f"📦 Entries: <b>{total}</b>",
                 f"🎯 Hits: <b>{hits}</b>",
                 f"❌ Misses: <b>{misses}</b>",
                 f"📊 Hit rate: <b>{hr:.1f}%</b>", "",
                 f"🔢 Numeric: {num}",
                 f"🤖 Bot: {bc}",
                 f"🔥 Pyrogram: {py}",
                 f"📱 Telethon: {tg}", "",
                 "TTL: 24h"]
        reveal_lines(m.chat.id, lines, interval=0.10, reply_to=m.message_id,
                     final_markup=settings_kb())
    except Exception as e: logger.error(f"btn_cachestats: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🔄 Reload FJ"))
def btn_rfj(m):
    try:
        typing(m.chat.id, 1.0)
        am = AnimMsg(m.chat.id,
            "🔄 <b>Reloading FJ</b>",
            "🔄 <b>Reloading FJ</b> .",
            "🔄 <b>Reloading FJ</b> ..",
            "🔄 <b>Reloading FJ</b> ...",
            interval=0.3, reply_to=m.message_id)
        am.start(); time.sleep(1.2)
        _validate_fj()
        am.stop(); am.delete()
        bot.send_message(m.chat.id, fj_status_text(), reply_markup=settings_kb())
    except Exception as e: logger.error(f"btn_rfj: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "📊 FJ Status"))
def btn_fjs(m):
    try:
        typing(m.chat.id, 0.5)
        bot.reply_to(m, fj_status_text(), reply_markup=settings_kb())
    except Exception as e: logger.error(f"btn_fjs: {e}")

# Back
@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and _btn_match(m, "🔙 Back to Menu"))
def btn_back(m):
    try:
        uid = m.from_user.id
        if is_banned(uid) and not is_admin(uid): return
        typing(m.chat.id, 0.4)
        bot.reply_to(m, "🏠 <b>Main Menu</b>", reply_markup=main_kb(uid))
    except Exception as e: logger.error(f"btn_back: {e}")

@bot.message_handler(func=lambda m: _private_only(m) and _has_user(m)
                     and is_admin(m.from_user.id) and _btn_match(m, "🔙 Admin Menu"))
def btn_am(m):
    try:
        typing(m.chat.id, 0.4)
        flash(m.chat.id, "👑 <b>Admin Panel</b>", reply_to=m.message_id)
        bot.send_message(m.chat.id, "Choose:", reply_markup=admin_kb())
    except Exception as e: logger.error(f"btn_am: {e}")

# ══════════════════════════════════════════════════════════════
#  TEXT ROUTER
# ══════════════════════════════════════════════════════════════
@bot.message_handler(content_types=['text'], func=lambda m: True)
def text_router(m):
    try:
        if not m.text or not _has_user(m): return
        text = m.text.strip()
        if _is_any_button(text): return
        if text.startswith("/"): return

        uid = m.from_user.id
        if is_banned(uid) and not is_admin(uid): return

        if settings.get("maintenance") and not is_admin(uid):
            if _is_group(m): return
            mm = settings.get("maintenance_msg") or "🔧 Maintenance. Try later."
            error_shake(m.chat.id, mm, reply_to=m.message_id); return

        if _is_group(m):
            if not (_bot_mentioned(m) or _replied_to_bot(m)): return
            q = re.sub(rf"@{BOT_USERNAME}", "", text, flags=re.I).strip()
            if not _valid_input(q):
                flash(m.chat.id, "❌ Send valid <b>@username</b> or <b>ID</b>.",
                      reply_to=m.message_id); return
            if not rate_ok_notify(m): return
            process_lookup(uid, m.chat.id, q, m.message_id, is_group=True)
            return

        if not rate_ok_notify(m): return
        if not ensure_joined(uid, m.chat.id, m.message_id): return

        if _valid_input(text):
            process_lookup(uid, m.chat.id, text, m.message_id); return

        error_shake(m.chat.id,
            "Invalid. Send <b>@username</b> or <b>numeric ID</b>.",
            reply_to=m.message_id)
    except Exception as e: logger.error(f"text_router: {e}")

# ══════════════════════════════════════════════════════════════
#  ENTRY
# ══════════════════════════════════════════════════════════════
def _boot_sequence():
    boot = ["  ╔══════════════════════════════════════╗",
            "  ║  🤖 UINFO BOT  v17.2                 ║",
            "  ║  Pyrogram + Telethon + Cache         ║",
            "  ╚══════════════════════════════════════╝"]
    for line in boot: logger.info(line)
    time.sleep(0.15)

if __name__ == "__main__":
    _boot_sequence()
    if not _init_bot_id():
        logger.critical("❌ BOT_TOKEN INVALID"); sys.exit(1)

    logger.info("=" * 60)
    logger.info("🚀 v17.2 — Multi-layer resolver")
    logger.info(f"👑 Admins ({len(get_all_admins())}): {get_all_admins()}")
    logger.info(f"💎 Search: {SEARCH_COST} | Daily: {DAILY_FREE_CREDITS}")
    logger.info(f"🔒 FJ: {_FJ_ENABLED} | env={len(_FJ_CHANNELS_ENV)} dyn={len(dynamic_fj)}")
    logger.info("=" * 60)

    logger.info("🔥 Initializing Pyrogram…")
    if _init_pyrogram():
        logger.info("✅ Pyrogram ready")
    else:
        logger.warning("⚠️ Pyrogram OFF")

    logger.info("📱 Initializing Telethon…")
    if _init_telethon():
        logger.info("✅ Telethon ready")
    else:
        logger.warning("⚠️ Telethon OFF (optional)")

    logger.info(f"🌐 Resolver status: Pyrogram={'🟢' if _pyro_ready else '🔴'} | "
                f"Telethon={'🟢' if _tg_ready else '🔴'}")

    logger.info("🔍 Validating FJ…")
    _validate_fj()
    logger.info("=" * 60)

    if BOT_ID:
        boot_msg = (
            "🎬 <b>Bot online — v17.2</b>\n"
            "<code>━━━━━━━━━━━━━━━</code>\n"
            f"👑 Admins: <b>{len(get_all_admins())}</b>\n"
            f"💎 Search: {SEARCH_COST}\n"
            f"🔥 Pyrogram: {'🟢 ON' if _pyro_ready else '🔴 OFF'}\n"
            f"📱 Telethon: {'🟢 ON' if _tg_ready else '🔴 OFF'}\n"
            f"🔒 FJ: {'🟢 ON' if _FJ_ACTIVE else '🔴 OFF'}\n"
            f"📢 Channels: <b>{len(_FJ_VALID)}</b>")
        for aid in get_all_admins():
            try: bot.send_message(aid, boot_msg, parse_mode="HTML")
            except: pass

    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down…")
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 401:
            logger.critical("🚨 Token invalid"); sys.exit(1)
        logger.critical(f"💥 Telegram error: {e}")
    except Exception as e:
        logger.critical(f"💥 Crashed: {e}")
        time.sleep(3)
        os.execv(sys.executable, [sys.executable] + sys.argv)
