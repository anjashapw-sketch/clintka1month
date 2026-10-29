import argparse
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TG MANDI PREMIUM TELEGRAM STORE BOT
Features:
- Channel Force-Join Gate with "JOIN" and "VERIFY" buttons.
- Referral System with instant notification to inviter & configurable bonus.
- Main Menu: Buy Accounts, Account, Referrals, Leaderboard.
- 3 Account Types: Spam Account, Non Spam Account, Premium Account (with Spam & Non-Spam sub-types).
- Cheapest account selection & Admin-controlled pricing.
- Live TG Mandi REST API v1 integration for purchases & OTP fetching.
- Full Card System UI: Small Caps typography with capitalized first letters, high-end technical icons.
- MongoDB integration (ClusterGivaway).
- Silent Admin Panel (/admin) exclusively accessible by bot administrators.
"""

import os
import sys
import time
import math
import logging
import asyncio
import re
import io
import random
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from pymongo import MongoClient, ASCENDING, DESCENDING
from PIL import Image, ImageDraw, ImageFont
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    User as TgUser,
    ChatMember,
    WebAppInfo,
    MenuButtonWebApp,
    MenuButtonDefault,
)
from aiohttp import web
from telegram.constants import ParseMode, ChatMemberStatus
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import aiohttp

# ──────────────────────────────────────────────────────────────────────────────
#   CONFIG & CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("TGCardStoreBot")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "9114092127:AAHuXk4Y6340V-tInyK7JX_ZRCwSDnfgjCk").strip()

# Primary permanent super-admin ID
PRIMARY_ADMIN_ID = 8027403165

# Default admin IDs
raw_admins = os.environ.get("ADMIN_IDS", "8954471152").split(",")
ADMIN_IDS = {PRIMARY_ADMIN_ID}
for a in raw_admins:
    try:
        a_clean = re.sub(r"\D", "", a.strip())
        if a_clean:
            ADMIN_IDS.add(int(a_clean))
    except ValueError:
        pass

# MongoDB Connection
MONGO_URL_DEFAULT = os.environ.get(
    "MONGO_URL",
    "mongodb+srv://anjashapw_db_user:anjashapw_db_user"
    "@clustergivaway.j6qctkx.mongodb.net/tgbot?retryWrites=true&w=majority"
    "&appName=ClusterGivaway",
).strip()

MONGO_DB_DEFAULT = os.environ.get("MONGO_DB", "tgbot")

MONGO_COLLECTIONS = (
    "users",
    "orders",
    "deposits",
    "ledger",
    "settings",
)

# TG Mandi REST API
TGMANDI_API_URL = os.environ.get(
    "TGMANDI_API_URL", "https://tgmandi.myvipsite.fun/api/v1"
).rstrip("/")

TGMANDI_API_KEY = os.environ.get(
    "TGMANDI_API_KEY", "tgm_5f31d40394e84b548ff4fbd88fc2ddcc0e133d08"
).strip()

# ──────────────────────────────────────────────────────────────────────────────
#   TYPOGRAPHY & CARD SYSTEM (SMALL CAPS + AESTHETIC ICONS)
# ──────────────────────────────────────────────────────────────────────────────

SMALL_CAPS_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ',
    'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ',
    'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
    's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
}

def to_small_caps(text: str) -> str:
    """
    Converts text to stylized Small Caps while keeping the first letter of each
    word capitalized, matching user specification:
    'yeha font small Cap mey ho and words ka first letter capital mey ho'
    """
    if not text:
        return ""
    words = text.split(" ")
    out = []
    for w in words:
        if not w:
            continue
        first = w[0].upper()
        rest = "".join(SMALL_CAPS_MAP.get(c.lower(), c) for c in w[1:])
        out.append(first + rest)
    return " ".join(out)

DIV = "──────────────────────────"

def mask_phone(phone: str) -> str:
    """Masks middle digits with XXXX while keeping country code and edge digits visible."""
    if not phone:
        return "+XX XXXX XXXX"
    clean = str(phone).strip()
    has_plus = clean.startswith("+")
    digits = re.sub(r"\D", "", clean)
    if len(digits) < 7:
        return clean

    if digits.startswith(("1", "7")):
        cc_len = 1
    elif digits.startswith(("20", "27", "30", "31", "32", "33", "34", "36", "39", "40", "41", "43", "44", "45", "46", "47", "48", "49", "51", "52", "53", "54", "55", "56", "57", "58", "60", "61", "62", "63", "64", "65", "66", "81", "82", "84", "86", "90", "91", "92", "93", "94", "95", "98")):
        cc_len = 2
    elif len(digits) >= 12:
        cc_len = 3
    else:
        cc_len = 1 if len(digits) <= 10 else 2

    cc = digits[:cc_len]
    rest = digits[cc_len:]
    if len(rest) >= 6:
        masked_rest = f"{rest[:2]}XXXX{rest[-4:]}"
    else:
        masked_rest = "XXXX" + rest[-2:]

    prefix = "+" if (has_plus or not clean.startswith("0")) else ""
    return f"{prefix}{cc} {masked_rest}"

def render_profile_card_image(user_id: int, name: str, balance: float, referrals: int, orders: int, avatar_bytes: Optional[bytes] = None) -> bytes:
    """Generates an ultra-crisp dark luxury VIP membership card with user DP and data."""
    W, H = 800, 420
    img = Image.new("RGB", (W, H), color="#0b0e14")
    draw = ImageDraw.Draw(img)

    font_bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_reg_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    try:
        title_f = ImageFont.truetype(font_bold_path, 22)
        sub_f = ImageFont.truetype(font_reg_path, 14)
        h1_f = ImageFont.truetype(font_bold_path, 26)
        num_f = ImageFont.truetype(font_bold_path, 24)
        lbl_f = ImageFont.truetype(font_bold_path, 13)
    except Exception:
        title_f = sub_f = h1_f = num_f = lbl_f = ImageFont.load_default()

    # Outer border & header bar
    draw.rounded_rectangle([8, 8, W-8, H-8], radius=24, outline="#00ffb3", width=2)
    draw.rounded_rectangle([25, 25, W-25, 85], radius=14, fill="#141923")
    draw.text((45, 40), "◈ TG MANDI VIP MEMBERSHIP ◈", font=title_f, fill="#00ffb3")
    draw.text((630, 43), "TIER: VIP MEMBER", font=sub_f, fill="#8c9bb3")

    # Avatar area
    av_box = [45, 115, 205, 275]
    if avatar_bytes:
        try:
            av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((160, 160))
            mask = Image.new("L", (160, 160), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 160, 160), fill=255)
            img.paste(av, (45, 115), mask)
            draw.ellipse(av_box, outline="#00ffb3", width=2)
        except Exception:
            draw.ellipse(av_box, fill="#1b2230", outline="#00ffb3", width=3)
            draw.text((105, 180), "VIP", font=h1_f, fill="#00ffb3")
    else:
        draw.ellipse(av_box, fill="#1b2230", outline="#00ffb3", width=3)
        draw.text((105, 180), "VIP", font=h1_f, fill="#00ffb3")

    # Name & Telegram ID
    clean_name = str(name or "Member")[:18]
    draw.text((230, 115), clean_name.upper(), font=h1_f, fill="#ffffff")
    draw.text((230, 155), f"TELEGRAM ID: {user_id}", font=sub_f, fill="#8c9bb3")

    # Stat Box 1: Balance
    draw.rounded_rectangle([230, 195, 475, 280], radius=12, fill="#141923", outline="#242c3d")
    draw.text((245, 206), "WALLET BALANCE", font=lbl_f, fill="#8c9bb3")
    draw.text((245, 232), f"₹{balance:.2f}", font=num_f, fill="#00ffb3")

    # Stat Box 2: Orders
    draw.rounded_rectangle([495, 195, 740, 280], radius=12, fill="#141923", outline="#242c3d")
    draw.text((510, 206), "TOTAL ORDERS", font=lbl_f, fill="#8c9bb3")
    draw.text((510, 232), f"{orders} Accounts", font=num_f, fill="#ffffff")

    # Bottom Box: Referrals & Status
    draw.rounded_rectangle([230, 300, 740, 385], radius=12, fill="#141923", outline="#242c3d")
    draw.text((245, 314), f"REFERRALS: {referrals} Users", font=sub_f, fill="#ffffff")
    draw.text((245, 345), "STATUS: ACTIVE VIP MEMBER", font=lbl_f, fill="#00ffb3")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

def card_box(title: str, items: List[tuple], footer: Optional[str] = None) -> str:
    """
    Renders a card with blockquote borders, aesthetic technical icons,
    and stylized headers.
    """
    header_sc = to_small_caps(title)
    lines = [f"<b>◈ {header_sc} ◈</b>", DIV, "<blockquote>"]
    for label, val in items:
        lbl_sc = to_small_caps(label)
        lines.append(f"▸ <b>{lbl_sc}:</b> {val}")
    lines.append("</blockquote>")
    if footer:
        lines.append(f"<i>{footer}</i>")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
#   MONGODB DATABASE MANAGER
# ──────────────────────────────────────────────────────────────────────────────

class DatabaseManager:
    def __init__(self, uri: str, db_name: str):
        self.uri = uri
        self.db_name = db_name
        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=3000)
            self.client.admin.command('ping')
            self.db = self.client[self.db_name]
            log.info('Connected to remote MongoDB cluster.')
        except Exception as e:
            log.warning('Remote MongoDB cluster unavailable (%s). Activating local resilient storage.', e)
            try:
                import mongomock
                self.client = mongomock.MongoClient()
                self.db = self.client[self.db_name]
            except Exception:
                pass
        self._ensure_indexes()
        self._init_settings()

    def _ensure_indexes(self):
        try:
            self.db.users.create_index([("user_id", ASCENDING)], unique=True)
            self.db.users.create_index([("referrals", DESCENDING)])
            self.db.orders.create_index([("order_id", ASCENDING)], sparse=True)
            self.db.orders.create_index([("user_id", ASCENDING)])
            self.db.settings.create_index([("key", ASCENDING)], unique=True)
            log.info("MongoDB indexes verified.")
        except Exception as e:
            log.warning("MongoDB index initialization note: %s", e)

    def _init_settings(self):
        defaults = {
            "spam_price": 15.0,
            "nonspam_price": 25.0,
            "prem_spam_price": 35.0,
            "prem_nonspam_price": 50.0,
            "referral_bonus": 5.0,
            "force_channels": [],  # List of dicts: {"chat_id": str, "username": str, "link": str}
            "maintenance": False,
            "admin_ids": [PRIMARY_ADMIN_ID],
            "mini_app_url": "",
        }
        for k, v in defaults.items():
            if self.db.settings.find_one({"key": k}) is None:
                self.db.settings.insert_one({"key": k, "value": v})

    def get_setting(self, key: str, default: Any = None) -> Any:
        doc = self.db.settings.find_one({"key": key})
        if doc and "value" in doc:
            return doc["value"]
        return default

    def set_setting(self, key: str, value: Any):
        self.db.settings.update_one(
            {"key": key},
            {"$set": {"value": value}},
            upsert=True
        )

    def get_admins(self) -> List[int]:
        ids = list(ADMIN_IDS)
        custom_admins = self.get_setting("admin_ids", [])
        if isinstance(custom_admins, list):
            for a in custom_admins:
                try:
                    aid = int(a)
                    if aid not in ids:
                        ids.append(aid)
                except (ValueError, TypeError):
                    pass
        if PRIMARY_ADMIN_ID not in ids:
            ids.insert(0, PRIMARY_ADMIN_ID)
        return ids

    def add_admin(self, user_id: int) -> bool:
        cur = self.get_setting("admin_ids", [])
        if not isinstance(cur, list):
            cur = [PRIMARY_ADMIN_ID]
        if user_id in cur:
            return False
        cur.append(user_id)
        self.set_setting("admin_ids", cur)
        ADMIN_IDS.add(user_id)
        return True

    def remove_admin(self, user_id: int) -> bool:
        if user_id == PRIMARY_ADMIN_ID:
            return False
        cur = self.get_setting("admin_ids", [])
        modified = False
        if isinstance(cur, list) and user_id in cur:
            cur.remove(user_id)
            self.set_setting("admin_ids", cur)
            modified = True
        if user_id in ADMIN_IDS:
            ADMIN_IDS.discard(user_id)
            modified = True
        return modified

    def get_or_create_user(self, user_id: int, first_name: str, username: Optional[str] = None, referrer_id: Optional[int] = None) -> dict:
        u = self.db.users.find_one({"user_id": user_id})
        if not u:
            # Valid referrer check (cannot refer oneself)
            ref = referrer_id if referrer_id and referrer_id != user_id else None
            u = {
                "user_id": user_id,
                "first_name": first_name or "User",
                "username": username or "",
                "balance": 0.0,
                "referrals": 0,
                "referred_by": ref,
                "referral_credited": False,
                "is_verified": False,
                "is_banned": False,
                "total_orders": 0,
                "total_spent": 0.0,
                "created_at": datetime.utcnow(),
            }
            self.db.users.insert_one(u)
        else:
            # Update latest username and name
            upd = {}
            if first_name and u.get("first_name") != first_name:
                upd["first_name"] = first_name
            if username and u.get("username") != username:
                upd["username"] = username
            if upd:
                self.db.users.update_one({"user_id": user_id}, {"$set": upd})
                u.update(upd)
        return u

    def get_user(self, user_id: int) -> Optional[dict]:
        return self.db.users.find_one({"user_id": user_id})

    def update_user(self, user_id: int, **fields):
        self.db.users.update_one({"user_id": user_id}, {"$set": fields})

    def add_balance(self, user_id: int, amount: float, reason: str = "Credit") -> float:
        amt = round(float(amount), 2)
        u = self.db.users.find_one_and_update(
            {"user_id": user_id},
            {"$inc": {"balance": amt}},
            return_document=True
        )
        new_bal = u["balance"] if u else 0.0
        self.db.ledger.insert_one({
            "user_id": user_id,
            "type": "credit",
            "amount": amt,
            "reason": reason,
            "balance_after": new_bal,
            "created_at": datetime.utcnow(),
        })
        return new_bal

    def deduct_balance(self, user_id: int, amount: float, reason: str = "Debit") -> Optional[float]:
        amt = round(float(amount), 2)
        user = self.get_user(user_id)
        if not user or user.get("balance", 0.0) < amt:
            return None
        u = self.db.users.find_one_and_update(
            {"user_id": user_id, "balance": {"$gte": amt}},
            {"$inc": {"balance": -amt, "total_spent": amt}},
            return_document=True
        )
        if not u:
            return None
        new_bal = u["balance"]
        self.db.ledger.insert_one({
            "user_id": user_id,
            "type": "debit",
            "amount": amt,
            "reason": reason,
            "balance_after": new_bal,
            "created_at": datetime.utcnow(),
        })
        return new_bal

    def award_referral(self, new_user_id: int) -> Optional[tuple]:
        """
        Awards referral bonus to the inviter when new user successfully verifies.
        Returns (inviter_id, bonus_amount) if credited, else None.
        """
        user = self.get_user(new_user_id)
        if not user or user.get("referral_credited"):
            return None
        ref_id = user.get("referred_by")
        if not ref_id:
            self.update_user(new_user_id, referral_credited=True)
            return None

        inviter = self.get_user(ref_id)
        if not inviter:
            self.update_user(new_user_id, referral_credited=True)
            return None

        bonus = float(self.get_setting("referral_bonus", 5.0))
        self.db.users.update_one(
            {"user_id": ref_id},
            {"$inc": {"balance": bonus, "referrals": 1}}
        )
        self.db.ledger.insert_one({
            "user_id": ref_id,
            "type": "credit",
            "amount": bonus,
            "reason": f"Referral Bonus (User {new_user_id})",
            "created_at": datetime.utcnow(),
        })
        self.update_user(new_user_id, referral_credited=True)
        return (ref_id, bonus)

    def get_top_referrers(self, limit: int = 10) -> List[dict]:
        return list(self.db.users.find({"referrals": {"$gt": 0}}).sort("referrals", DESCENDING).limit(limit))

    def create_order(self, order_data: dict):
        self.db.orders.insert_one(order_data)
        self.db.users.update_one(
            {"user_id": order_data["user_id"]},
            {"$inc": {"total_orders": 1}}
        )

    def get_order(self, order_id: str) -> Optional[dict]:
        return self.db.orders.find_one({"order_id": order_id})

    def get_user_orders(self, user_id: int, limit: int = 10) -> List[dict]:
        try:
            return list(self.db.orders.find({"user_id": user_id}).sort("created_at", -1).limit(limit))
        except Exception as e:
            log.error("get_user_orders error: %s", e)
            return []

    def get_stats(self) -> dict:
        total_users = self.db.users.count_documents({})
        total_orders = self.db.orders.count_documents({})
        pipeline_sales = [{"$group": {"_id": None, "total": {"$sum": "$price"}, "cost": {"$sum": "$supplier_price"}}}]
        agg_sales = list(self.db.orders.aggregate(pipeline_sales))
        total_sales = agg_sales[0]["total"] if agg_sales else 0.0
        total_cost = agg_sales[0].get("cost", 0.0) if agg_sales else 0.0
        total_profit = max(0.0, total_sales - total_cost)

        pipeline_bal = [{"$group": {"_id": None, "total_bal": {"$sum": "$balance"}, "total_refs": {"$sum": "$referrals"}}}]
        agg_bal = list(self.db.users.aggregate(pipeline_bal))
        total_bal = agg_bal[0]["total_bal"] if agg_bal else 0.0
        total_refs = agg_bal[0].get("total_refs", 0) if agg_bal else 0

        return {
            "total_users": total_users,
            "total_orders": total_orders,
            "total_sales": round(float(total_sales), 2),
            "total_supplier_cost": round(float(total_cost), 2),
            "total_profit": round(float(total_profit), 2),
            "total_user_balance": round(float(total_bal), 2),
            "total_referrals": int(total_refs),
        }

# Global DB instance
db = DatabaseManager(MONGO_URL_DEFAULT, MONGO_DB_DEFAULT)

def is_admin(user_id: int) -> bool:
    if not user_id:
        return False
    if user_id == PRIMARY_ADMIN_ID:
        return True
    return user_id in db.get_admins()


# ──────────────────────────────────────────────────────────────────────────────
#   TG MANDI OFFICIAL REST API CLIENT
# ──────────────────────────────────────────────────────────────────────────────

class TGMandiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=45),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
                    "X-Api-Key": self.api_key,
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json, text/plain, */*",
                }
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_balance(self) -> dict:
        s = await self._get_session()
        try:
            async with s.get(f"{self.base_url}/me") as r:
                data = await r.json(content_type=None)
                if r.status == 200 and data.get("ok"):
                    u = (data.get("data") or {}).get("user") or {}
                    return {"ok": True, "balance": float(u.get("balance") or 0.0), "user": u.get("username")}
                return {"ok": False, "error": data.get("error", "Unauthorized")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_account_details(self) -> dict:
        """Fetches full account and reseller stats from /me."""
        s = await self._get_session()
        try:
            async with s.get(f"{self.base_url}/me", timeout=aiohttp.ClientTimeout(total=8)) as r:
                d = await r.json(content_type=None)
                if r.status == 200 and d.get("ok"):
                    data_obj = d.get("data") or {}
                    return {
                        "ok": True,
                        "user": data_obj.get("user") or {},
                        "stats": data_obj.get("stats") or {},
                    }
                return {"ok": False, "error": d.get("error", "Unauthorized")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_api_orders(self, limit: int = 8) -> list:
        """Fetches recent orders directly from TG Mandi supplier API."""
        s = await self._get_session()
        try:
            async with s.get(f"{self.base_url}/orders?limit={limit}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                d = await r.json(content_type=None)
                if r.status == 200 and d.get("ok"):
                    return (d.get("data") or {}).get("orders") or []
        except Exception as e:
            log.debug("get_api_orders error: %s", e)
        return []

    async def get_api_transactions(self, limit: int = 8) -> list:
        """Fetches recent transactions from TG Mandi supplier API."""
        s = await self._get_session()
        try:
            async with s.get(f"{self.base_url}/transactions", timeout=aiohttp.ClientTimeout(total=10)) as r:
                d = await r.json(content_type=None)
                if r.status == 200 and d.get("ok"):
                    txs = (d.get("data") or {}).get("transactions") or []
                    return txs[:limit]
        except Exception as e:
            log.debug("get_api_transactions error: %s", e)
        return []

    async def get_live_stock_counts(self) -> dict:
        """Fetches live stock count across major countries."""
        s = await self._get_session()
        countries = ["BGD", "USA", "IND", "GBR", "PHL", "IDN", "EGY", "BRA", "TUR"]
        counts = {}

        async def count_c(cc):
            try:
                async with s.get(f"{self.base_url}/accounts?country={cc}&limit=40", timeout=aiohttp.ClientTimeout(total=6)) as r:
                    if r.status == 200:
                        d = await r.json(content_type=None)
                        items = (d.get("data") or {}).get("items") or []
                        return cc, len(items)
            except Exception:
                pass
            return cc, 0

        res = await asyncio.gather(*[count_c(c) for c in countries], return_exceptions=True)
        for r in res:
            if isinstance(r, tuple):
                counts[r[0]] = r[1]
        return counts

    async def get_candidates(self, acc_type: str, limit: int = 5) -> List[dict]:
        """
        Fast multi-candidate search across top high-stock countries.
        Returns top matching candidate accounts sorted by price (or premium days).
        """
        s = await self._get_session()
        # Top 5 high-stock countries in TG Mandi for ultra-fast parallel fetch (<1.8s)
        countries = ["BGD", "USA", "IND", "PHL", "GBR"]

        async def fetch_country(cc):
            url = f"{self.base_url}/accounts?country={cc}&limit=40&sort=price_to_up"
            try:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=4)) as r:
                    if r.status == 200:
                        d = await r.json(content_type=None)
                        data_obj = d.get("data") or {}
                        return data_obj.get("items") or data_obj.get("accounts") or []
            except Exception as e:
                log.debug("fetch_country %s error: %s", cc, e)
            return []

        results = await asyncio.gather(*[fetch_country(c) for c in countries], return_exceptions=True)
        all_candidates = []
        for res in results:
            if isinstance(res, list):
                for it in res:
                    if float(it.get("price") or 0.0) > 0 and it.get("id"):
                        all_candidates.append(it)

        if not all_candidates:
            return []

        filtered = []
        for it in all_candidates:
            spam = str(it.get("spam", "")).lower()
            prem = str(it.get("premium", "")).lower()

            if acc_type == "spam":
                if spam == "yes":
                    filtered.append(it)
            elif acc_type == "nonspam":
                if spam == "no":
                    filtered.append(it)
            elif acc_type == "prem_spam":
                if prem == "yes" and spam == "yes":
                    filtered.append(it)
            elif acc_type == "prem_nonspam":
                if prem == "yes" and spam != "yes":
                    filtered.append(it)

        # Fallback for nonspam: if no strictly 'no' accounts in stock, include 'unknown'
        if acc_type == "nonspam" and not filtered:
            for it in all_candidates:
                if str(it.get("spam", "")).lower() in ("no", "unknown"):
                    filtered.append(it)

        # Fallback for premium: if no strict premium with spam flag, take any available premium
        if "prem" in acc_type and not filtered:
            for it in all_candidates:
                if str(it.get("premium", "")).lower() == "yes":
                    filtered.append(it)

        if not filtered:
            return []

        # Sort accounts
        if "prem" in acc_type:
            # Highest premium days + cheapest price
            filtered.sort(key=lambda x: (
                -float(x.get("premium_expires") or x.get("premium_until") or x.get("premium_days") or 0),
                float(x.get("price") or 9999)
            ))
        else:
            # Cheapest price
            filtered.sort(key=lambda x: float(x.get("price") or 9999))

        return filtered[:limit]

    async def search_account(self, acc_type: str) -> Optional[dict]:
        candidates = await self.get_candidates(acc_type, limit=1)
        return candidates[0] if candidates else None

    async def buy_account(self, item_id: str, max_price: float = 500.0) -> dict:
        """
        Executes real account purchase through POST /buy on TG Mandi API.
        Uses max_price=500.0 so TG Mandi accepts purchase with generous headroom.
        """
        s = await self._get_session()
        payload = {"id": str(item_id), "max_price": float(max_price), "price": float(max_price)}
        try:
            async with s.post(f"{self.base_url}/buy", json=payload, timeout=aiohttp.ClientTimeout(total=25)) as r:
                d = await r.json(content_type=None)
                if r.status == 200 and d.get("ok"):
                    ord_data = (d.get("data") or {}).get("order") or d.get("order") or {}
                    order_no = ord_data.get("order_no") or str(item_id)
                    phone = ord_data.get("phone") or ""
                    password = ord_data.get("password") or ""
                    return {
                        "ok": True,
                        "order_no": order_no,
                        "phone": phone,
                        "password": password,
                        "price": float(ord_data.get("price") or 0.0),
                        "raw_order": ord_data,
                    }
                err_obj = d.get("error")
                if isinstance(err_obj, dict):
                    err_msg = err_obj.get("message") or err_obj.get("code") or f"HTTP {r.status}"
                else:
                    err_msg = str(err_obj or d.get("message") or f"HTTP {r.status}")
                return {"ok": False, "error": err_msg}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def get_otp_code(self, order_id: str, order: Optional[dict] = None) -> dict:
        """
        Queries /orders/{id}/code to fetch real login OTP from TG Mandi API.
        """
        # If code already cached in DB, return it immediately
        if order and order.get("last_code"):
            return {"ok": True, "code": str(order["last_code"]), "cached": True}

        s = await self._get_session()
        candidates = [str(order_id)]
        if order and order.get("item_id") and str(order.get("item_id")) not in candidates:
            candidates.append(str(order["item_id"]))

        last_err = "Waiting for SMS code..."
        for target in candidates:
            try:
                async with s.get(f"{self.base_url}/orders/{target}/code", timeout=aiohttp.ClientTimeout(total=15)) as r:
                    d = await r.json(content_type=None)
                    if r.status == 200 and d.get("ok"):
                        raw_code = (d.get("data") or {}).get("code") or d.get("code")
                        if raw_code:
                            code_str = str(raw_code).strip()
                            db.db.orders.update_one({"order_id": order_id}, {"$set": {"last_code": code_str}})
                            return {"ok": True, "code": code_str}
                    else:
                        err_obj = d.get("error")
                        if isinstance(err_obj, dict):
                            last_err = err_obj.get("message") or last_err
                        elif err_obj:
                            last_err = str(err_obj)
            except Exception as e:
                log.debug("otp fetch error for %s: %s", target, e)

        return {"ok": False, "waiting": True, "error": last_err}

# Global API instance
tgmandi = TGMandiClient(TGMANDI_API_URL, TGMANDI_API_KEY)

async def send_payout_channel_notification(bot, order: dict):
    channel = db.get_setting("payout_channel")
    if not channel:
        return
    try:
        masked = mask_phone(order.get("phone", ""))
        price = float(order.get("price", 0.0))
        t_label = order.get("type_label") or to_small_caps(str(order.get("type", "Account")).replace("_", " "))
        uid = order.get("user_id", 0)
        bot_info = await bot.get_me()
        bot_uname = bot_info.username or "StoreBot"

        txt = card_box(
            "Nᴇᴡ Aᴄᴄᴏᴜɴᴛ Pᴜʀᴄʜᴀsᴇᴅ",
            [
                ("Tʏᴘᴇ", t_label),
                ("Pʀɪᴄᴇ", f"₹{price:.2f}"),
                ("Nᴜᴍʙᴇʀ", f"<code>{masked}</code>"),
                ("Bᴜʏᴇʀ", f"Usᴇʀ #{str(uid)[-4:]}"),
                ("Dᴇʟɪᴠᴇʀʏ", "Iɴsᴛᴀɴᴛ (SMS / OTP)"),
                ("Sᴛᴀᴛᴜs", "Dᴇʟɪᴠᴇʀᴇᴅ"),
            ],
            footer="Tʜᴀɴᴋ ʏᴏᴜ ғᴏʀ ᴘᴜʀᴄʜᴀsɪɴɢ ғʀᴏᴍ ᴏᴜʀ sᴛᴏʀᴇ!"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◈ Bᴜʏ Aᴄᴄᴏᴜɴᴛ Nᴏᴡ", url=f"https://t.me/{bot_uname}")]])
        await bot.send_message(chat_id=channel, text=txt, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        log.warning("Payout channel notification note for %s: %s", channel, e)


# ──────────────────────────────────────────────────────────────────────────────
#   CHANNEL GATE & VERIFICATION HELPER
# ──────────────────────────────────────────────────────────────────────────────

async def check_user_joined_all(bot, user_id: int) -> bool:
    """Checks if the user has joined all configured force-join channels."""
    channels = db.get_setting("force_channels", [])
    if not channels:
        return True
    for ch in channels:
        cid = ch.get("chat_id") or ch.get("username")
        if not cid:
            continue
        try:
            member = await bot.get_chat_member(cid, user_id)
            if member.status in (
                ChatMemberStatus.LEFT,
                ChatMemberStatus.BANNED,
                "left",
                "kicked",
            ):
                return False
        except Exception as e:
            log.debug("Channel membership check failed for %s: %s", cid, e)
            # If bot lacks admin rights or channel private, proceed safely
            continue
    return True

def get_join_keyboard() -> InlineKeyboardMarkup:
    """Builds keyboard with 'JOIN' button(s) and 'VERIFY' button."""
    channels = db.get_setting("force_channels", [])
    keyboard = []
    for ch in channels:
        link = ch.get("link") or (f"https://t.me/{ch.get('username').lstrip('@')}" if ch.get("username") else None)
        if link:
            keyboard.append([InlineKeyboardButton("◈ JOIN", url=link)])
    if not keyboard:
        # Default placeholder if admin hasn't added any channel link
        keyboard.append([InlineKeyboardButton("◈ JOIN", url="https://t.me/telegram")])

    keyboard.append([InlineKeyboardButton("◈ VERIFY", callback_data="verify_join")])
    return InlineKeyboardMarkup(keyboard)


# ──────────────────────────────────────────────────────────────────────────────
#   MAIN MENU & KEYBOARDS
# ──────────────────────────────────────────────────────────────────────────────

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    mini_url = (db.get_setting("mini_app_url") or "").strip()
    rows = []
    if mini_url.startswith("https://"):
        rows.append([InlineKeyboardButton("⚡ Oᴘᴇɴ Mɪɴɪ Aᴘᴘ", web_app=WebAppInfo(url=mini_url))])
    elif mini_url:
        rows.append([InlineKeyboardButton("⚡ Oᴘᴇɴ Mɪɴɪ Aᴘᴘ", url=mini_url)])

    rows.extend([
        [InlineKeyboardButton("◈ Bᴜʏ Aᴄᴄᴏᴜɴᴛs", callback_data="menu_buy")],
        [
            InlineKeyboardButton("◈ Aᴄᴄᴏᴜɴᴛ", callback_data="menu_account"),
            InlineKeyboardButton("◈ Rᴇғᴇʀʀᴀʟs", callback_data="menu_referrals"),
        ],
        [InlineKeyboardButton("◈ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ", callback_data="menu_leaderboard")],
    ])
    return InlineKeyboardMarkup(rows)

def get_buy_menu_keyboard() -> InlineKeyboardMarkup:
    spam_p = db.get_setting("spam_price", 15.0)
    nonspam_p = db.get_setting("nonspam_price", 25.0)
    prem_p = db.get_setting("prem_spam_price", 35.0)

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"◈ Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ • ₹{spam_p:.2f}", callback_data="buy_type_spam")],
        [InlineKeyboardButton(f"◈ Nᴏɴ Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ • ₹{nonspam_p:.2f}", callback_data="buy_type_nonspam")],
        [InlineKeyboardButton(f"◈ Pʀᴇᴍɪᴜᴍ Aᴄᴄᴏᴜɴᴛ • Fʀᴏᴍ ₹{prem_p:.2f}", callback_data="buy_type_premium")],
        [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Mᴇɴᴜ", callback_data="main_menu")],
    ])

def get_premium_submenu_keyboard() -> InlineKeyboardMarkup:
    p_spam = db.get_setting("prem_spam_price", 35.0)
    p_nonspam = db.get_setting("prem_nonspam_price", 50.0)

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"◈ Pʀᴇᴍɪᴜᴍ Sᴘᴀᴍ • ₹{p_spam:.2f}", callback_data="buy_type_prem_spam")],
        [InlineKeyboardButton(f"◈ Pʀᴇᴍɪᴜᴍ Nᴏɴ-Sᴘᴀᴍ • ₹{p_nonspam:.2f}", callback_data="buy_type_prem_nonspam")],
        [InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="menu_buy")],
    ])

def get_confirm_keyboard(acc_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◈ Cᴏɴғɪʀᴍ Bᴜʏ", callback_data=f"exec_buy_{acc_type}")],
        [InlineKeyboardButton("« Cᴀɴᴄᴇʟ", callback_data="menu_buy")],
    ])


# ──────────────────────────────────────────────────────────────────────────────
#   BOT HANDLERS: /start & VERIFICATION
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return

    # Check maintenance mode
    if db.get_setting("maintenance", False) and not is_admin(user.id):
        txt = card_box("Mᴀɪɴᴛᴇɴᴀɴᴄᴇ Mᴏᴅᴇ", [
            ("Sᴛᴀᴛᴜs", "Uɴᴅᴇʀ Sᴄʜᴇᴅᴜʟᴇᴅ Mᴀɪɴᴛᴇɴᴀɴᴄᴇ"),
            ("Nᴏᴛᴇ", "Pʟᴇᴀsᴇ Cʜᴇᴄᴋ Bᴀᴄᴋ Sʜᴏʀᴛʟʏ"),
        ])
        await msg.reply_text(txt, parse_mode=ParseMode.HTML)
        return

    # Process Referral Argument
    ref_id = None
    if ctx.args:
        raw_arg = ctx.args[0].strip()
        digits = re.sub(r"\D", "", raw_arg)
        if digits:
            try:
                ref_id = int(digits)
            except ValueError:
                pass

    u_data = db.get_or_create_user(user.id, user.first_name, user.username, referrer_id=ref_id)
    if u_data.get("is_banned"):
        return

    # Verify Channel Membership
    is_joined = await check_user_joined_all(ctx.bot, user.id)
    if not is_joined:
        txt = card_box(
            "Cʜᴀɴɴᴇʟ Vᴇʀɪғɪᴄᴀᴛɪᴏɴ",
            [
                ("Rᴇǫᴜɪʀᴇᴍᴇɴᴛ", "Jᴏɪɴ Oᴜʀ Oғғɪᴄɪᴀʟ Cʜᴀɴɴᴇʟs"),
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Tᴀᴘ JOIN, Tʜᴇɴ Tᴀᴘ VERIFY"),
            ],
            footer="Yᴏᴜ ᴍᴜsᴛ ʙᴇ ᴀ ᴍᴇᴍʙᴇʀ ᴛᴏ ᴀᴄᴄᴇss ᴛʜᴇ sᴛᴏʀᴇ."
        )
        await msg.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=get_join_keyboard())
        return

    # User is verified
    db.update_user(user.id, is_verified=True)
    credited = db.award_referral(user.id)
    if credited:
        inviter_id, bonus = credited
        try:
            notif = card_box(
                "Rᴇғᴇʀʀᴀʟ Cᴏᴍᴘʟᴇᴛᴇᴅ",
                [
                    ("Nᴇᴡ Usᴇʀ", f"<code>{user.id}</code> ({user.first_name})"),
                    ("Bᴏɴᴜs Aᴡᴀʀᴅᴇᴅ", f"+₹{bonus:.2f}"),
                    ("Sᴛᴀᴛᴜs", "Cʀᴇᴅɪᴛᴇᴅ Tᴏ Yᴏᴜʀ Bᴀʟᴀɴᴄᴇ"),
                ],
                footer="Kᴇᴇᴘ sʜᴀʀɪɴɢ ʏᴏᴜʀ ʟɪɴᴋ ᴛᴏ ᴇᴀʀɴ ᴍᴏʀᴇ!"
            )
            await ctx.bot.send_message(inviter_id, notif, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    # Open Main Menu
    txt = card_box(
        "Wᴇʟᴄᴏᴍᴇ Tᴏ Sᴛᴏʀᴇ",
        [
            ("Usᴇʀ", user.first_name),
            ("Usᴇʀ ID", f"<code>{user.id}</code>"),
            ("Bᴀʟᴀɴᴄᴇ", f"₹{u_data.get('balance', 0.0):.2f}"),
            ("Sᴛᴀᴛᴜs", "Aᴄᴛɪᴠᴇ"),
        ],
        footer="Sᴇʟᴇᴄᴛ ᴀɴ ᴏᴘᴛɪᴏɴ ғʀᴏᴍ ᴛʜᴇ ᴍᴇɴᴜ ʙᴇʟᴏᴡ."
    )
    await msg.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=get_main_menu_keyboard())


async def cb_verify_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    is_joined = await check_user_joined_all(ctx.bot, user.id)

    if not is_joined:
        await q.answer("❌ Pʟᴇᴀsᴇ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ғɪʀsᴛ, ᴛʜᴇɴ ᴛᴀᴘ Vᴇʀɪғʏ.", show_alert=True)
        return

    await q.answer("✅ Vᴇʀɪғɪᴄᴀᴛɪᴏɴ Sᴜᴄᴄᴇssғᴜʟ!")
    db.update_user(user.id, is_verified=True)

    credited = db.award_referral(user.id)
    if credited:
        inviter_id, bonus = credited
        try:
            notif = card_box(
                "Rᴇғᴇʀʀᴀʟ Cᴏᴍᴘʟᴇᴛᴇᴅ",
                [
                    ("Nᴇᴡ Usᴇʀ", f"<code>{user.id}</code> ({user.first_name})"),
                    ("Bᴏɴᴜs Aᴡᴀʀᴅᴇᴅ", f"+₹{bonus:.2f}"),
                    ("Sᴛᴀᴛᴜs", "Cʀᴇᴅɪᴛᴇᴅ Tᴏ Yᴏᴜʀ Bᴀʟᴀɴᴄᴇ"),
                ],
                footer="Kᴇᴇᴘ sʜᴀʀɪɴɢ ʏᴏᴜʀ ʟɪɴᴋ ᴛᴏ ᴇᴀʀɴ ᴍᴏʀᴇ!"
            )
            await ctx.bot.send_message(inviter_id, notif, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    u_data = db.get_user(user.id) or {}
    txt = card_box(
        "Wᴇʟᴄᴏᴍᴇ Tᴏ Sᴛᴏʀᴇ",
        [
            ("Usᴇʀ", user.first_name),
            ("Usᴇʀ ID", f"<code>{user.id}</code>"),
            ("Bᴀʟᴀɴᴄᴇ", f"₹{u_data.get('balance', 0.0):.2f}"),
            ("Sᴛᴀᴛᴜs", "Aᴄᴛɪᴠᴇ"),
        ],
        footer="Sᴇʟᴇᴄᴛ ᴀɴ ᴏᴘᴛɪᴏɴ ғʀᴏᴍ ᴛʜᴇ ᴍᴇɴᴜ ʙᴇʟᴏᴡ."
    )
    await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=get_main_menu_keyboard())


async def send_or_edit(q, text: str, reply_markup=None):
    """Safely updates current message or sends a new one if current is a photo."""
    try:
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except Exception:
        if q.message:
            try:
                await q.message.delete()
            except Exception:
                pass
            await q.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


# ──────────────────────────────────────────────────────────────────────────────
#   MAIN MENU & SUB-PAGES
# ──────────────────────────────────────────────────────────────────────────────

async def cb_main_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    u_data = db.get_user(user.id) or {}

    txt = card_box(
        "Wᴇʟᴄᴏᴍᴇ Tᴏ Sᴛᴏʀᴇ",
        [
            ("Usᴇʀ", user.first_name),
            ("Usᴇʀ ID", f"<code>{user.id}</code>"),
            ("Bᴀʟᴀɴᴄᴇ", f"₹{u_data.get('balance', 0.0):.2f}"),
            ("Sᴛᴀᴛᴜs", "Aᴄᴛɪᴠᴇ"),
        ],
        footer="Sᴇʟᴇᴄᴛ ᴀɴ ᴏᴘᴛɪᴏɴ ғʀᴏᴍ ᴛʜᴇ ᴍᴇɴᴜ ʙᴇʟᴏᴡ."
    )
    await send_or_edit(q, txt, get_main_menu_keyboard())


async def cb_menu_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    u_data = db.get_user(user.id) or {}

    txt = card_box(
        "Bᴜʏ Aᴄᴄᴏᴜɴᴛs",
        [
            ("Yᴏᴜʀ Bᴀʟᴀɴᴄᴇ", f"₹{u_data.get('balance', 0.0):.2f}"),
            ("Aᴠᴀɪʟᴀʙʟᴇ Tʏᴘᴇs", "Sᴘᴀᴍ, Nᴏɴ-Sᴘᴀᴍ, Pʀᴇᴍɪᴜᴍ"),
            ("Dᴇʟɪᴠᴇʀʏ", "Iɴsᴛᴀɴᴛ (SMS / OTP)"),
        ],
        footer="Cʜᴏᴏsᴇ ᴀɴ ᴀᴄᴄᴏᴜɴᴛ ᴄᴀᴛᴇɢᴏʀʏ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ."
    )
    await send_or_edit(q, txt, get_buy_menu_keyboard())


async def cb_menu_account(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    u_data = db.get_user(user.id) or {}
    created = u_data.get("created_at")
    created_str = created.strftime("%d %b %Y") if isinstance(created, datetime) else "N/A"

    bal = float(u_data.get("balance", 0.0))
    refs = int(u_data.get("referrals", 0))
    orders_cnt = int(u_data.get("total_orders", 0))

    # Fetch User Avatar bytes if available
    avatar_bytes = None
    try:
        photos = await ctx.bot.get_user_profile_photos(user.id, limit=1)
        if photos and photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            tg_file = await ctx.bot.get_file(file_id)
            avatar_bytes = await tg_file.download_as_bytearray()
    except Exception as e:
        log.debug("User avatar fetch note: %s", e)

    # Render dynamic VIP Profile Card
    card_bytes = render_profile_card_image(
        user_id=user.id,
        name=user.first_name,
        balance=bal,
        referrals=refs,
        orders=orders_cnt,
        avatar_bytes=avatar_bytes
    )

    caption = card_box(
        "Usᴇʀ Pʀᴏғɪʟᴇ",
        [
            ("Usᴇʀ", user.first_name),
            ("Usᴇʀ ID", f"<code>{user.id}</code>"),
            ("Usᴇʀɴᴀᴍᴇ", f"@{user.username}" if user.username else "N/A"),
            ("Bᴀʟᴀɴᴄᴇ", f"₹{bal:.2f}"),
            ("Rᴇғᴇʀʀᴀʟs", str(refs)),
            ("Tᴏᴛᴀʟ Oʀᴅᴇʀs", str(orders_cnt)),
            ("Tᴏᴛᴀʟ Sᴘᴇɴᴛ", f"₹{u_data.get('total_spent', 0.0):.2f}"),
            ("Jᴏɪɴᴇᴅ Dᴀᴛᴇ", created_str),
        ],
        footer="Yᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɪs ᴠᴇʀɪғɪᴇᴅ ᴀɴᴅ ɪɴ ɢᴏᴏᴅ sᴛᴀɴᴅɪɴɢ."
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("◈ Mʏ Aᴄᴄᴏᴜɴᴛs", callback_data="my_accounts")],
        [InlineKeyboardButton("◈ Rᴇғᴇʀʀᴀʟs", callback_data="menu_referrals")],
        [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Mᴇɴᴜ", callback_data="main_menu")],
    ])

    if q.message:
        try:
            await q.message.delete()
        except Exception:
            pass
    await ctx.bot.send_photo(
        chat_id=user.id,
        photo=card_bytes,
        caption=caption,
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )


async def cb_my_accounts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user

    orders = db.get_user_orders(user.id, limit=10)

    if not orders:
        txt = card_box(
            "Mʏ Pᴜʀᴄʜᴀsᴇᴅ Aᴄᴄᴏᴜɴᴛs",
            [
                ("Sᴛᴀᴛᴜs", "Nᴏ Aᴄᴄᴏᴜɴᴛs Pᴜʀᴄʜᴀsᴇᴅ Yᴇᴛ"),
                ("Tɪᴘ", "Gᴏ ᴛᴏ Bᴜʏ Aᴄᴄᴏᴜɴᴛs ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʀsᴛ ᴀᴄᴄᴏᴜɴᴛ!"),
            ],
            footer="Aʟʟ ʏᴏᴜʀ ᴘᴜʀᴄʜᴀsᴇᴅ ᴀᴄᴄᴏᴜɴᴛs ᴡɪʟʟ ᴀᴘᴘᴇᴀʀ ʜᴇʀᴇ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Bᴜʏ Aᴄᴄᴏᴜɴᴛs", callback_data="menu_buy")],
            [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Pʀᴏғɪʟᴇ", callback_data="menu_account")],
            [InlineKeyboardButton("« Mᴀɪɴ Mᴇɴᴜ", callback_data="main_menu")],
        ])
        await send_or_edit(q, txt, kb)
        return

    items = []
    btn_rows = []
    for i, o in enumerate(orders, 1):
        phone = o.get("phone", "Unknown")
        oid = o.get("order_id", "N/A")
        t_label = o.get("type_label") or to_small_caps(str(o.get("type", "Account")).replace("_", " "))
        c_at = o.get("created_at")
        date_str = c_at.strftime("%d %b %H:%M") if isinstance(c_at, datetime) else "Recent"
        items.append((f"#{i} {t_label}", f"<code>{phone}</code> • ₹{o.get('price', 0):.2f} ({date_str})"))

        btn_rows.append([InlineKeyboardButton(f"📱 {phone} • Get OTP", callback_data=f"get_otp_{oid}")])

    btn_rows.append([InlineKeyboardButton("◈ Bᴜʏ Mᴏʀᴇ Aᴄᴄᴏᴜɴᴛs", callback_data="menu_buy")])
    btn_rows.append([InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Pʀᴏғɪʟᴇ", callback_data="menu_account"),
                     InlineKeyboardButton("« Mᴀɪɴ Mᴇɴᴜ", callback_data="main_menu")])

    txt = card_box(
        "Mʏ Pᴜʀᴄʜᴀsᴇᴅ Aᴄᴄᴏᴜɴᴛs",
        items,
        footer="Tᴀᴘ ᴀɴ ᴀᴄᴄᴏᴜɴᴛ ʙᴇʟᴏᴡ ᴛᴏ ғᴇᴛᴄʜ ɪᴛs ʟᴏɢɪɴ OTP."
    )
    await send_or_edit(q, txt, InlineKeyboardMarkup(btn_rows))


async def cb_menu_referrals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    u_data = db.get_user(user.id) or {}
    bot_info = await ctx.bot.get_me()
    bot_uname = bot_info.username or "Bot"
    ref_link = f"https://t.me/{bot_uname}?start=ref_{user.id}"

    bonus = db.get_setting("referral_bonus", 5.0)
    refs = u_data.get("referrals", 0)
    total_earned = refs * bonus

    txt = card_box(
        "Rᴇғᴇʀʀᴀʟ Sʏsᴛᴇᴍ",
        [
            ("Yᴏᴜʀ Rᴇғᴇʀʀᴀʟ Lɪɴᴋ", f"<code>{ref_link}</code>"),
            ("Tᴏᴛᴀʟ Rᴇғᴇʀʀᴀʟs", str(refs)),
            ("Bᴏɴᴜs Pᴇʀ Rᴇғᴇʀʀᴀʟ", f"₹{bonus:.2f}"),
            ("Tᴏᴛᴀʟ Eᴀʀɴᴇᴅ", f"₹{total_earned:.2f}"),
        ],
        footer="Sʜᴀʀᴇ ʏᴏᴜʀ ʟɪɴᴋ. Wʜᴇɴ ᴀ ғʀɪᴇɴᴅ ᴊᴏɪɴs ᴀɴᴅ ᴠᴇʀɪғɪᴇs, ʏᴏᴜ ɢᴇᴛ ɪɴsᴛᴀɴᴛ ʙᴀʟᴀɴᴄᴇ!"
    )
    share_url = f"https://t.me/share/url?url={ref_link}&text=Join%20this%20Telegram%20store%20bot!"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("◈ Sʜᴀʀᴇ Lɪɴᴋ", url=share_url)],
        [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Mᴇɴᴜ", callback_data="main_menu")],
    ])
    await send_or_edit(q, txt, kb)


async def cb_menu_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    leaders = db.get_top_referrers(limit=10)

    items = []
    if not leaders:
        items.append(("Sᴛᴀᴛᴜs", "Nᴏ Rᴇғᴇʀʀᴀʟs Rᴇᴄᴏʀᴅᴇᴅ Yᴇᴛ"))
    else:
        for idx, leader in enumerate(leaders, 1):
            name = leader.get("first_name") or f"User {leader.get('user_id')}"
            refs = leader.get("referrals", 0)
            items.append((f"Rᴀɴᴋ #{idx}", f"{name} • {refs} Rᴇғs"))

    txt = card_box(
        "Tᴏᴘ 10 Rᴇғᴇʀʀᴀʟ Lᴇᴀᴅᴇʀʙᴏᴀʀᴅ",
        items,
        footer="Rᴇғᴇʀ ᴍᴏʀᴇ ᴜsᴇʀs ᴛᴏ ᴄʟɪᴍʙ ᴛʜᴇ ʟᴇᴀᴅᴇʀʙᴏᴀʀᴅ ʀᴀɴᴋɪɴɢs!"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Mᴇɴᴜ", callback_data="main_menu")]])
    await send_or_edit(q, txt, kb)


# ──────────────────────────────────────────────────────────────────────────────
#   PURCHASE FLOW: SPAM, NON-SPAM, PREMIUM
# ──────────────────────────────────────────────────────────────────────────────

ACC_TYPE_INFO = {
    "spam": {"name": "Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ", "setting_key": "spam_price", "desc": "Cʜᴇᴀᴘᴇsᴛ Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ"},
    "nonspam": {"name": "Nᴏɴ Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ", "setting_key": "nonspam_price", "desc": "Cʟᴇᴀɴ Sᴘᴀᴍ-Fʀᴇᴇ Aᴄᴄᴏᴜɴᴛ"},
    "prem_spam": {"name": "Pʀᴇᴍɪᴜᴍ Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ", "setting_key": "prem_spam_price", "desc": "Cʜᴇᴀᴘᴇsᴛ Pʀᴇᴍɪᴜᴍ Aᴄᴄᴏᴜɴᴛ (Mᴀx Dᴜʀᴀᴛɪᴏɴ)"},
    "prem_nonspam": {"name": "Pʀᴇᴍɪᴜᴍ Nᴏɴ-Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ", "setting_key": "prem_nonspam_price", "desc": "Cʟᴇᴀɴ Pʀᴇᴍɪᴜᴍ Aᴄᴄᴏᴜɴᴛ (Mᴀx Dᴜʀᴀᴛɪᴏɴ)"},
}

async def execute_store_purchase(user_id: int, acc_type: str) -> dict:
    """
    Central purchasing engine used by both Telegram Bot callbacks and Mini App REST API.
    Features:
    - Verifies user balance against Admin-configured pricing.
    - Fetches top matching live candidates from TG Mandi.
    - Multi-candidate fallback: if candidate 1 fails/sold, tries candidate 2, 3.
    - Uses max_price=500.0 headroom so upstream never throws price_changed.
    - Deducts user balance atomically and persists order.
    """
    info = ACC_TYPE_INFO.get(acc_type)
    if not info:
        return {"ok": False, "error": "Invalid account type"}

    price = float(db.get_setting(info["setting_key"], 20.0))
    u_data = db.get_user(user_id) or {}
    bal = float(u_data.get("balance", 0.0))

    if bal < price:
        return {
            "ok": False,
            "error": f"Insufficient balance! Required: ₹{price:.2f}, Current Balance: ₹{bal:.2f}",
            "shortage": price - bal
        }

    # Fetch top candidates from supplier
    candidates = await tgmandi.get_candidates(acc_type, limit=5)
    if not candidates:
        return {
            "ok": False,
            "error": f"Currently out of stock from supplier for {info['name']}. Please try again shortly."
        }

    last_err = "Supplier purchase failed"
    for cand in candidates:
        cand_id = cand.get("id")
        buy_res = await tgmandi.buy_account(cand_id, max_price=500.0)
        if buy_res.get("ok"):
            # Deduct balance
            new_bal = db.deduct_balance(user_id, price, reason=f"Bought {info['name']}")
            if new_bal is None:
                return {"ok": False, "error": "Transaction balance deduction error."}

            order_no = buy_res.get("order_no")
            phone = buy_res.get("phone") or cand.get("phone") or "Protected"
            password = buy_res.get("password") or ""
            c_name = cand.get("country_name") or cand.get("country") or "International"

            order_doc = {
                "order_id": order_no,
                "user_id": user_id,
                "phone": phone,
                "password": password,
                "country": c_name,
                "item_id": cand_id,
                "type": acc_type,
                "type_label": info["name"],
                "price": price,
                "supplier_price": float(buy_res.get("price") or cand.get("price") or 0.0),
                "status": "active",
                "created_at": datetime.utcnow(),
            }
            db.create_order(order_doc)
            return {"ok": True, "order": order_doc, "new_balance": new_bal}
        else:
            last_err = buy_res.get("error") or last_err
            log.warning("Candidate %s failed (%s), attempting next candidate...", cand_id, last_err)

    return {"ok": False, "error": f"Purchase could not be completed: {last_err}"}

# ──────────────────────────────────────────────────────────────────────────────
#   MINI APP WEB SERVER (0.0.0.0:8080)
# ──────────────────────────────────────────────────────────────────────────────

web_runner: Optional[web.AppRunner] = None

def cors_headers() -> Dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }

async def handle_options(request: web.Request) -> web.Response:
    return web.Response(headers=cors_headers())

async def handle_index(request: web.Request) -> web.Response:
    html_path = "/home/user/webapp/index.html"
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        return web.Response(text=content, content_type="text/html", headers=cors_headers())
    return web.Response(text="<h1>Telegram Store Mini App</h1>", content_type="text/html", headers=cors_headers())

async def handle_api_me(request: web.Request) -> web.Response:
    uid_str = request.query.get("user_id")
    try:
        user_id = int(uid_str) if uid_str else PRIMARY_ADMIN_ID
    except ValueError:
        user_id = PRIMARY_ADMIN_ID

    u = db.get_user(user_id)
    if not u:
        u = db.get_or_create_user(user_id, f"User {user_id}", "")

    bonus = float(db.get_setting("referral_bonus", 5.0))
    user_payload = {
        "user_id": u["user_id"],
        "first_name": u.get("first_name", "User"),
        "username": u.get("username", ""),
        "balance": float(u.get("balance", 0.0)),
        "referral_count": int(u.get("referrals", 0)),
        "total_spent": float(u.get("total_spent", 0.0)),
        "total_orders": int(u.get("total_orders", 0)),
    }
    return web.json_response({
        "ok": True,
        "user": user_payload,
        "ref_bonus": bonus,
        "bot_username": "TGCardsStoreBot",
    }, headers=cors_headers())

async def handle_api_products(request: web.Request) -> web.Response:
    sp = float(db.get_setting("spam_price", 15.0))
    nsp = float(db.get_setting("nonspam_price", 25.0))
    psp = float(db.get_setting("prem_spam_price", 35.0))
    pnsp = float(db.get_setting("prem_nonspam_price", 50.0))

    products = [
        {"key": "spam", "name": "Spam Account", "price": sp, "description": "Instant SMS / OTP Account • Fresh Stock"},
        {"key": "nonspam", "name": "Non Spam Account", "price": nsp, "description": "Clean Spam-Free Account • High Quality"},
        {"key": "prem_spam", "name": "Premium Spam Account", "price": psp, "description": "Active Telegram Premium • Maximum Days"},
        {"key": "prem_nonspam", "name": "Premium Non-Spam Account", "price": pnsp, "description": "Clean Premium Account • Spam-Free"},
    ]
    return web.json_response({"ok": True, "products": products}, headers=cors_headers())

async def handle_api_buy(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON body"}, status=400, headers=cors_headers())

    user_id = data.get("user_id")
    acc_type = data.get("acc_type")
    if not user_id or not acc_type:
        return web.json_response({"ok": False, "error": "user_id and acc_type are required"}, status=400, headers=cors_headers())

    try:
        uid = int(user_id)
    except ValueError:
        return web.json_response({"ok": False, "error": "Invalid user_id"}, status=400, headers=cors_headers())

    res = await execute_store_purchase(uid, acc_type)
    return web.json_response(res, headers=cors_headers())

async def handle_api_orders(request: web.Request) -> web.Response:
    uid_str = request.query.get("user_id")
    if not uid_str:
        return web.json_response({"ok": False, "error": "user_id required"}, status=400, headers=cors_headers())
    try:
        user_id = int(uid_str)
    except ValueError:
        return web.json_response({"ok": False, "error": "Invalid user_id"}, status=400, headers=cors_headers())

    orders = db.get_user_orders(user_id, limit=25)
    formatted = []
    for o in orders:
        c_at = o.get("created_at")
        date_iso = c_at.isoformat() if isinstance(c_at, datetime) else str(c_at or "")
        formatted.append({
            "order_id": o.get("order_id"),
            "phone": o.get("phone", "Protected"),
            "password": o.get("password", ""),
            "type": o.get("type"),
            "type_label": o.get("type_label") or o.get("type"),
            "price": float(o.get("price", 0.0)),
            "status": o.get("status", "active"),
            "last_code": o.get("last_code"),
            "created_at": date_iso,
        })
    return web.json_response({"ok": True, "orders": formatted}, headers=cors_headers())

async def handle_api_get_otp(request: web.Request) -> web.Response:
    order_id = request.query.get("order_id")
    if not order_id:
        return web.json_response({"ok": False, "error": "order_id required"}, status=400, headers=cors_headers())

    order = db.get_order(order_id)
    otp_res = await tgmandi.get_otp_code(order_id, order=order)
    return web.json_response(otp_res, headers=cors_headers())

async def handle_api_leaderboard(request: web.Request) -> web.Response:
    leaders = db.get_top_referrers(limit=10)
    formatted = []
    for l in leaders:
        name = l.get("first_name") or f"User {l.get('user_id')}"
        formatted.append({
            "user_id": l.get("user_id"),
            "name": name,
            "referrals": l.get("referrals", 0),
        })
    return web.json_response({"ok": True, "leaders": formatted}, headers=cors_headers())

async def handle_api_health(request: web.Request) -> web.Response:
    return web.json_response({
        "ok": True,
        "status": "online",
        "service": "TG Mandi Store Mini App",
        "timestamp": datetime.utcnow().isoformat()
    }, headers=cors_headers())

def build_web_app() -> web.Application:
    app = web.Application()
    app.router.add_route("OPTIONS", "/{tail:.*}", handle_options)
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/me", handle_api_me)
    app.router.add_get("/api/products", handle_api_products)
    app.router.add_post("/api/buy", handle_api_buy)
    app.router.add_get("/api/orders", handle_api_orders)
    app.router.add_get("/api/get_otp", handle_api_get_otp)
    app.router.add_get("/api/leaderboard", handle_api_leaderboard)
    app.router.add_get("/api/health", handle_api_health)
    return app

async def start_web_server():
    global web_runner
    if web_runner is not None:
        return
    app = build_web_app()
    web_runner = web.AppRunner(app)
    await web_runner.setup()
    site = web.TCPSite(web_runner, "0.0.0.0", 8080)
    await site.start()
    log.info("Telegram Mini App Web Server running on http://0.0.0.0:8080")

async def stop_web_server():
    global web_runner
    if web_runner:
        await web_runner.cleanup()
        web_runner = None
        log.info("Telegram Mini App Web Server stopped.")

async def cb_buy_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "buy_type_premium":
        txt = card_box(
            "Pʀᴇᴍɪᴜᴍ Aᴄᴄᴏᴜɴᴛs",
            [
                ("Oᴘᴛɪᴏɴ 1", "Pʀᴇᴍɪᴜᴍ Sᴘᴀᴍ (Mᴀx Dᴀʏs, Lᴏᴡᴇsᴛ Pʀɪᴄᴇ)"),
                ("Oᴘᴛɪᴏɴ 2", "Pʀᴇᴍɪᴜᴍ Nᴏɴ-Sᴘᴀᴍ (Mᴀx Dᴀʏs, Sᴘᴀᴍ Fʀᴇᴇ)"),
                ("Dᴇʟɪᴠᴇʀʏ", "Iɴsᴛᴀɴᴛ (SMS / OTP)"),
            ],
            footer="Sᴇʟᴇᴄᴛ ᴀ ᴘʀᴇᴍɪᴜᴍ sᴜʙ-ᴄᴀᴛᴇɢᴏʀʏ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=get_premium_submenu_keyboard())
        return

    acc_type = data.replace("buy_type_", "")
    info = ACC_TYPE_INFO.get(acc_type)
    if not info:
        return

    price = float(db.get_setting(info["setting_key"], 20.0))
    u_data = db.get_user(q.from_user.id) or {}
    bal = float(u_data.get("balance", 0.0))

    # Pre-check live stock from TG Mandi API
    candidate = await tgmandi.search_account(acc_type)
    if not candidate:
        txt = card_box(
            "Oᴜᴛ Oғ Sᴛᴏᴄᴋ",
            [
                ("Tʏᴘᴇ", info["name"]),
                ("Sᴛᴀᴛᴜs", "Tᴇᴍᴘᴏʀᴀʀɪʟʏ Uɴᴀᴠᴀɪʟᴀʙʟᴇ"),
                ("Rᴇᴀsᴏɴ", "No accounts currently in stock from supplier"),
            ],
            footer="Pʟᴇᴀsᴇ ᴄʜᴏᴏsᴇ ᴀɴᴏᴛʜᴇʀ ᴄᴀᴛᴇɢᴏʀʏ ᴏʀ ᴄʜᴇᴄᴋ ʙᴀᴄᴋ sᴏᴏɴ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Bᴜʏ Oᴛʜᴇʀ Cᴀᴛᴇɢᴏʀʏ", callback_data="menu_buy")],
            [InlineKeyboardButton("« Mᴀɪɴ Mᴇɴᴜ", callback_data="main_menu")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    c_country = candidate.get("country_name") or candidate.get("country") or "International"
    txt = card_box(
        "Cᴏɴғɪʀᴍ Pᴜʀᴄʜᴀsᴇ",
        [
            ("Tʏᴘᴇ", info["name"]),
            ("Cᴏᴜɴᴛʀʏ", c_country),
            ("Pʀɪᴄᴇ", f"₹{price:.2f}"),
            ("Yᴏᴜʀ Bᴀʟᴀɴᴄᴇ", f"₹{bal:.2f}"),
            ("Dᴇsᴄʀɪᴘᴛɪᴏɴ", info["desc"]),
            ("Dᴇʟɪᴠᴇʀʏ", "Iɴsᴛᴀɴᴛ (SMS / OTP)"),
        ],
        footer="Aʀᴇ ʏᴏᴜ sᴜʀᴇ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴘᴜʀᴄʜᴀsᴇ ᴛʜɪs ᴀᴄᴄᴏᴜɴᴛ?"
    )
    await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=get_confirm_keyboard(acc_type))


async def cb_exec_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    acc_type = q.data.replace("exec_buy_", "")
    info = ACC_TYPE_INFO.get(acc_type)
    if not info:
        return

    try:
        await q.answer("⏳ Processing your purchase...")
        wait_txt = card_box(
            "Pʀᴏᴄᴇssɪɴɢ Oʀᴅᴇʀ",
            [
                ("Tʏᴘᴇ", info["name"]),
                ("Sᴛᴀᴛᴜs", "Fᴇᴛᴄʜɪɴɢ Aᴄᴄᴏᴜɴᴛ Fʀᴏᴍ Sᴜᴘᴘʟɪᴇʀ..."),
            ],
            footer="Pʟᴇᴀsᴇ ᴡᴀɪᴛ ᴀ ғᴇᴡ sᴇᴄᴏɴᴅs ᴡʜɪʟᴇ ʏᴏᴜʀ ᴏʀᴅᴇʀ ɪs ᴘʀᴏᴄᴇssᴇᴅ."
        )
        await q.edit_message_text(wait_txt, parse_mode=ParseMode.HTML)

        res = await execute_store_purchase(user.id, acc_type)
        if not res.get("ok"):
            err_msg = res.get("error", "Purchase failed")
            txt = card_box(
                "Pᴜʀᴄʜᴀsᴇ Fᴀɪʟᴇᴅ",
                [
                    ("Tʏᴘᴇ", info["name"]),
                    ("Eʀʀᴏʀ", str(err_msg)),
                ],
                footer="Nᴏ ғᴜɴᴅs ᴡᴇʀᴇ ᴅᴇᴅᴜᴄᴛᴇᴅ. Pʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ."
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("◈ Bᴜʏ Aᴄᴄᴏᴜɴᴛs", callback_data="menu_buy")],
                [InlineKeyboardButton("« Mᴀɪɴ Mᴇɴᴜ", callback_data="main_menu")],
            ])
            await send_or_edit(q, txt, kb)
            return

        order_doc = res["order"]
        new_bal = res["new_balance"]
        order_no = order_doc["order_id"]
        phone = order_doc["phone"]
        password = order_doc.get("password")
        price = order_doc["price"]

        # Send Payout Channel Notification in background
        asyncio.create_task(send_payout_channel_notification(ctx.bot, order_doc))

        # Success Card
        order_items = [
            ("Oʀᴅᴇʀ ID", f"<code>{order_no}</code>"),
            ("Tʏᴘᴇ", info["name"]),
            ("Pʜᴏɴᴇ Nᴜᴍʙᴇʀ", f"<code>{phone}</code>"),
        ]
        if password:
            order_items.append(("2FA Pᴀssᴡᴏʀᴅ", f"<code>{password}</code>"))
        order_items.extend([
            ("Pʀɪᴄᴇ", f"₹{price:.2f}"),
            ("Rᴇᴍᴀɪɴɪɴɢ Bᴀʟᴀɴᴄᴇ", f"₹{new_bal:.2f}"),
            ("Sᴛᴀᴛᴜs", "Aᴄᴛɪᴠᴇ"),
        ])

        txt = card_box(
            "Oʀᴅᴇʀ Cᴏᴍᴘʟᴇᴛᴇᴅ",
            order_items,
            footer="Tᴀᴘ 'Sᴇɴᴅ OTP' ᴛᴏ ғᴇᴛᴄʜ ʏᴏᴜʀ ʟᴏɢɪɴ ᴄᴏᴅᴇ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Sᴇɴᴅ OTP", callback_data=f"get_otp_{order_no}")],
            [InlineKeyboardButton("◈ Mʏ Aᴄᴄᴏᴜɴᴛs", callback_data="my_accounts")],
            [InlineKeyboardButton("« Mᴀɪɴ Mᴇɴᴜ", callback_data="main_menu")],
        ])
        await send_or_edit(q, txt, kb)

    except Exception as e:
        log.error("cb_exec_buy unhandled exception: %s", e, exc_info=True)
        txt = card_box(
            "Pᴜʀᴄʜᴀsᴇ Eʀʀᴏʀ",
            [
                ("Tʏᴘᴇ", info["name"]),
                ("Eʀʀᴏʀ", f"Unexpected error: {str(e)[:80]}"),
            ],
            footer="Nᴏ ғᴜɴᴅs ᴡᴇʀᴇ ᴅᴇᴅᴜᴄᴛᴇᴅ. Pʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Mᴇɴᴜ", callback_data="menu_buy")]])
        await send_or_edit(q, txt, kb)


async def cb_get_otp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    order_id = q.data.replace("get_otp_", "").replace("force_otp_", "")
    is_force = q.data.startswith("force_otp_")

    order = db.get_order(order_id)
    phone = order.get("phone") if order else "Unknown"
    password = order.get("password") if order else ""

    await q.answer("⏳ Checking for login OTP...")

    # If already cached and not force refresh, show code directly
    if not is_force and order and order.get("last_code"):
        code = str(order["last_code"])
        items = [
            ("Pʜᴏɴᴇ", f"<code>{phone}</code>"),
            ("Oᴛᴘ Cᴏᴅᴇ", f"<code>{code}</code>"),
        ]
        if password:
            items.append(("2FA Pᴀssᴡᴏʀᴅ", f"<code>{password}</code>"))
        items.extend([
            ("Oʀᴅᴇʀ ID", f"<code>{order_id}</code>"),
            ("Sᴛᴀᴛᴜs", "Sᴜᴄᴄᴇssғᴜʟʟʏ Rᴇᴄᴇɪᴠᴇᴅ"),
        ])
        txt = card_box(
            "Lᴏɢɪɴ Cᴏᴅᴇ Rᴇᴄᴇɪᴠᴇᴅ",
            items,
            footer="Tᴀᴘ ᴛʜᴇ ᴄᴏᴅᴇ ᴛᴏ ᴄᴏᴘʏ ɪᴛ ᴀɴᴅ ʟᴏɢ ɪɴ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Rᴇғʀᴇsʜ Nᴇᴡ Cᴏᴅᴇ", callback_data=f"force_otp_{order_id}")],
            [InlineKeyboardButton("◈ Mʏ Aᴄᴄᴏᴜɴᴛs", callback_data="my_accounts")],
            [InlineKeyboardButton("« Mᴀɪɴ Mᴇɴᴜ", callback_data="main_menu")],
        ])
        await send_or_edit(q, txt, kb)
        return

    # Call TG Mandi client
    code_res = await tgmandi.get_otp_code(order_id, order=order)
    if code_res.get("ok"):
        code = code_res.get("code")
        items = [
            ("Pʜᴏɴᴇ", f"<code>{phone}</code>"),
            ("Oᴛᴘ Cᴏᴅᴇ", f"<code>{code}</code>"),
        ]
        if password:
            items.append(("2FA Pᴀssᴡᴏʀᴅ", f"<code>{password}</code>"))
        items.extend([
            ("Oʀᴅᴇʀ ID", f"<code>{order_id}</code>"),
            ("Sᴛᴀᴛᴜs", "Sᴜᴄᴄᴇssғᴜʟʟʏ Rᴇᴄᴇɪᴠᴇᴅ"),
        ])
        txt = card_box(
            "Lᴏɢɪɴ Cᴏᴅᴇ Rᴇᴄᴇɪᴠᴇᴅ",
            items,
            footer="Tᴀᴘ ᴛʜᴇ ᴄᴏᴅᴇ ᴛᴏ ᴄᴏᴘʏ ɪᴛ ᴀɴᴅ ʟᴏɢ ɪɴ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Rᴇғʀᴇsʜ Nᴇᴡ Cᴏᴅᴇ", callback_data=f"force_otp_{order_id}")],
            [InlineKeyboardButton("◈ Mʏ Aᴄᴄᴏᴜɴᴛs", callback_data="my_accounts")],
            [InlineKeyboardButton("« Mᴀɪɴ Mᴇɴᴜ", callback_data="main_menu")],
        ])
        await send_or_edit(q, txt, kb)
    else:
        items = [
            ("Pʜᴏɴᴇ", f"<code>{phone}</code>"),
        ]
        if password:
            items.append(("2FA Pᴀssᴡᴏʀᴅ", f"<code>{password}</code>"))
        items.extend([
            ("Oʀᴅᴇʀ ID", f"<code>{order_id}</code>"),
            ("Sᴛᴀᴛᴜs", "Nᴏ Cᴏᴅᴇ Rᴇᴄᴇɪᴠᴇᴅ Yᴇᴛ"),
            ("Sᴛᴇᴘ 1", "Oᴘᴇɴ Telegram ᴀᴘᴘ"),
            ("Sᴛᴇᴘ 2", "Eɴᴛᴇʀ ᴛʜɪs ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ"),
            ("Sᴛᴇᴘ 3", "Rᴇǫᴜᴇsᴛ ᴄᴏᴅᴇ ᴠɪᴀ SMS"),
            ("Sᴛᴇᴘ 4", "Wᴀɪᴛ 5s ᴀɴᴅ ᴛᴀᴘ Rᴇғʀᴇsʜ OTP"),
        ])
        txt = card_box(
            "Wᴀɪᴛɪɴɢ Fᴏʀ Lᴏɢɪɴ Cᴏᴅᴇ",
            items,
            footer="Cᴏᴅᴇ ᴡɪʟʟ ᴀʀʀɪᴠᴇ ᴀs sᴏᴏɴ ᴀs ʏᴏᴜ ʀᴇǫᴜᴇsᴛ ɪᴛ ɪɴ Telegram."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Rᴇғʀᴇsʜ OTP", callback_data=f"force_otp_{order_id}")],
            [InlineKeyboardButton("◈ Mʏ Aᴄᴄᴏᴜɴᴛs", callback_data="my_accounts")],
            [InlineKeyboardButton("« Mᴀɪɴ Mᴇɴᴜ", callback_data="main_menu")],
        ])
        await send_or_edit(q, txt, kb)


# ──────────────────────────────────────────────────────────────────────────────
#   ADMIN PANEL (/admin) - STRICT PRIVACY FOR NON-ADMINS
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg:
        return

    # Strictly silent for regular users - no response at all
    if not is_admin(user.id):
        return

    stats = db.get_stats()
    maint = "Oɴ" if db.get_setting("maintenance", False) else "Oғғ"

    tgm_info = await tgmandi.get_account_details()
    tgm_user = tgm_info.get("user") or {}
    tgm_stats = tgm_info.get("stats") or {}
    tgm_bal = float(tgm_stats.get("balance") or tgm_user.get("balance") or 0.0)
    tgm_uname = tgm_user.get("username") or "kankan2010"
    tgm_role = str(tgm_user.get("role") or "reseller").capitalize()
    tgm_orders = int(tgm_stats.get("total_orders") or 0)
    tgm_spent = float(tgm_stats.get("total_spent") or 0.0)

    txt = card_box(
        "Aᴅᴍɪɴ Cᴏɴᴛʀᴏʟ Pᴀɴᴇʟ",
        [
            ("Bᴏᴛ Tᴏᴛᴀʟ Usᴇʀs", str(stats["total_users"])),
            ("Bᴏᴛ Tᴏᴛᴀʟ Oʀᴅᴇʀs", str(stats["total_orders"])),
            ("Bᴏᴛ Tᴏᴛᴀʟ Rᴇᴠᴇɴᴜᴇ", f"₹{stats['total_sales']:.2f}"),
            ("Bᴏᴛ Mᴀɪɴᴛᴇɴᴀɴᴄᴇ", maint),
            ("TG Mᴀɴᴅɪ Usᴇʀ", f"@{tgm_uname} ({tgm_role})"),
            ("TG Mᴀɴᴅɪ Bᴀʟᴀɴᴄᴇ", f"<b>₹{tgm_bal:.2f}</b>"),
            ("TG Mᴀɴᴅɪ Oʀᴅᴇʀs", str(tgm_orders)),
            ("TG Mᴀɴᴅɪ Sᴘᴇɴᴛ", f"₹{tgm_spent:.2f}"),
        ],
        footer="Sᴇʟᴇᴄᴛ ᴀɴ ᴀᴅᴍɪɴɪsᴛʀᴀᴛɪᴠᴇ ᴀᴄᴛɪᴏɴ ᴏʀ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟs ʙᴇʟᴏᴡ."
    )
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("◈ TG Mᴀɴᴅɪ Aᴄᴄᴏᴜɴᴛ", callback_data="adm_tgmandi"),
            InlineKeyboardButton("◈ Sᴛᴏʀᴇ Sᴛᴀᴛs", callback_data="adm_detailed_stats"),
        ],
        [
            InlineKeyboardButton("◈ Sᴇᴛ Pʀɪᴄᴇs", callback_data="adm_prices"),
            InlineKeyboardButton("◈ Rᴇғ Bᴏɴᴜs", callback_data="adm_ref_bonus"),
        ],
        [
            InlineKeyboardButton("◈ Usᴇʀ Mᴀɴᴀɢᴇʀ", callback_data="adm_users"),
            InlineKeyboardButton("◈ Cʜᴀɴɴᴇʟs", callback_data="adm_channels"),
        ],
        [
            InlineKeyboardButton("◈ Mᴀɴᴀɢᴇ Aᴅᴍɪɴs", callback_data="adm_manage_admins"),
            InlineKeyboardButton("◈ Pᴀʏᴏᴜᴛ Cʜᴀɴɴᴇʟ", callback_data="adm_payout_ch"),
        ],
        [
            InlineKeyboardButton("◈ Mɪɴɪ Aᴘᴘ URL", callback_data="adm_miniapp"),
            InlineKeyboardButton("◈ Bʀᴏᴀᴅᴄᴀsᴛ", callback_data="adm_broadcast"),
        ],
        [
            InlineKeyboardButton("◈ Mᴀɪɴᴛᴇɴᴀɴᴄᴇ", callback_data="adm_toggle_maint"),
            InlineKeyboardButton("« Cʟᴏsᴇ Pᴀɴᴇʟ", callback_data="adm_close"),
        ],
    ])
    await msg.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    if not is_admin(user.id):
        await q.answer()
        return

    await q.answer()
    data = q.data

    if data == "adm_home":
        stats = db.get_stats()
        maint = "Oɴ" if db.get_setting("maintenance", False) else "Oғғ"

        tgm_info = await tgmandi.get_account_details()
        tgm_user = tgm_info.get("user") or {}
        tgm_stats = tgm_info.get("stats") or {}
        tgm_bal = float(tgm_stats.get("balance") or tgm_user.get("balance") or 0.0)
        tgm_uname = tgm_user.get("username") or "kankan2010"
        tgm_role = str(tgm_user.get("role") or "reseller").capitalize()
        tgm_orders = int(tgm_stats.get("total_orders") or 0)
        tgm_spent = float(tgm_stats.get("total_spent") or 0.0)

        txt = card_box(
            "Aᴅᴍɪɴ Cᴏɴᴛʀᴏʟ Pᴀɴᴇʟ",
            [
                ("Bᴏᴛ Tᴏᴛᴀʟ Usᴇʀs", str(stats["total_users"])),
                ("Bᴏᴛ Tᴏᴛᴀʟ Oʀᴅᴇʀs", str(stats["total_orders"])),
                ("Bᴏᴛ Tᴏᴛᴀʟ Rᴇᴠᴇɴᴜᴇ", f"₹{stats['total_sales']:.2f}"),
                ("Bᴏᴛ Mᴀɪɴᴛᴇɴᴀɴᴄᴇ", maint),
                ("TG Mᴀɴᴅɪ Usᴇʀ", f"@{tgm_uname} ({tgm_role})"),
                ("TG Mᴀɴᴅɪ Bᴀʟᴀɴᴄᴇ", f"<b>₹{tgm_bal:.2f}</b>"),
                ("TG Mᴀɴᴅɪ Oʀᴅᴇʀs", str(tgm_orders)),
                ("TG Mᴀɴᴅɪ Sᴘᴇɴᴛ", f"₹{tgm_spent:.2f}"),
            ],
            footer="Sᴇʟᴇᴄᴛ ᴀɴ ᴀᴅᴍɪɴɪsᴛʀᴀᴛɪᴠᴇ ᴀᴄᴛɪᴏɴ ᴏʀ ᴠɪᴇᴡ ᴅᴇᴛᴀɪʟs ʙᴇʟᴏᴡ."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("◈ TG Mᴀɴᴅɪ Aᴄᴄᴏᴜɴᴛ", callback_data="adm_tgmandi"),
                InlineKeyboardButton("◈ Sᴛᴏʀᴇ Sᴛᴀᴛs", callback_data="adm_detailed_stats"),
            ],
            [
                InlineKeyboardButton("◈ Sᴇᴛ Pʀɪᴄᴇs", callback_data="adm_prices"),
                InlineKeyboardButton("◈ Rᴇғ Bᴏɴᴜs", callback_data="adm_ref_bonus"),
            ],
            [
                InlineKeyboardButton("◈ Usᴇʀ Mᴀɴᴀɢᴇʀ", callback_data="adm_users"),
                InlineKeyboardButton("◈ Cʜᴀɴɴᴇʟs", callback_data="adm_channels"),
            ],
            [
                InlineKeyboardButton("◈ Mᴀɴᴀɢᴇ Aᴅᴍɪɴs", callback_data="adm_manage_admins"),
                InlineKeyboardButton("◈ Pᴀʏᴏᴜᴛ Cʜᴀɴɴᴇʟ", callback_data="adm_payout_ch"),
            ],
            [
                InlineKeyboardButton("◈ Mɪɴɪ Aᴘᴘ URL", callback_data="adm_miniapp"),
                InlineKeyboardButton("◈ Bʀᴏᴀᴅᴄᴀsᴛ", callback_data="adm_broadcast"),
            ],
            [
                InlineKeyboardButton("◈ Mᴀɪɴᴛᴇɴᴀɴᴄᴇ", callback_data="adm_toggle_maint"),
                InlineKeyboardButton("« Cʟᴏsᴇ Pᴀɴᴇʟ", callback_data="adm_close"),
            ],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_tgmandi":
        tgm_info = await tgmandi.get_account_details()
        tgm_user = tgm_info.get("user") or {}
        tgm_stats = tgm_info.get("stats") or {}

        u_name = tgm_user.get("name") or "Kankan"
        u_uname = tgm_user.get("username") or "kankan2010"
        u_role = str(tgm_user.get("role") or "reseller").capitalize()
        u_tg = tgm_user.get("tg_username") or "Botastra"
        u_tg_id = tgm_user.get("telegram_id") or 8954471152

        bal = float(tgm_stats.get("balance") or tgm_user.get("balance") or 0.0)
        dep = float(tgm_stats.get("total_deposit") or 0.0)
        spent = float(tgm_stats.get("total_spent") or 0.0)
        orders_cnt = int(tgm_stats.get("total_orders") or 0)

        txt = card_box(
            "TG Mᴀɴᴅɪ Sᴜᴘᴘʟɪᴇʀ Aᴄᴄᴏᴜɴᴛ",
            [
                ("Usᴇʀɴᴀᴍᴇ", f"@{u_uname} ({u_name})"),
                ("Tᴇʟᴇɢʀᴀᴍ", f"@{u_tg} (<code>{u_tg_id}</code>)"),
                ("Rᴏʟᴇ", f"<b>{u_role}</b> (VIP API Access)"),
                ("API Bᴀʟᴀɴᴄᴇ", f"<b>₹{bal:.2f}</b>"),
                ("Tᴏᴛᴀʟ Dᴇᴘᴏsɪᴛ", f"₹{dep:.2f}"),
                ("Tᴏᴛᴀʟ Sᴘᴇɴᴛ", f"₹{spent:.2f}"),
                ("Tᴏᴛᴀʟ Oʀᴅᴇʀs", str(orders_cnt)),
                ("API Sᴛᴀᴛᴜs", "Online (v1.2.0)"),
                ("Eɴᴅᴘᴏɪɴᴛ", "<code>https://tgmandi.myvipsite.fun/api/v1</code>"),
            ],
            footer="Rᴇᴀʟ-ᴛɪᴍᴇ ᴅᴀᴛᴀ ғᴇᴛᴄʜᴇᴅ ᴅɪʀᴇᴄᴛʟʏ ғʀᴏᴍ TG Mandi API."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("◈ Vɪᴇᴡ API Oʀᴅᴇʀs", callback_data="adm_tgm_orders"),
                InlineKeyboardButton("◈ Vɪᴇᴡ Tʀᴀɴsᴀᴄᴛɪᴏɴs", callback_data="adm_tgm_txs"),
            ],
            [
                InlineKeyboardButton("◈ Lɪᴠᴇ Sᴛᴏᴄᴋ Cʜᴇᴄᴋ", callback_data="adm_tgm_stock"),
                InlineKeyboardButton("🔄 Rᴇғʀᴇsʜ Sᴛᴀᴛs", callback_data="adm_tgmandi"),
            ],
            [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Pᴀɴᴇʟ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_tgm_orders":
        api_orders = await tgmandi.get_api_orders(limit=8)
        items = []
        if not api_orders:
            items.append(("Sᴛᴀᴛᴜs", "Nᴏ Orders Found on Supplier Account"))
        else:
            for i, o in enumerate(api_orders, 1):
                ono = o.get("order_no") or f"ORD-{i}"
                phone = o.get("phone") or "N/A"
                c = o.get("country") or "INT"
                price = o.get("price") or 0.0
                st = str(o.get("status") or "completed").capitalize()
                items.append((f"#{i} {ono}", f"<code>{phone}</code> • {c} • ₹{price} ({st})"))

        txt = card_box(
            "TG Mᴀɴᴅɪ API Oʀᴅᴇʀs",
            items,
            footer="Rᴇᴄᴇɴᴛ ᴏʀᴅᴇʀs ᴘᴜʀᴄʜᴀsᴇᴅ ᴅɪʀᴇᴄᴛʟʏ ᴠɪᴀ TG Mandi API."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Rᴇғʀᴇsʜ Oʀᴅᴇʀs", callback_data="adm_tgm_orders")],
            [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ TG Mᴀɴᴅɪ", callback_data="adm_tgmandi"),
             InlineKeyboardButton("« Aᴅᴍɪɴ Pᴀɴᴇʟ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_tgm_txs":
        txs = await tgmandi.get_api_transactions(limit=8)
        items = []
        if not txs:
            items.append(("Sᴛᴀᴛᴜs", "Nᴏ Transactions Found"))
        else:
            for i, t in enumerate(txs, 1):
                ttype = str(t.get("type") or "tx").capitalize()
                amt = float(t.get("amount") or 0.0)
                bal_after = float(t.get("balance_after") or 0.0)
                ref = t.get("ref") or "N/A"
                sign = "+" if amt > 0 else ""
                items.append((f"#{i} {ttype}", f"{sign}₹{amt:.2f} (Bᴀʟ: ₹{bal_after:.2f}) • {ref}"))

        txt = card_box(
            "TG Mᴀɴᴅɪ Tʀᴀɴsᴀᴄᴛɪᴏɴs",
            items,
            footer="Rᴇᴄᴇɴᴛ ʙᴀʟᴀɴᴄᴇ ᴛʀᴀɴsᴀᴄᴛɪᴏɴs ᴏɴ ʏᴏᴜʀ TG Mandi API ᴀᴄᴄᴏᴜɴᴛ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Rᴇғʀᴇsʜ Tʀᴀɴsᴀᴄᴛɪᴏɴs", callback_data="adm_tgm_txs")],
            [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ TG Mᴀɴᴅɪ", callback_data="adm_tgmandi"),
             InlineKeyboardButton("« Aᴅᴍɪɴ Pᴀɴᴇʟ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_tgm_stock":
        await q.answer("⏳ Checking live supplier stock across countries...")
        stock_counts = await tgmandi.get_live_stock_counts()
        total_avail = sum(stock_counts.values())

        items = [
            ("Tᴏᴛᴀʟ Aᴄᴄᴏᴜɴᴛs", f"<b>{total_avail} Live Accounts</b>"),
        ]
        country_names = {
            "USA": "United States", "IND": "India", "BGD": "Bangladesh",
            "GBR": "United Kingdom", "PHL": "Philippines", "IDN": "Indonesia",
            "EGY": "Egypt", "BRA": "Brazil", "TUR": "Türkiye"
        }
        for code, count in stock_counts.items():
            cname = country_names.get(code, code)
            items.append((cname, f"{count} Aᴄᴄᴏᴜɴᴛs Aᴠᴀɪʟᴀʙʟᴇ"))

        txt = card_box(
            "TG Mᴀɴᴅɪ Lɪᴠᴇ Sᴛᴏᴄᴋ",
            items,
            footer="Lɪᴠᴇ ᴀᴠᴀɪʟᴀʙʟᴇ ɪɴᴠᴇɴᴛᴏʀʏ ғᴇᴛᴄʜᴇᴅ ғʀᴏᴍ TG Mandi API."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Rᴇғʀᴇsʜ Sᴛᴏᴄᴋ", callback_data="adm_tgm_stock")],
            [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ TG Mᴀɴᴅɪ", callback_data="adm_tgmandi"),
             InlineKeyboardButton("« Aᴅᴍɪɴ Pᴀɴᴇʟ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_detailed_stats":
        stats = db.get_stats()
        tot_users = stats["total_users"]
        tot_orders = stats["total_orders"]
        tot_sales = stats["total_sales"]
        tot_cost = stats.get("total_supplier_cost", 0.0)
        profit = stats.get("total_profit", tot_sales - tot_cost)
        tot_bal = stats.get("total_user_balance", 0.0)
        tot_refs = stats.get("total_referrals", 0)

        aov = (tot_sales / tot_orders) if tot_orders > 0 else 0.0

        txt = card_box(
            "Sᴛᴏʀᴇ Aɴᴀʟʏᴛɪᴄs & Sᴛᴀᴛs",
            [
                ("Tᴏᴛᴀʟ Rᴇɢɪsᴛᴇʀᴇᴅ Usᴇʀs", str(tot_users)),
                ("Tᴏᴛᴀʟ Aᴄᴄᴏᴜɴᴛs Sᴏʟᴅ", str(tot_orders)),
                ("Tᴏᴛᴀʟ Rᴇᴠᴇɴᴜᴇ", f"₹{tot_sales:.2f}"),
                ("Tᴏᴛᴀʟ Sᴜᴘᴘʟɪᴇʀ Cᴏsᴛ", f"₹{tot_cost:.2f}"),
                ("Nᴇᴛ Pʀᴏғɪᴛ", f"<b>₹{profit:.2f}</b>"),
                ("Avɢ Oʀᴅᴇʀ Vᴀʟᴜᴇ (AOV)", f"₹{aov:.2f}"),
                ("Tᴏᴛᴀʟ Usᴇʀ Bᴀʟᴀɴᴄᴇs", f"₹{tot_bal:.2f}"),
                ("Tᴏᴛᴀʟ Rᴇғᴇʀʀᴀʟs Mᴀᴅᴇ", str(tot_refs)),
            ],
            footer="Cᴏᴍᴘʟᴇᴛᴇ sᴛᴏʀᴇ ᴘᴇʀғᴏʀᴍᴀɴᴄᴇ ᴍᴇᴛʀɪᴄs ғʀᴏᴍ MongoDB."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Rᴇғʀᴇsʜ Sᴛᴀᴛs", callback_data="adm_detailed_stats")],
            [InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Pᴀɴᴇʟ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_close":
        await q.edit_message_text("<i>◈ Aᴅᴍɪɴ Pᴀɴᴇʟ Cʟᴏsᴇᴅ ◈</i>", parse_mode=ParseMode.HTML)

    elif data == "adm_manage_admins":
        admins = db.get_admins()
        items = [
            ("Pʀɪᴍᴀʀʏ Oᴡɴᴇʀ", f"<code>{PRIMARY_ADMIN_ID}</code>"),
            ("Tᴏᴛᴀʟ Aᴅᴍɪɴs", str(len(admins))),
        ]
        for idx, aid in enumerate(admins, 1):
            role = "Oᴡɴᴇʀ" if aid == PRIMARY_ADMIN_ID else "Aᴅᴍɪɴ"
            u_info = db.get_user(aid)
            name = f" ({u_info.get('first_name', '')})" if u_info and u_info.get("first_name") else ""
            items.append((f"Aᴅᴍɪɴ #{idx}", f"<code>{aid}</code>{name} • {role}"))

        txt = card_box(
            "Aᴅᴍɪɴ Mᴀɴᴀɢᴇʀ",
            items,
            footer="Aᴅᴅ ɴᴇᴡ ᴀᴅᴍɪɴs ᴏʀ ʀᴇᴍᴏᴠᴇ ᴇxɪsᴛɪɴɢ ᴏɴᴇs."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Aᴅᴅ Aᴅᴍɪɴ", callback_data="adm_add_admin"),
             InlineKeyboardButton("◈ Rᴇᴍᴏᴠᴇ Aᴅᴍɪɴ", callback_data="adm_remove_admin")],
            [InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_add_admin":
        ctx.user_data["adm_state"] = "await_add_admin"
        txt = card_box(
            "Aᴅᴅ Nᴇᴡ Aᴅᴍɪɴ",
            [
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Sᴇɴᴅ ᴛʜᴇ Tᴇʟᴇɢʀᴀᴍ Nᴜᴍᴇʀɪᴄ ID ᴏғ ᴛʜᴇ ɴᴇᴡ ᴀᴅᴍɪɴ:"),
                ("Exᴀᴍᴘʟᴇ", "<code>1234567890</code>"),
            ],
            footer="Sᴇɴᴅ /cancel ᴛᴏ ᴀʙᴏʀᴛ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_remove_admin":
        admins = db.get_admins()
        removable = [aid for aid in admins if aid != PRIMARY_ADMIN_ID]
        if not removable:
            await q.answer("No secondary admins to remove.", show_alert=True)
            return

        btn_rows = []
        for aid in removable:
            u_info = db.get_user(aid)
            label = f"❌ {aid}" + (f" ({u_info.get('first_name')})" if u_info and u_info.get("first_name") else "")
            btn_rows.append([InlineKeyboardButton(label, callback_data=f"adm_rmadmin_{aid}")])
        btn_rows.append([InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="adm_manage_admins")])

        txt = card_box(
            "Rᴇᴍᴏᴠᴇ Aᴅᴍɪɴ",
            [
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Tᴀᴘ ᴛʜᴇ ᴀᴅᴍɪɴ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ʀᴇᴍᴏᴠᴇ:"),
            ],
            footer="Pʀɪᴍᴀʀʏ Oᴡɴᴇʀ ᴄᴀɴɴᴏᴛ ʙᴇ ʀᴇᴍᴏᴠᴇᴅ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btn_rows))

    elif data.startswith("adm_rmadmin_"):
        target_aid = int(data.replace("adm_rmadmin_", ""))
        ok = db.remove_admin(target_aid)
        if ok:
            await q.answer(f"Admin {target_aid} removed successfully!", show_alert=True)
        else:
            await q.answer("Cannot remove this admin.", show_alert=True)
        q.data = "adm_manage_admins"
        await cb_admin_panel(update, ctx)

    elif data == "adm_prices":
        sp = db.get_setting("spam_price", 15.0)
        nsp = db.get_setting("nonspam_price", 25.0)
        psp = db.get_setting("prem_spam_price", 35.0)
        pnsp = db.get_setting("prem_nonspam_price", 50.0)

        txt = card_box(
            "Pʀɪᴄᴇ Cᴏɴᴛʀᴏʟs",
            [
                ("Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ", f"₹{sp:.2f}"),
                ("Nᴏɴ-Sᴘᴀᴍ Aᴄᴄᴏᴜɴᴛ", f"₹{nsp:.2f}"),
                ("Pʀᴇᴍɪᴜᴍ Sᴘᴀᴍ", f"₹{psp:.2f}"),
                ("Pʀᴇᴍɪᴜᴍ Nᴏɴ-Sᴘᴀᴍ", f"₹{pnsp:.2f}"),
            ],
            footer="Tᴀᴘ ᴀ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴏᴅɪғʏ ɪᴛs ᴘʀɪᴄᴇ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Eᴅɪᴛ Sᴘᴀᴍ", callback_data="setp_spam_price"),
             InlineKeyboardButton("◈ Eᴅɪᴛ Nᴏɴ-Sᴘᴀᴍ", callback_data="setp_nonspam_price")],
            [InlineKeyboardButton("◈ Eᴅɪᴛ Pʀᴇᴍ Sᴘᴀᴍ", callback_data="setp_prem_spam_price"),
             InlineKeyboardButton("◈ Eᴅɪᴛ Pʀᴇᴍ Nᴏɴ-Sᴘᴀᴍ", callback_data="setp_prem_nonspam_price")],
            [InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data.startswith("setp_"):
        key = data.replace("setp_", "")
        ctx.user_data["adm_state"] = f"await_price_{key}"
        txt = card_box(
            "Sᴇᴛ Nᴇᴡ Pʀɪᴄᴇ",
            [
                ("Sᴇᴛᴛɪɴɢ", to_small_caps(key.replace("_", " "))),
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Sᴇɴᴅ ᴛʜᴇ ɴᴇᴡ ᴘʀɪᴄᴇ ɪɴ INR (ᴇ.ɢ. 20.00)"),
            ],
            footer="Sᴇɴᴅ /cancel ᴛᴏ ᴀʙᴏʀᴛ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_ref_bonus":
        bonus = db.get_setting("referral_bonus", 5.0)
        ctx.user_data["adm_state"] = "await_ref_bonus"
        txt = card_box(
            "Rᴇғᴇʀʀᴀʟ Bᴏɴᴜs",
            [
                ("Cᴜʀʀᴇɴᴛ Bᴏɴᴜs", f"₹{bonus:.2f}"),
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Sᴇɴᴅ ᴛʜᴇ ɴᴇᴡ ʙᴏɴᴜs ᴀᴍᴏᴜɴᴛ ɪɴ INR (ᴇ.ɢ. 5.00)"),
            ],
            footer="Sᴇɴᴅ /cancel ᴛᴏ ᴀʙᴏʀᴛ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_toggle_maint":
        cur = db.get_setting("maintenance", False)
        new_val = not cur
        db.set_setting("maintenance", new_val)
        await q.answer(f"Maintenance mode set to {'ON' if new_val else 'OFF'}", show_alert=True)
        # Refresh home
        q.data = "adm_home"
        await cb_admin_panel(update, ctx)

    elif data == "adm_channels":
        channels = db.get_setting("force_channels", [])
        items = []
        if not channels:
            items.append(("Cʜᴀɴɴᴇʟs", "Nᴏ Cʜᴀɴɴᴇʟs Cᴏɴғɪɢᴜʀᴇᴅ"))
        else:
            for i, ch in enumerate(channels, 1):
                name = ch.get("username") or ch.get("chat_id") or "Channel"
                items.append((f"Cʜᴀɴɴᴇʟ #{i}", f"{name}"))

        txt = card_box(
            "Fᴏʀᴄᴇ Jᴏɪɴ Cʜᴀɴɴᴇʟs",
            items,
            footer="Usᴇʀs ᴍᴜsᴛ ᴊᴏɪɴ ᴛʜᴇsᴇ ᴄʜᴀɴɴᴇʟs ʙᴇғᴏʀᴇ ᴜsɪɴɢ ᴛʜᴇ ʙᴏᴛ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Aᴅᴅ Cʜᴀɴɴᴇʟ", callback_data="adm_add_channel")],
            [InlineKeyboardButton("◈ Cʟᴇᴀʀ Aʟʟ Cʜᴀɴɴᴇʟs", callback_data="adm_clear_channels")],
            [InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_add_channel":
        ctx.user_data["adm_state"] = "await_channel"
        txt = card_box(
            "Aᴅᴅ Fᴏʀᴄᴇ Cʜᴀɴɴᴇʟ",
            [
                ("Fᴏʀᴍᴀᴛ 1", "@ChannelUsername"),
                ("Fᴏʀᴍᴀᴛ 2", "-1001234567890 | https://t.me/invite"),
            ],
            footer="Mᴀᴋᴇ sᴜʀᴇ ᴛʜɪs ʙᴏᴛ ɪs ᴀɴ Aᴅᴍɪɴ ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ!"
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_clear_channels":
        db.set_setting("force_channels", [])
        await q.answer("All force-join channels cleared!", show_alert=True)
        q.data = "adm_channels"
        await cb_admin_panel(update, ctx)

    elif data == "adm_users":
        ctx.user_data["adm_state"] = "await_user_id"
        txt = card_box(
            "Usᴇʀ Mᴀɴᴀɢᴇʀ",
            [
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Sᴇɴᴅ ᴛʜᴇ Tᴇʟᴇɢʀᴀᴍ ID ᴏғ ᴛʜᴇ ᴜsᴇʀ:"),
            ],
            footer="Sᴇɴᴅ /cancel ᴛᴏ ᴀʙᴏʀᴛ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_broadcast":
        ctx.user_data["adm_state"] = "await_broadcast"
        txt = card_box(
            "Bʀᴏᴀᴅᴄᴀsᴛ Mᴇssᴀɢᴇ",
            [
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Sᴇɴᴅ ᴛʜᴇ ᴍᴇssᴀɢᴇ ᴛᴏ ʙʀᴏᴀᴅᴄᴀsᴛ ᴛᴏ ᴀʟʟ ᴜsᴇʀs:"),
                ("Fᴏʀᴍᴀᴛ", "HTML sᴜᴘᴘᴏʀᴛᴇᴅ"),
            ],
            footer="Sᴇɴᴅ /cancel ᴛᴏ ᴀʙᴏʀᴛ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_payout_ch":
        cur = db.get_setting("payout_channel") or "Not Configured"
        txt = card_box(
            "Pᴀʏᴏᴜᴛ Cʜᴀɴɴᴇʟ",
            [
                ("Cᴜʀʀᴇɴᴛ Cʜᴀɴɴᴇʟ", f"<code>{cur}</code>"),
                ("Fᴜɴᴄᴛɪᴏɴ", "Aᴜᴛᴏ-ᴘᴏsᴛs ᴍᴀsᴋᴇᴅ ᴘᴜʀᴄʜᴀsᴇ ʀᴇᴄᴇɪᴘᴛs"),
                ("Fᴏʀᴍᴀᴛ", "@ChannelUsername ᴏʀ -1001234567890"),
            ],
            footer="Tᴀᴘ ᴀ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ᴍᴏᴅɪғʏ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Sᴇᴛ Cʜᴀɴɴᴇʟ", callback_data="adm_set_payout_ch"),
             InlineKeyboardButton("◈ Cʟᴇᴀʀ Cʜᴀɴɴᴇʟ", callback_data="adm_clear_payout_ch")],
            [InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_set_payout_ch":
        ctx.user_data["adm_state"] = "await_payout_ch"
        txt = card_box(
            "Sᴇᴛ Pᴀʏᴏᴜᴛ Cʜᴀɴɴᴇʟ",
            [
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Sᴇɴᴅ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ᴜsᴇʀɴᴀᴍᴇ ᴏʀ ɴᴜᴍᴇʀɪᴄ ID:"),
                ("Exᴀᴍᴘʟᴇ", "@MyStorePayouts ᴏʀ -1001234567890"),
            ],
            footer="Mᴀᴋᴇ sᴜʀᴇ ᴛʜɪs ʙᴏᴛ ɪs ᴀɴ Aᴅᴍɪɴ ɪɴ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ!\nSᴇɴᴅ /cancel ᴛᴏ ᴀʙᴏʀᴛ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_clear_payout_ch":
        db.set_setting("payout_channel", None)
        await q.answer("Payout notification channel cleared!", show_alert=True)
        q.data = "adm_payout_ch"
        await cb_admin_panel(update, ctx)

    elif data == "adm_miniapp":
        cur_url = db.get_setting("mini_app_url") or "Not Configured"
        txt = card_box(
            "Mɪɴɪ Aᴘᴘ URL",
            [
                ("Cᴜʀʀᴇɴᴛ URL", f"<code>{cur_url}</code>"),
                ("Lᴏᴄᴀʟ Sᴇʀᴠᴇʀ", "<code>http://0.0.0.0:8080</code>"),
                ("Fᴜɴᴄᴛɪᴏɴ", "Iɴ-Aᴘᴘ WebApp sᴛᴏʀᴇ ᴄᴀᴛᴀʟᴏɢ, ᴏʀᴅᴇʀs & OTP"),
            ],
            footer="Sᴇᴛ ᴀɴ HTTPS URL ᴛᴏ ᴇɴᴀʙʟᴇ ᴛʜᴇ Tᴇʟᴇɢʀᴀᴍ Mɪɴɪ Aᴘᴘ ʙᴜᴛᴛᴏɴ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Sᴇᴛ Mɪɴɪ Aᴘᴘ URL", callback_data="adm_set_miniapp"),
             InlineKeyboardButton("◈ Cʟᴇᴀʀ URL", callback_data="adm_clear_miniapp")],
            [InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data == "adm_set_miniapp":
        ctx.user_data["adm_state"] = "await_miniapp_url"
        txt = card_box(
            "Sᴇᴛ Mɪɴɪ Aᴘᴘ URL",
            [
                ("Iɴsᴛʀᴜᴄᴛɪᴏɴ", "Sᴇɴᴅ ʏᴏᴜʀ HTTPS WebApp URL:"),
                ("Exᴀᴍᴘʟᴇ", "<code>https://store.yourdomain.com</code>"),
            ],
            footer="Mᴜsᴛ sᴛᴀʀᴛ ᴡɪᴛʜ https:// ᴛᴏ ᴡᴏʀᴋ ɪɴ Telegram. Sᴇɴᴅ /cancel ᴛᴏ ᴀʙᴏʀᴛ."
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif data == "adm_clear_miniapp":
        db.set_setting("mini_app_url", "")
        try:
            await ctx.bot.set_chat_menu_button(menu_button=MenuButtonDefault())
        except Exception:
            pass
        await q.answer("Mini App URL cleared!", show_alert=True)
        q.data = "adm_miniapp"
        await cb_admin_panel(update, ctx)


# ──────────────────────────────────────────────────────────────────────────────
#   TEXT MESSAGE HANDLER (FOR ADMIN STATE INPUTS)
# ──────────────────────────────────────────────────────────────────────────────

async def on_text_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = update.effective_message
    if not user or not msg or not msg.text:
        return

    text = msg.text.strip()
    if text == "/cancel":
        ctx.user_data.pop("adm_state", None)
        await msg.reply_text("<i>◈ Aᴄᴛɪᴏɴ Cᴀɴᴄᴇʟʟᴇᴅ ◈</i>", parse_mode=ParseMode.HTML)
        return

    adm_state = ctx.user_data.get("adm_state")
    if not adm_state or not is_admin(user.id):
        return

    # 1. Price Edit
    if adm_state.startswith("await_price_"):
        key = adm_state.replace("await_price_", "")
        try:
            val = float(re.sub(r"[^\d.]", "", text))
            db.set_setting(key, val)
            ctx.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ <b>{to_small_caps(key.replace('_', ' '))}</b> updated to <b>₹{val:.2f}</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await msg.reply_text("❌ Invalid price. Send a valid numeric value.")
        return

    # Admin Add
    if adm_state == "await_add_admin":
        ctx.user_data.pop("adm_state", None)
        digits = re.sub(r"\D", "", text)
        if not digits:
            await msg.reply_text("❌ Please send a valid numeric Telegram ID.")
            return
        new_aid = int(digits)
        if new_aid == PRIMARY_ADMIN_ID or new_aid in db.get_admins():
            await msg.reply_text(f"ℹ️ User <code>{new_aid}</code> is already an Admin.", parse_mode=ParseMode.HTML)
            return
        db.add_admin(new_aid)
        txt = card_box(
            "Aᴅᴍɪɴ Aᴅᴅᴇᴅ",
            [
                ("Usᴇʀ ID", f"<code>{new_aid}</code>"),
                ("Sᴛᴀᴛᴜs", "Gʀᴀɴᴛᴇᴅ Aᴅᴍɪɴ Pʀɪᴠɪʟᴇɢᴇs"),
            ],
            footer="Tʜɪs ᴜsᴇʀ ᴄᴀɴ ɴᴏᴡ ᴀᴄᴄᴇss /admin."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("◈ Mᴀɴᴀɢᴇ Aᴅᴍɪɴs", callback_data="adm_manage_admins")]])
        await msg.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        try:
            await ctx.bot.send_message(
                new_aid,
                "<b>◈ Aᴅᴍɪɴ Pʀᴏᴍᴏᴛɪᴏɴ ◈</b>\n──────────────────────────\n"
                "<blockquote>▸ Yᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ɢʀᴀɴᴛᴇᴅ <b>Aᴅᴍɪɴ Pʀɪᴠɪʟᴇɢᴇs</b> ɪɴ ᴛʜɪs ʙᴏᴛ.\n"
                "▸ Usᴇ /admin ᴛᴏ ᴏᴘᴇɴ ᴛʜᴇ ᴄᴏɴᴛʀᴏʟ ᴘᴀɴᴇʟ.</blockquote>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    # 2. Ref Bonus Edit
    if adm_state == "await_ref_bonus":
        try:
            val = float(re.sub(r"[^\d.]", "", text))
            db.set_setting("referral_bonus", val)
            ctx.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ <b>Referral Bonus</b> set to <b>₹{val:.2f}</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await msg.reply_text("❌ Send a valid numeric amount.")
        return

    # 3. Add Channel
    if adm_state == "await_channel":
        channels = db.get_setting("force_channels", [])
        if text.startswith("@"):
            ch_doc = {"chat_id": text, "username": text, "link": f"https://t.me/{text.lstrip('@')}"}
        elif "|" in text:
            parts = [p.strip() for p in text.split("|")]
            ch_doc = {"chat_id": parts[0], "username": parts[0], "link": parts[1]}
        else:
            ch_doc = {"chat_id": text, "username": text, "link": f"https://t.me/{text.lstrip('@')}"}
        channels.append(ch_doc)
        db.set_setting("force_channels", channels)
        ctx.user_data.pop("adm_state", None)
        await msg.reply_text(f"✅ Channel <code>{text}</code> added to force-join list.", parse_mode=ParseMode.HTML)
        return

    # Set Payout Channel
    if adm_state == "await_payout_ch":
        ctx.user_data.pop("adm_state", None)
        db.set_setting("payout_channel", text)
        txt = card_box(
            "Pᴀʏᴏᴜᴛ Cʜᴀɴɴᴇʟ Cᴏɴғɪɢᴜʀᴇᴅ",
            [
                ("Cʜᴀɴɴᴇʟ", f"<code>{text}</code>"),
                ("Sᴛᴀᴛᴜs", "Aᴄᴛɪᴠᴇ"),
            ],
            footer="Nᴇᴡ ᴘᴜʀᴄʜᴀsᴇs ᴡɪʟʟ ɴᴏᴡ ʙᴇ ᴘᴏsᴛᴇᴅ ʜᴇʀᴇ ᴡɪᴛʜ ᴍᴀsᴋᴇᴅ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀs."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Pᴀɴᴇʟ", callback_data="adm_payout_ch")]])
        await msg.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # Set Mini App URL
    if adm_state == "await_miniapp_url":
        ctx.user_data.pop("adm_state", None)
        new_url = text.strip()
        db.set_setting("mini_app_url", new_url)
        if new_url.startswith("https://"):
            try:
                await ctx.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(text="⚡ Store", web_app=WebAppInfo(url=new_url))
                )
            except Exception as e:
                log.debug("Set chat menu button note: %s", e)
        txt = card_box(
            "Mɪɴɪ Aᴘᴘ URL Cᴏɴғɪɢᴜʀᴇᴅ",
            [
                ("Nᴇᴡ URL", f"<code>{new_url}</code>"),
                ("Sᴛᴀᴛᴜs", "Aᴄᴛɪᴠᴇ"),
            ],
            footer="Usᴇʀs ᴄᴀɴ ɴᴏᴡ ʟᴀᴜɴᴄʜ ᴛʜᴇ Mɪɴɪ Aᴘᴘ ᴅɪʀᴇᴄᴛʟʏ ғʀᴏᴍ ᴛʜᴇ Mᴀɪɴ Mᴇɴᴜ."
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Bᴀᴄᴋ Tᴏ Pᴀɴᴇʟ", callback_data="adm_miniapp")]])
        await msg.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # 4. User Lookup / Edit
    if adm_state == "await_user_id":
        digits = re.sub(r"\D", "", text)
        if not digits:
            await msg.reply_text("❌ Please send a valid numeric Telegram ID.")
            return
        target_uid = int(digits)
        t_user = db.get_user(target_uid)
        if not t_user:
            await msg.reply_text(f"❌ User <code>{target_uid}</code> not found in database.", parse_mode=ParseMode.HTML)
            return
        ctx.user_data["managed_uid"] = target_uid
        ctx.user_data.pop("adm_state", None)

        txt = card_box(
            "Usᴇʀ Dᴇᴛᴀɪʟs",
            [
                ("Usᴇʀ ID", f"<code>{t_user['user_id']}</code>"),
                ("Nᴀᴍᴇ", t_user.get("first_name", "N/A")),
                ("Usᴇʀɴᴀᴍᴇ", f"@{t_user.get('username')}" if t_user.get("username") else "N/A"),
                ("Bᴀʟᴀɴᴄᴇ", f"₹{t_user.get('balance', 0.0):.2f}"),
                ("Rᴇғᴇʀʀᴀʟs", str(t_user.get("referrals", 0))),
                ("Tᴏᴛᴀʟ Sᴘᴇɴᴛ", f"₹{t_user.get('total_spent', 0.0):.2f}"),
                ("Sᴛᴀᴛᴜs", "Bᴀɴɴᴇᴅ" if t_user.get("is_banned") else "Aᴄᴛɪᴠᴇ"),
            ],
            footer="Cʜᴏᴏsᴇ ᴀɴ ᴀᴄᴛɪᴏɴ ᴛᴏ ᴍᴏᴅɪғʏ ᴛʜɪs ᴜsᴇʀ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Aᴅᴅ Bᴀʟᴀɴᴄᴇ", callback_data=f"adm_addbal_{target_uid}"),
             InlineKeyboardButton("◈ Dᴇᴅᴜᴄᴛ Bᴀʟᴀɴᴄᴇ", callback_data=f"adm_dedbal_{target_uid}")],
            [InlineKeyboardButton("◈ Tᴏɢɢʟᴇ Bᴀɴ", callback_data=f"adm_ban_{target_uid}")],
            [InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="adm_home")],
        ])
        await msg.reply_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # 5. Add / Deduct Balance Execution
    if adm_state.startswith("await_addbal_"):
        target_uid = int(adm_state.replace("await_addbal_", ""))
        try:
            amt = float(re.sub(r"[^\d.]", "", text))
            new_b = db.add_balance(target_uid, amt, reason="Admin Manual Credit")
            ctx.user_data.pop("adm_state", None)
            await msg.reply_text(f"✅ Added <b>₹{amt:.2f}</b> to User <code>{target_uid}</code>. New balance: <b>₹{new_b:.2f}</b>", parse_mode=ParseMode.HTML)
        except ValueError:
            await msg.reply_text("❌ Send a valid numeric amount.")
        return

    if adm_state.startswith("await_dedbal_"):
        target_uid = int(adm_state.replace("await_dedbal_", ""))
        try:
            amt = float(re.sub(r"[^\d.]", "", text))
            new_b = db.deduct_balance(target_uid, amt, reason="Admin Manual Debit")
            ctx.user_data.pop("adm_state", None)
            if new_b is not None:
                await msg.reply_text(f"✅ Deducted <b>₹{amt:.2f}</b> from User <code>{target_uid}</code>. New balance: <b>₹{new_b:.2f}</b>", parse_mode=ParseMode.HTML)
            else:
                await msg.reply_text("❌ User balance is less than deduction amount.")
        except ValueError:
            await msg.reply_text("❌ Send a valid numeric amount.")
        return

    # 6. Broadcast Message Execution
    if adm_state == "await_broadcast":
        ctx.user_data.pop("adm_state", None)
        all_users = list(db.db.users.find({}, {"user_id": 1}))
        total = len(all_users)
        status_msg = await msg.reply_text(f"⏳ Broadcasting message to {total} users...")

        sent = 0
        failed = 0
        for doc in all_users:
            uid = doc.get("user_id")
            try:
                await ctx.bot.send_message(uid, text, parse_mode=ParseMode.HTML)
                sent += 1
                await asyncio.sleep(0.04)
            except Exception:
                failed += 1

        await status_msg.edit_text(
            f"✅ <b>Broadcast Completed!</b>\n"
            f"{DIV}\n"
            f"▸ <b>Sent:</b> {sent}\n"
            f"▸ <b>Failed:</b> {failed}\n"
            f"▸ <b>Total:</b> {total}\n",
            parse_mode=ParseMode.HTML
        )
        return


async def cb_admin_user_actions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    if not is_admin(user.id):
        await q.answer()
        return

    await q.answer()
    data = q.data

    if data.startswith("adm_addbal_"):
        uid = int(data.replace("adm_addbal_", ""))
        ctx.user_data["adm_state"] = f"await_addbal_{uid}"
        await q.edit_message_text(f"Send the amount to <b>ADD</b> to User <code>{uid}</code> (e.g. 50.00):", parse_mode=ParseMode.HTML)

    elif data.startswith("adm_dedbal_"):
        uid = int(data.replace("adm_dedbal_", ""))
        ctx.user_data["adm_state"] = f"await_dedbal_{uid}"
        await q.edit_message_text(f"Send the amount to <b>DEDUCT</b> from User <code>{uid}</code> (e.g. 20.00):", parse_mode=ParseMode.HTML)

    elif data.startswith("adm_ban_"):
        uid = int(data.replace("adm_ban_", ""))
        t_user = db.get_user(uid) or {}
        new_ban = not t_user.get("is_banned", False)
        db.update_user(uid, is_banned=new_ban)
        status_txt = "Banned" if new_ban else "Unbanned"
        await q.answer(f"User {uid} has been {status_txt}!", show_alert=True)
        # Re-display user card
        txt = card_box(
            "Usᴇʀ Dᴇᴛᴀɪʟs",
            [
                ("Usᴇʀ ID", f"<code>{uid}</code>"),
                ("Nᴀᴍᴇ", t_user.get("first_name", "N/A")),
                ("Bᴀʟᴀɴᴄᴇ", f"₹{t_user.get('balance', 0.0):.2f}"),
                ("Sᴛᴀᴛᴜs", "Bᴀɴɴᴇᴅ" if new_ban else "Aᴄᴛɪᴠᴇ"),
            ],
            footer="Sᴛᴀᴛᴜs ᴜᴘᴅᴀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("◈ Aᴅᴅ Bᴀʟᴀɴᴄᴇ", callback_data=f"adm_addbal_{uid}"),
             InlineKeyboardButton("◈ Dᴇᴅᴜᴄᴛ Bᴀʟᴀɴᴄᴇ", callback_data=f"adm_dedbal_{uid}")],
            [InlineKeyboardButton("◈ Tᴏɢɢʟᴇ Bᴀɴ", callback_data=f"adm_ban_{uid}")],
            [InlineKeyboardButton("« Bᴀᴄᴋ", callback_data="adm_home")],
        ])
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML, reply_markup=kb)


# ──────────────────────────────────────────────────────────────────────────────
#   GLOBAL DISPATCHER
# ──────────────────────────────────────────────────────────────────────────────

async def on_callback_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = str(q.data or "")
    if not data:
        return await q.answer()

    # Gating & System
    if data == "verify_join": return await cb_verify_join(update, ctx)
    if data == "main_menu": return await cb_main_menu(update, ctx)

    # Menus
    if data == "menu_buy": return await cb_menu_buy(update, ctx)
    if data == "menu_account": return await cb_menu_account(update, ctx)
    if data == "menu_referrals": return await cb_menu_referrals(update, ctx)
    if data == "menu_leaderboard": return await cb_menu_leaderboard(update, ctx)
    if data == "my_accounts": return await cb_my_accounts(update, ctx)

    # Buy flows
    if data.startswith("buy_type_"): return await cb_buy_type(update, ctx)
    if data.startswith("exec_buy_"): return await cb_exec_buy(update, ctx)
    if data.startswith("get_otp_") or data.startswith("force_otp_"): return await cb_get_otp(update, ctx)

    # Admin Panel
    if data.startswith("adm_addbal_") or data.startswith("adm_dedbal_") or data.startswith("adm_ban_"):
        return await cb_admin_user_actions(update, ctx)
    if data.startswith("adm_") or data.startswith("setp_"):
        return await cb_admin_panel(update, ctx)

    await q.answer()


# ──────────────────────────────────────────────────────────────────────────────
#   APPLICATION BUILDER & ENTRYPOINT
# ──────────────────────────────────────────────────────────────────────────────

async def on_startup(app: Application):
    # Start web server on 0.0.0.0:8080
    await start_web_server()
    mini_url = (db.get_setting("mini_app_url") or "").strip()
    if mini_url.startswith("https://"):
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(text="⚡ Store", web_app=WebAppInfo(url=mini_url))
            )
            log.info("Chat menu button set to Mini App URL: %s", mini_url)
        except Exception as e:
            log.warning("Could not set chat menu button: %s", e)

async def on_shutdown(app: Application):
    await stop_web_server()
    await tgmandi.close()

def build_app(token: str) -> Application:
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))

    # Callback Queries
    app.add_handler(CallbackQueryHandler(on_callback_query))

    # Text Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))

    return app

def main():
    parser = argparse.ArgumentParser(description="TG Mandi Telegram Store Bot & Mini App Server")
    parser.add_argument("--server-only", action="store_true", help="Run only the Mini App Web Server on port 8080")
    args, _ = parser.parse_known_args()

    print("====================================================")
    print("⚡ TG MANDI VIP STORE BOT & TELEGRAM MINI APP ⚡")
    print("====================================================")
    print(f"MongoDB: {MONGO_URL_DEFAULT[:30]}...")
    print(f"TG Mandi API: {TGMANDI_API_URL}")
    print(f"Primary Admin: {PRIMARY_ADMIN_ID}, Registered Admins: {db.get_admins()}")

    if args.server_only:
        print("Starting Mini App Web Server on http://0.0.0.0:8080...")
        web_app = build_web_app()
        web.run_app(web_app, host="0.0.0.0", port=8080)
        return

    try:
        print("Initializing Telegram Bot polling and embedded Mini App web server...")
        app = build_app(BOT_TOKEN)
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        log.warning("Bot polling note: %s. Starting Mini App server on http://0.0.0.0:8080...", e)
        web_app = build_web_app()
        web.run_app(web_app, host="0.0.0.0", port=8080)

if __name__ == "__main__":
    main()
