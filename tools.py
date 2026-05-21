import logging
import html
import random
from datetime import date, datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler,
    MessageHandler, filters, PreCheckoutQueryHandler, CallbackContext, InlineQueryHandler
)
from telegram.constants import ParseMode
from config import BOT_TOKEN, ADMIN_ID, DB_PATH, INVITE_POINTS, REQUIRED_CHANNELS
from database import Database

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.ERROR,
)
logger = logging.getLogger(__name__)

db = Database(DB_PATH)

# ── Premium Emoji Config ──────────────────────────────────────────────────────
PREMIUM_EMOJIS = {
    "STAR":     ("5994495149336434048", "⭐"),
    "POINT":    ("5345843457145453967", "🏅"),
    "IMAGE": ("5931629923478278721", "🖼️"),
    "LOCK":     ("6037249452824072506", "🔒"),
    "UNLOCK":   ("6034962180875490251", "🔓"),
    "CHECK":    ("5260416304224936047", "✅"),
    "CANCEL":   ("5192829775437117939", "❌"),
    "INFO":     ("5258503720928288433", "ℹ️"),
    "WARNING":  ("4915853119839011973", "⚠️"),
    "GIFT":     ("5963213811597970978", "🎁"),
    "TREASURE": ("5807465992363710697", "💎"),
    "CROWN":    ("5807868868886009920", "👑"),
    "ROCKET":   ("5316571734604790521", "🚀"),
    "HEART":    ("5258179403652801593", "❤️"),
    "COIN":     ("5318972874726339331", "🪙"),
    "down":     ("6037157012242960559", "👇"),
    "paper":    ("5289888859436366020", "📄"),
    "party":    ("5989848973974704652", "🎉"),
    "LINK":     ("5260730055880876557", "🔗"),
    "name":     ("6068610874522735901", "📛"),
    "DELETE":   ("5258130763148172425", "🗑️"),
    "pack":     ("5884479287171485878", "📦"),
    "bulb":     ("5258216851472654189", "💡"),
    "LIST":     ("5330363643391393348", "📋"),
    "BACK":     ("5877629862306385808", "◀️"),
    "EDIT":     ("5879841310902324730", "✏️"),
    "WAVE":     ("5994750571041525522", "👋"),
    "PEOPLE":   ("5942877472163892475", "👥"),
    "SEARCH":   ("5361712364871763071", "🔍"),
    "TAG":      ("5456136765607783041", "🏷️"),
    "FIRE":     ("5116414868357907335", "🔥"),
    "MEDAL1":   ("6206370726476256501", "🥇"),
    "MEDAL2":   ("6206222099132978580", "🥈"),
    "MEDAL3":   ("5453902265922376865", "🥉"),
    "TROPHY":   ("5870684638195748414", "🏆"),
    "STREAK":   ("5215512756152704759", "🔥"),
    "SHIELD":   ("5931409969613116639", "🛡️"),
    "BELL":     ("5909201569898827582", "🔔"),
    "CHART":    ("5931472654660800739", "📊"),
    "BAN":      ("5872829476143894491", "🚫"),
    "USER":     ("5258011929993026890", "👤"),
    "FAV":      ("5994453058656931434", "❤️"),
    "STAR5":    ("5976731220434753490", "⭐⭐⭐⭐⭐"),
    "REVIEW":   ("5884510167986343350", "💬"),
    "Star5": ("5976731220434753490", "lol"),
    "NEXT": ("5260450573768990626", "nextsha"),
    "TEETH": ("5354889508674360491", "LOL")
}


def emoji(name: str) -> str:
    emoji_id, fallback = PREMIUM_EMOJIS.get(name, ("", ""))
    if not emoji_id:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'

def escape_html(text: str) -> str:
    return html.escape(str(text))

def icon_button(text: str, emoji_key: str = None, **kwargs) -> InlineKeyboardButton:
    api_kwargs = {}
    if emoji_key and emoji_key in PREMIUM_EMOJIS:
        api_kwargs["icon_custom_emoji_id"] = PREMIUM_EMOJIS[emoji_key][0]
    if api_kwargs:
        kwargs["api_kwargs"] = api_kwargs
    return InlineKeyboardButton(text=text, **kwargs)

def back_btn(callback_data: str = "show_catalog") -> InlineKeyboardButton:
    return icon_button("Back", emoji_key="BACK", callback_data=callback_data)

def cancel_btn() -> InlineKeyboardButton:
    return icon_button("Cancel", callback_data="conv_cancel", emoji_key="CANCEL")

def step_header(current: int, total: int, title: str) -> str:
    bar = "●" * current + "○" * (total - current)
    return f"<b>[{bar}] Step {current}/{total} — {title}</b>\n\n"

# ── Achievements Definition ───────────────────────────────────────────────────
ACHIEVEMENTS = {
    "first_purchase": ("🎯", "First Purchase",   "Unlocked your first tool"),
    "collector":      ("📦", "Collector",         "Unlocked 5 tools"),
    "scholar":        ("📚", "Scholar",           "Unlocked 10 tools"),
    "streak_3":       ("🔥", "On Fire",           "3-day check-in streak"),
    "streak_7":       ("⚡", "Weekly Warrior",    "7-day check-in streak"),
    "streak_30":      ("👑", "Legendary Streak",  "30-day check-in streak"),
    "referrer":       ("🤝", "Connector",         "Referred your first friend"),
    "super_referrer": ("🚀", "Super Connector",   "Referred 5 friends"),
    "reviewer":       ("💬", "Critic",            "Left your first review"),
    "suggester":      ("💡", "Innovator",         "Had a suggestion approved"),
    "rich":           ("💰", "Whale",             "Accumulated 1000+ points"),
}

# ── Conversation States ───────────────────────────────────────────────────────
(ADD_TOOL_NAME, ADD_TOOL_DESC, ADD_TOOL_CAT, ADD_TOOL_TYPE,
 ADD_TOOL_PRICE_STARS, ADD_TOOL_PRICE_POINTS, ADD_TOOL_CONTENT) = range(7)

(SUGGEST_NAME, SUGGEST_DESC, SUGGEST_TYPE,
 SUGGEST_ENTER_PRICE, SUGGEST_CONTENT) = range(10, 15)

EDIT_TOOL_ID, EDIT_TOOL_FIELD, EDIT_TOOL_VALUE = range(30, 33)

BROADCAST_MSG    = 40
REVIEW_RATING    = 50
REVIEW_TEXT      = 51
SEARCH_QUERY     = 60
BAN_USER_ID      = 70
AWARD_USER_ID    = 71
AWARD_AMOUNT     = 72

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_admin(update: Update) -> bool:
    return update.effective_user.id == ADMIN_ID

def get_invite_points() -> int:
    v = db.get_setting("invite_points")
    return int(v) if v else INVITE_POINTS

def get_suggestion_reward() -> int:
    v = db.get_setting("suggestion_reward")
    return int(v) if v else 50

def get_checkin_reward() -> int:
    v = db.get_setting("checkin_reward")
    return int(v) if v else 10

from functools import wraps

# ── Force Join Helper ─────────────────────────────────────────────────────────
async def _send_join_required(update: Update, context: CallbackContext, missing_channels: list,
                              original_callback_data: str = None):
    """Send a message asking to join required channels."""
    keyboard = []
    for ch in missing_channels:
        url = f"https://t.me/{ch[1:]}" if ch.startswith('@') else f"https://t.me/{ch}"
        keyboard.append([icon_button(f"Join {ch}", url=url, emoji_key="LINK")])

    # Add check button
    keyboard.append([icon_button("I have joined", callback_data="check_join", emoji_key="CHECK")])

    text = f"{emoji('LOCK')} <b>Access Restricted</b>\n\nYou must join the following channels to use this bot:\n\n"
    for ch in missing_channels:
        text += f"• {ch}\n"
    text += "\nAfter joining, click the button below."

    if update.callback_query:
        if original_callback_data:
            context.user_data["pending_callback"] = original_callback_data
        await update.callback_query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def _is_user_joined_all(user_id: int, context: CallbackContext) -> tuple:
    """Return (joined: bool, missing_channels: list)."""
    missing = []
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ("member", "creator", "administrator"):
                missing.append(channel)
        except Exception:
            missing.append(channel)  # assume not joined if bot can't check
    return len(missing) == 0, missing

def force_join(func):
    """Decorator to enforce joining required channels before executing the function."""
    @wraps(func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        joined, missing = await _is_user_joined_all(user_id, context)
        if joined:
            return await func(update, context, *args, **kwargs)
        # Not joined → store original callback data if applicable
        original_data = None
        if update.callback_query:
            original_data = update.callback_query.data
        await _send_join_required(update, context, missing, original_data)
        return
    return wrapper

async def check_join_callback(update: Update, context: CallbackContext):
    """Callback handler for 'check_join' button."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    joined, missing = await _is_user_joined_all(user_id, context)
    if joined:
        # user joined all channels → retry the pending action
        pending = context.user_data.pop("pending_callback", None)
        if pending:
            # simulate the original callback
            new_query = query
            new_query.data = pending
            await query.edit_message_text(
                f"{emoji('CHECK')} <b>All channels joined!</b>\n\nYou can now use the bot. Please retry your action{emoji('TEETH')}.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[back_btn("show_catalog")]])
            )
        else:
            # just acknowledge
            await query.edit_message_text(
                f"{emoji('CHECK')} Thanks for joining! You can now use the bot.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[back_btn("show_catalog")]])
            )
    else:
        # still missing some channels
        await _send_join_required(update, context, missing, context.user_data.get("pending_callback"))

def stars(n: int) -> str:
    if n <= 0:
        return "☆☆☆☆☆"
    n = min(5, n)
    return "⭐" * n + "☆" * (5 - n)

# ── Achievement engine ────────────────────────────────────────────────────────
async def check_and_award(bot, user_id: int, trigger: str):
    """Award achievements based on trigger events. Notifies user on unlock."""
    unlocked = db.get_user_achievements(user_id)
    earned = []

    purchases = len(db.get_user_purchases(user_id))
    referrals = db.count_referrals(user_id)
    user      = db.get_user(user_id)
    streak    = user['streak'] if user else 0
    points    = user['points'] if user else 0

    candidates = []
    if trigger == "purchase":
        if purchases >= 1:  candidates.append("first_purchase")
        if purchases >= 5:  candidates.append("collector")
        if purchases >= 10: candidates.append("scholar")
    if trigger == "referral":
        if referrals >= 1: candidates.append("referrer")
        if referrals >= 5: candidates.append("super_referrer")
    if trigger == "checkin":
        if streak >= 3:  candidates.append("streak_3")
        if streak >= 7:  candidates.append("streak_7")
        if streak >= 30: candidates.append("streak_30")
    if trigger == "review":
        candidates.append("reviewer")
    if trigger == "suggestion_approved":
        candidates.append("suggester")
    if trigger == "points" and points >= 1000:
        candidates.append("rich")

    for key in candidates:
        if key not in unlocked:
            db.award_achievement(user_id, key)
            icon, name, desc = ACHIEVEMENTS[key]
            earned.append((icon, name, desc))

    for icon, name, desc in earned:
        try:
            await bot.send_message(
                user_id,
                f"{emoji('TROPHY')} <b>Achievement Unlocked!</b>\n\n"
                f"{icon} <b>{name}</b>\n<i>{desc}</i>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

# ── Cancel helpers ────────────────────────────────────────────────────────────
async def cancel_all(update: Update, context: CallbackContext):
    context.user_data.clear()
    msg, keyboard, _ = await _build_catalog()
    text = f"{emoji('CANCEL')} Cancelled.\n\n" + (msg or "")
    if keyboard:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def conv_cancel_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    msg, keyboard, _ = await _build_catalog()
    text = f"{emoji('CANCEL')} Cancelled.\n\n" + (msg or "")
    if keyboard:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    else:
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return ConversationHandler.END

# ── Catalog builder ───────────────────────────────────────────────────────────
ITEMS_PER_PAGE = 5  # Tools per page

async def _build_catalog(category: str = None, page: int = 0):
    """Build catalog with pagination."""
    tools_list = db.get_all_active_tools(category=category)
    if not tools_list:
        return None, None, 0

    total_pages = (len(tools_list) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    page_tools = tools_list[start_idx:end_idx]

    keyboard = []
    for tool in page_tools:
        avg = db.get_avg_rating(tool["id"])
        rating_str = f" {stars(round(avg))}" if avg else ""
        cat_str = f" [{tool['category'] or 'General'}]" if tool['category'] else ""
        keyboard.append([
            icon_button(
                f"{escape_html(tool['name'])}{cat_str}{rating_str}",
                callback_data=f"tool_{tool['id']}",
            )
        ])
        actions = []
        if tool["price_stars"]:
            actions.append(
                icon_button(f"{tool['price_stars']}", callback_data=f"buystars_{tool['id']}", emoji_key="STAR"))
        if tool["price_points"]:
            actions.append(
                icon_button(f"{tool['price_points']}", callback_data=f"buypoints_{tool['id']}", emoji_key="POINT"))
        if actions:
            keyboard.append(actions)

    # Pagination controls
    nav_buttons = []
    if page > 0:
        nav_buttons.append(icon_button("Previous", callback_data=f"catalog_page_{page - 1}", emoji_key="BACK"))
    if page < total_pages - 1:
        nav_buttons.append(icon_button("Next", callback_data=f"catalog_page_{page + 1}", emoji_key="NEXT"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    # Main menu buttons (always visible)
    keyboard += [
        [
            icon_button("Search", callback_data="search_start", emoji_key="SEARCH"),
            icon_button("Categories", callback_data="show_categories", emoji_key="TAG"),
        ],
        [
            icon_button("Suggest", callback_data="suggest_start", emoji_key="bulb"),
            icon_button("Leaderboard", callback_data="show_leaderboard", emoji_key="TROPHY"),
        ],
        [
            icon_button("About", callback_data="show_info", emoji_key="INFO"),
            icon_button("My Points", callback_data="show_points", emoji_key="POINT"),
            icon_button("My Tools", callback_data="show_purchases", emoji_key="pack"),
        ],
        [
            icon_button("Favorites", callback_data="show_favorites", emoji_key="FAV"),
            icon_button("Daily Reward", callback_data="daily_checkin", emoji_key="GIFT"),
        ],
    ]

    msg = (
        f"{emoji('TREASURE')} <b>Premium Dev Toolbox</b>\n"
        f"{emoji('ROCKET')} <i>Page {page + 1}/{total_pages}</i> • {len(page_tools)} tools shown\n\n"
        f"{emoji('LOCK')} Tap a tool · ⭐/🏅 to buy instantly"
    )
    return msg, InlineKeyboardMarkup(keyboard), total_pages

async def send_tool_detail_message(chat_id, user_id, tool_id, context: CallbackContext):
    """Send the tool detail (not-owned version) to a chat."""
    tool = db.get_tool(tool_id)
    if not tool:
        await context.bot.send_message(chat_id, "Tool not found.")
        return

    is_fav = db.is_favorite(user_id, tool_id)
    fav_text = "❤️ Unfav" if is_fav else "🤍 Favorite"

    if db.user_has_purchased(user_id, tool_id):
        # Owned tool – send content directly
        await send_tool_content(chat_id, tool, context)
        reviews = db.get_tool_reviews(tool_id)
        rev_txt = ""
        if reviews:
            rev_txt = f"\n\n{emoji('REVIEW')} <b>Reviews</b>\n"
            for r in reviews[:3]:
                uname = f"@{r['username']}" if r['username'] else "User"
                rev_txt += f"{stars(r['rating'])} <i>{r['review_text'] or ''}</i> — {escape_html(uname)}\n"
        await context.bot.send_message(
            chat_id,
            f"{emoji('UNLOCK')} <b>{escape_html(tool['name'])}</b> — yours!\n\n"
            f"{rev_txt}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [icon_button(fav_text, callback_data=f"fav_{tool_id}", emoji_key="FAV"),
                 icon_button("Review", callback_data=f"review_{tool_id}", emoji_key="REVIEW")],
                [icon_button("My Tools", callback_data="show_purchases", emoji_key="pack")],
                [back_btn("show_catalog")],
            ]),
        )
        return

    # Not owned – show buy menu
    avg = db.get_avg_rating(tool_id)
    rating_line = f"\n{emoji('STAR')} Rating: <b>{avg:.1f}/5</b>" if avg else ""
    cat_line = f"\nCategory: <b>{escape_html(tool['category'] or 'General')}</b>" if tool['category'] else ""

    msg = (
        f"{emoji('LOCK')} <b>{escape_html(tool['name'])}</b>{cat_line}{rating_line}\n\n"
        f"{emoji('paper')} {escape_html(tool['description'])}\n\n"
        f"<b>Unlock with:</b>\n"
    )
    if tool['price_stars']:
        msg += f"  {emoji('STAR')} <b>{tool['price_stars']}</b> Telegram Stars\n"
    if tool['price_points']:
        msg += f"  {emoji('POINT')} <b>{tool['price_points']}</b> Points\n"

    buy_row = []
    if tool['price_stars']:
        buy_row.append(icon_button(f"{tool['price_stars']} Stars", callback_data=f"buystars_{tool_id}", emoji_key="STAR"))
    if tool['price_points']:
        buy_row.append(icon_button(f"{tool['price_points']} pts", callback_data=f"buypoints_{tool_id}", emoji_key="POINT"))

    keyboard = []
    if buy_row:
        keyboard.append(buy_row)
    keyboard.append([icon_button(fav_text, callback_data=f"fav_{tool_id}", emoji_key="FAV")])
    keyboard.append([back_btn("show_catalog")])

    await context.bot.send_message(
        chat_id,
        msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

@force_join
async def send_category_tools(update: Update, context: CallbackContext, category: str):
    """Send a list of tools in a given category to the user."""
    tools = db.get_all_active_tools(category=category)
    if not tools:
        await update.message.reply_text(f"No tools in <b>{escape_html(category)}</b> yet.", parse_mode=ParseMode.HTML)
        return
    text = f"{emoji('TAG')} <b>{escape_html(category)} tools</b>\n\n"
    keyboard = []
    for tool in tools:
        keyboard.append([icon_button(escape_html(tool['name']), callback_data=f"tool_{tool['id']}", emoji_key="LOCK")])
    keyboard.append([back_btn("show_catalog")])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
# ── /start ────────────────────────────────────────────────────────────────────
@force_join
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    db.add_user_if_not_exists(user.id, user.username)

    refer_id = None
    if context.args and context.args[0].startswith("ref"):
        try:
            refer_id = int(context.args[0][3:])
        except ValueError:
            pass

    if refer_id and refer_id != user.id and not db.user_has_referrer(user.id):
        db.set_referrer(user.id, refer_id)
        pts = get_invite_points()
        db.add_points(refer_id, pts, "referral")
        await check_and_award(context.bot, refer_id, "referral")
        try:
            await context.bot.send_message(
                refer_id,
                f"{emoji('party')} {user.mention_html()} joined via your link!\n"
                f"You earned {emoji('POINT')} <b>{pts} points</b>!",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    # ── Inline deep links ───────────────────────────────────────────────────
    if context.args:
        arg = context.args[0]
        if arg.startswith("tool_"):
            try:
                tool_id = int(arg[5:])
                await send_tool_detail_message(
                    update.effective_chat.id,
                    user.id,
                    tool_id,
                    context,
                )
                return
            except ValueError:
                pass
        elif arg.startswith("category:"):
            cat = arg.split(":", 1)[1]
            await send_category_tools(update, context, cat)
            return

    keyboard = InlineKeyboardMarkup([
        [icon_button("Browse Tools",    callback_data="show_catalog", emoji_key="SEARCH")],
        [
            icon_button("My Points",    callback_data="show_points", emoji_key="POINT"),
            icon_button("My Tools",     callback_data="show_purchases", emoji_key="pack"),
            icon_button("Favorites",    callback_data="show_favorites", emoji_key="FAV"),
        ],
        [
            icon_button("Daily Reward", callback_data="daily_checkin", emoji_key="GIFT"),
            icon_button("Leaderboard",  callback_data="show_leaderboard", emoji_key="TROPHY"),
        ],
        [
            icon_button("Suggest",      callback_data="suggest_start", emoji_key="bulb"),
            icon_button("About",        callback_data="show_info", emoji_key="INFO"),
        ],
    ])
    await update.message.reply_text(
        f"{emoji('WAVE')} <b>Welcome to the Premium Dev Tools Gallery!{emoji('IMAGE')}</b>\n\n"
        f"{emoji('TREASURE')} Curated premium tools for developers and noobs.\n"
        f"{emoji('STAR')} Unlock with Telegram Stars or Points.<I>Monetization coming soon..</i>\n"
        f"{emoji('GIFT')} Invite friends & suggest tools for bonus points.\n"
        f"{emoji('FIRE')} Check in daily to build your streak!\n\n"
        f"{emoji('INFO')} Use /help for all commands.",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )

# ── /help ─────────────────────────────────────────────────────────────────────
@force_join
async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text(
        f"{emoji('INFO')} <b>Commands</b>\n\n"
        f"<b>User</b>\n"
        f"/start — Welcome screen\n"
        f"/tools — Browse catalog\n"
        f"/search — Search for a tool\n"
        f"/points — Balance &amp; referral link\n"
        f"/my_purchases — Owned tools\n"
        f"/favorites — Saved favorites\n"
        f"/checkin — Claim daily reward\n"
        f"/leaderboard — Top points earners\n"
        f"/achievements — Your badges\n"
        f"/suggest — Suggest a tool\n"
        f"/cancel — Abort any operation\n\n",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            icon_button("Browse Tools", callback_data="show_catalog", emoji_key="SEARCH")
        ]]),
    )

# ── /tools ────────────────────────────────────────────────────────────────────
@force_join
async def tools(update: Update, context: CallbackContext):
    msg, keyboard, total = await _build_catalog(page=0)
    if not keyboard:
        await update.message.reply_text(
            f"{emoji('WARNING')} No tools yet — check back soon!", parse_mode=ParseMode.HTML
        )
        return
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)

@force_join
async def show_catalog(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    # Get page from callback or default to 0
    page = 0
    if query.data.startswith("catalog_page_"):
        page = int(query.data.split("_")[-1])

    msg, keyboard, total = await _build_catalog(page=page)
    if not keyboard:
        await query.edit_message_text(
            f"{emoji('WARNING')} No tools yet.", parse_mode=ParseMode.HTML
        )
        return

    await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)

# ── Inline Mode Handler ──────────────────────────────────────────────────────
def build_tool_inline_result(tool, bot_username):
    """Helper: create an InlineQueryResultArticle for a tool."""
    avg = db.get_avg_rating(tool["id"])
    stars_str = stars(round(avg)) if avg else ""
    desc_parts = [tool["category"] or "General"]
    prices = []

    if tool["price_stars"]:
        prices.append(f"⭐{tool['price_stars']}")
    if tool["price_points"]:
        prices.append(f"🏅{tool['price_points']}")

    if prices:
        desc_parts.append(" ".join(prices))
    else:
        desc_parts.append("Free")

    if stars_str:
        desc_parts.append(stars_str)
    description = " | ".join(desc_parts)

    # Escape texts safely
    safe_name = html.escape(tool["name"])
    safe_desc = html.escape(tool["description"])
    unlock_text = " ".join(prices) if prices else "Free"

    return InlineQueryResultArticle(
        id=f"tool_{tool['id']}",
        title=tool["name"],
        description=description,
        input_message_content=InputTextMessageContent(
            message_text=(
                f"🔒 <b>{safe_name}</b>\n"
                f"{safe_desc}\n\n"
                f"<b>Unlock with:</b> {unlock_text}"
            ),
            parse_mode=ParseMode.HTML,
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔍 View & Buy",
                        url=f"https://t.me/toolstorerobot?start=tool_{tool['id']}",
                    )
                ]
            ]
        ),
    )


async def inline_query(update: Update, context: CallbackContext):
    query_text = update.inline_query.query.strip()
    user_id = update.inline_query.from_user.id
    bot_username = context.bot.username
    results = []

    # ─── No query → show categories (browse) ────────────────────────────────
    if not query_text:
        cats = db.get_all_categories()
        for cat in cats:
            count = db.count_tools_in_category(cat)
            results.append(
                InlineQueryResultArticle(
                    id=f"cat_{cat}",
                    title=f"📁 {cat}",
                    description=f"{count} tools",
                    input_message_content=InputTextMessageContent(
                        message_text=f"📁 Browse {cat} tools",
                        parse_mode=ParseMode.HTML,
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    f"Open {cat} tools in bot",
                                    url=f"https://t.me/toolstorerobot?start=category_{cat}",
                                )
                            ]
                        ]
                    ),
                )
            )
        await update.inline_query.answer(results, cache_time=0)
        return

    # ─── Specific keywords ──────────────────────────────────────────────────
    query_lower = query_text.lower()

    if query_lower in ("random", "r"):
        all_tools = db.get_all_active_tools()
        if all_tools:
            tool = random.choice(all_tools)
            results.append(build_tool_inline_result(tool, bot_username))
    elif query_lower in ("favs", "favorites", "favourites"):
        favs = db.get_favorites(user_id)
        for fav in favs[:10]:
            tool = db.get_tool(fav["tool_id"])
            if tool:
                results.append(build_tool_inline_result(tool, bot_username))
    elif query_text.startswith("category:"):
        cat = query_text.split(":", 1)[1].strip()
        tools = db.get_all_active_tools(category=cat)
        for tool in tools[:10]:
            results.append(build_tool_inline_result(tool, bot_username))
    else:
        # Default: tool search
        tools = db.search_tools(query_text)
        for tool in tools[:10]:
            results.append(build_tool_inline_result(tool, bot_username))

    await update.inline_query.answer(results, cache_time=0)

# ── Categories ────────────────────────────────────────────────────────────────
async def show_categories(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    cats = db.get_all_categories()
    if not cats:
        await query.edit_message_text(
            f"{emoji('INFO')} No categories yet.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("show_catalog")]]),
        )
        return
    keyboard = []
    for cat in cats:
        count = db.count_tools_in_category(cat)
        keyboard.append([icon_button(f"{cat}  ({count})", callback_data=f"cat_{cat}", emoji_key="TAG")])
    keyboard.append([back_btn("show_catalog")])
    await query.edit_message_text(
        f"{emoji('TAG')} <b>Categories</b>\n\nBrowse tools by category:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_category(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    # Parse category and page
    data = query.data[4:]  # Remove "cat_"
    if "_page_" in data:
        category, page = data.rsplit("_page_", 1)
        page = int(page)
    else:
        category = data
        page = 0

    msg, keyboard_obj, total = await _build_catalog(category=category, page=page)
    if not keyboard_obj:
        await query.edit_message_text(
            f"{emoji('INFO')} No tools in <b>{escape_html(category)}</b> yet.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("show_categories")]]),
        )
        return

    rows = list(keyboard_obj.inline_keyboard)

    await query.edit_message_text(
        f"{emoji('TAG')} <b>{escape_html(category)}</b> tools (Page {page + 1}/{total}):\n\n" + msg,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(rows),
    )

# ── Search ────────────────────────────────────────────────────────────────────
@force_join
async def search_start(update: Update, context: CallbackContext):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            f"{emoji('SEARCH')} <b>Search Tools</b>\n\nType a keyword to search by name or description:\n\n<i>/cancel to abort.</i>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"{emoji('SEARCH')} <b>Search Tools</b>\n\nType a keyword to search:\n\n<i>/cancel to abort.</i>",
            parse_mode=ParseMode.HTML,
        )
    return SEARCH_QUERY

@force_join
async def search_query(update: Update, context: CallbackContext):
    q = update.message.text.strip()
    results = db.search_tools(q)
    if not results:
        await update.message.reply_text(
            f"{emoji('WARNING')} No tools found for <b>{escape_html(q)}</b>.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [icon_button("Search Again", callback_data="search_start", emoji_key="SEARCH")],
                [back_btn("show_catalog")],
            ]),
        )
        return ConversationHandler.END

    keyboard = []
    for tool in results:
        avg = db.get_avg_rating(tool["id"])
        rating_str = f" {stars(round(avg))}" if avg else ""
        keyboard.append([
            icon_button(f"{escape_html(tool['name'])}{rating_str}", callback_data=f"tool_{tool['id']}", emoji_key="LOCK")
        ])
    keyboard.append([back_btn("show_catalog")])
    await update.message.reply_text(
        f"{emoji('SEARCH')} <b>Results for '{escape_html(q)}'</b>  ({len(results)} found):",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ConversationHandler.END

# ── Favorites ─────────────────────────────────────────────────────────────────
async def toggle_favorite(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    tool_id = int(query.data.split("_")[1])
    user_id = query.from_user.id
    is_fav  = db.toggle_favorite(user_id, tool_id)
    status  = "Added to" if is_fav else "Removed from"
    await query.answer(f"{status} favorites!", show_alert=False)
    # Re-render tool detail
    await tool_detail(update, context)

async def show_favorites(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        send = query.edit_message_text
    else:
        user_id = update.effective_user.id
        send = update.message.reply_text

    favs = db.get_favorites(user_id)
    if not favs:
        text = (
            f"{emoji('FAV')} <b>Your Favorites</b>\n\n"
            f"You haven't saved any tools yet.\n"
            f"Tap {emoji('HEART')} on any tool detail page to save it!"
        )
        kb = InlineKeyboardMarkup([[back_btn("show_catalog")]])
        if update.callback_query:
            await send(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await send(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    keyboard = []
    for fav in favs:
        tool = db.get_tool(fav["tool_id"])
        if tool:
            keyboard.append([icon_button(
                f"{escape_html(tool['name'])}",
                callback_data=f"tool_{tool['id']}",
                emoji_key="LOCK"
            )])
    keyboard.append([back_btn("show_catalog")])
    text = f"{emoji('FAV')} <b>Your Favorites</b>  ({len(favs)} saved)"
    if update.callback_query:
        await send(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await send(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

# ── Daily Check-in ────────────────────────────────────────────────────────────
@force_join
async def daily_checkin(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        edit    = query.edit_message_text
    else:
        user_id = update.effective_user.id
        edit    = None

    today       = str(date.today())
    last_checkin = db.get_last_checkin(user_id)
    streak      = db.get_streak(user_id)

    if last_checkin == today:
        text = (
            f"{emoji('STREAK')} <b>Already checked in today!</b>\n\n"
            f"Streak: <b>{streak} day{'s' if streak != 1 else ''}</b> {emoji('FIRE')}\n"
            f"Come back tomorrow to keep it going!"
        )
        kb = InlineKeyboardMarkup([[back_btn("show_catalog")]])
        if edit:
            await edit(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # Update streak
    yesterday = str(date.fromordinal(date.today().toordinal() - 1))
    new_streak = (streak + 1) if last_checkin == yesterday else 1
    db.update_checkin(user_id, today, new_streak)

    reward = get_checkin_reward()
    bonus  = 0
    bonus_msg = ""
    if new_streak % 7 == 0:
        bonus = reward * 2
        bonus_msg = f"\n{emoji('party')} <b>+{bonus} bonus</b> for a {new_streak}-day streak!"
    db.add_points(user_id, reward + bonus, "daily_checkin")
    await check_and_award(context.bot, user_id, "checkin")
    await check_and_award(context.bot, user_id, "points")

    text = (
        f"{emoji('GIFT')} <b>Daily Reward Claimed!</b>\n\n"
        f"+ <b>{reward} points</b>{bonus_msg}\n\n"
        f"{emoji('STREAK')} Streak: <b>{new_streak} day{'s' if new_streak != 1 else ''}</b>\n"
        f"{'🔥' * min(new_streak, 10)}"
    )
    kb = InlineKeyboardMarkup([
        [icon_button("Leaderboard", callback_data="show_leaderboard", emoji_key="TROPHY")],
        [back_btn("show_catalog")],
    ])
    if edit:
        await edit(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ── Leaderboard ───────────────────────────────────────────────────────────────
@force_join
async def show_leaderboard(update: Update, context: CallbackContext):
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        send = query.edit_message_text
    else:
        send = update.message.reply_text

    top = db.get_leaderboard(limit=10)
    if not top:
        text = f"{emoji('TROPHY')} <b>Leaderboard</b>\n\nNo entries yet. Start earning points!"
    else:
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        lines  = [f"{emoji('TROPHY')} <b>Top Points Earners</b>\n"]
        for i, row in enumerate(top):
            uname = f"@{row['username']}" if row['username'] else f"User {row['user_id']}"
            lines.append(f"{medals[i]} {escape_html(uname)}  —  <b>{row['points']} pts</b>")
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([[back_btn("show_catalog")]])
    await send(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ── Achievements ──────────────────────────────────────────────────────────────
async def show_achievements(update: Update, context: CallbackContext):
    if update.callback_query:
        query   = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        send    = query.edit_message_text
    else:
        user_id = update.effective_user.id
        send    = update.message.reply_text

    unlocked = db.get_user_achievements(user_id)
    lines    = [f"{emoji('TROPHY')} <b>Your Achievements</b>\n"]
    for key, (icon, name, desc) in ACHIEVEMENTS.items():
        if key in unlocked:
            lines.append(f"{icon} <b>{name}</b> — <i>{desc}</i>")
        else:
            lines.append(f"{emoji('LOCK')}<s>{name}</s>")

    kb = InlineKeyboardMarkup([[back_btn("show_catalog")]])
    await send("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)

# ── Ratings & Reviews ─────────────────────────────────────────────────────────
async def review_start(update: Update, context: CallbackContext):
    query   = update.callback_query
    await query.answer()
    tool_id = int(query.data.split("_")[1])
    user_id = query.from_user.id

    if not db.user_has_purchased(user_id, tool_id):
        await query.answer("You must own this tool to leave a review, Bro Geezzz!", show_alert=True)
        return ConversationHandler.END

    context.user_data["review_tool_id"] = tool_id
    keyboard = InlineKeyboardMarkup([[
        icon_button("1", callback_data="rate_1", emoji_key="MEDAL1"),
        icon_button("2", callback_data="rate_2", emoji_key="MEDAL2"),
        icon_button("3", callback_data="rate_3", emoji_key="MEDAL3"),
        icon_button("⭐ 4", callback_data="rate_4"),
        icon_button("5", callback_data="rate_5", emoji_key="Star5"),
    ], [cancel_btn()]])
    await query.edit_message_text(
        f"{emoji('REVIEW')} <b>Rate this Tool</b>\n\nChoose your rating:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
    return REVIEW_RATING

async def review_rating(update: Update, context: CallbackContext):
    query  = update.callback_query
    await query.answer()
    rating = int(query.data.split("_")[1])
    context.user_data["review_rating"] = rating
    await query.edit_message_text(
        f"{emoji('REVIEW')} You rated: {stars(rating)}\n\n"
        f"Now write a short <b>review</b> (or send <b>skip</b> to just save the rating):\n\n"
        f"<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return REVIEW_TEXT

async def review_text(update: Update, context: CallbackContext):
    tool_id = context.user_data["review_tool_id"]
    rating  = context.user_data["review_rating"]
    text    = update.message.text.strip()
    user_id = update.effective_user.id
    review  = "" if text.lower() == "skip" else text

    db.save_review(user_id, tool_id, rating, review)
    await check_and_award(context.bot, user_id, "review")

    tool = db.get_tool(tool_id)
    await update.message.reply_text(
        f"{emoji('CHECK')} <b>Review saved!</b>\n\n"
        f"{escape_html(tool['name'])}: {stars(rating)}\n"
        f"{'<i>' + escape_html(review) + '</i>' if review else ''}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            icon_button(f"Back to Tool", callback_data=f"tool_{tool_id}", emoji_key="BACK")
        ]]),
    )
    context.user_data.clear()
    return ConversationHandler.END

# ── /points & /my_purchases ───────────────────────────────────────────────────
async def points_command(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    db.add_user_if_not_exists(user_id, update.effective_user.username)
    user = db.get_user(user_id)
    streak = db.get_streak(user_id)
    bot_username = context.bot.username
    await update.message.reply_text(
        f"{emoji('POINT')} <b>Your Balance</b>\n\n"
        f"Points: <b>{user['points']}</b>\n"
        f"Streak: <b>{streak} day{'s' if streak != 1 else ''}</b> {emoji('FIRE')}\n\n"
        f"{emoji('PEOPLE')} Earn <b>{get_invite_points()} pts</b> per referral:\n"
        f"<code>https://t.me/{bot_username}?start=ref{user_id}</code>\n\n"
        f"{emoji('bulb')} Approved suggestions earn <b>{get_suggestion_reward()} pts</b>!\n"
        f"{emoji('GIFT')} Daily check-in earns <b>{get_checkin_reward()} pts</b>!",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [icon_button("Claim Daily", callback_data="daily_checkin", emoji_key="GIFT")],
            [icon_button("Suggest",     callback_data="suggest_start", emoji_key="bulb")],
            [icon_button("Browse",      callback_data="show_catalog", emoji_key="TREASURE")],
        ]),
    )

async def show_points(update: Update, context: CallbackContext):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user    = db.get_user(user_id)
    streak  = db.get_streak(user_id)
    bot_username = context.bot.username
    await query.edit_message_text(
        f"{emoji('POINT')} <b>Your Balance</b>\n\n"
        f"Points: <b>{user['points']}</b>\n"
        f"Streak: <b>{streak} day{'s' if streak != 1 else ''}</b> {emoji('FIRE')}\n\n"
        f"{emoji('PEOPLE')} Earn <b>{get_invite_points()} pts</b> per referral:\n"
        f"<code>https://t.me/{bot_username}?start=ref{user_id}</code>\n\n"
        f"{emoji('bulb')} Approved suggestions earn <b>{get_suggestion_reward()} pts</b>!\n"
        f"{emoji('GIFT')} Daily check-in earns <b>{get_checkin_reward()} pts</b>!",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [icon_button("Claim Daily",   callback_data="daily_checkin", emoji_key="GIFT")],
            [icon_button("Leaderboard",   callback_data="show_leaderboard", emoji_key="TROPHY")],
            [icon_button("Achievements",  callback_data="show_achievements", emoji_key="TROPHY")],
            [back_btn("show_catalog")],
        ]),
    )

async def my_purchases(update: Update, context: CallbackContext):
    user_id   = update.effective_user.id
    purchases = db.get_user_purchases(user_id)
    kb = InlineKeyboardMarkup([[back_btn("show_catalog")]])
    if not purchases:
        await update.message.reply_text(
            f"{emoji('INFO')} No tools unlocked yet.\nBrowse the catalog to get started!",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[icon_button("Browse", callback_data="show_catalog", emoji_key="TREASURE")]]),
        )
        return
    text = f"{emoji('TREASURE')} <b>Your Unlocked Tools</b>\n\n"
    for p in purchases:
        tool = db.get_tool(p["tool_id"])
        if tool:
            text += f"{emoji('UNLOCK')} <b>{escape_html(tool['name'])}</b>  <i>via {p['purchase_type'] or '?'}</i>\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def show_purchases(update: Update, context: CallbackContext):
    query     = update.callback_query
    await query.answer()
    user_id   = query.from_user.id
    purchases = db.get_user_purchases(user_id)
    if not purchases:
        await query.edit_message_text(
            f"{emoji('INFO')} No tools unlocked yet.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[icon_button("Browse", callback_data="show_catalog", emoji_key="TREASURE")]]),
        )
        return
    text = f"{emoji('TREASURE')} <b>Your Unlocked Tools</b>\n\n"
    for p in purchases:
        tool = db.get_tool(p["tool_id"])
        if tool:
            text += f"{emoji('UNLOCK')} <b>{escape_html(tool['name'])}</b>\n"
    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[back_btn("show_catalog")]]),
    )

async def send_tool_content(chat_id, tool, context: CallbackContext):
    """Send the actual content (text or file) of a tool."""
    content = tool['content']
    if content.startswith('[PHOTO:'):
        file_id = content[7:-1]   # extract file_id
        caption = content[len(file_id)+8:] if '\n' in content else ''
        await context.bot.send_photo(chat_id, file_id, caption=caption or tool['name'])
    elif content.startswith('[DOCUMENT:'):
        parts = content[10:-1].split(':', 1)
        file_id = parts[0]
        caption = content.split('\n', 1)[1] if '\n' in content else ''
        await context.bot.send_document(chat_id, file_id, caption=caption or tool['name'])
    elif content.startswith('[VIDEO:'):
        file_id = content[9:-1]
        caption = content.split('\n', 1)[1] if '\n' in content else ''
        await context.bot.send_video(chat_id, file_id, caption=caption or tool['name'])
    else:
        # plain text
        await context.bot.send_message(chat_id, content, parse_mode=None)
# ── Tool Detail (with favorites + review button) ──────────────────────────────
async def tool_detail(update: Update, context: CallbackContext):
    query   = update.callback_query
    await query.answer()
    # Support both tool_<id> and fav_<id> callbacks
    raw_id  = query.data.split("_")[-1]
    tool_id = int(raw_id)
    tool    = db.get_tool(tool_id)

    if not tool:
        await query.edit_message_text(
            f"{emoji('CANCEL')} Tool not found.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[back_btn("show_catalog")]]),
        )
        return

    user_id  = query.from_user.id
    is_fav   = db.is_favorite(user_id, tool_id)
    fav_text = "❤️ Unfav" if is_fav else "🤍 Favorite"

    # Already owned → reveal
    if db.user_has_purchased(user_id, tool_id):
        reviews = db.get_tool_reviews(tool_id)
        avg     = db.get_avg_rating(tool_id)
        rev_txt = ""
        if reviews:
            rev_txt = f"\n\n{emoji('REVIEW')} <b>Reviews</b>\n"
            for r in reviews[:3]:
                uname = f"@{r['username']}" if r['username'] else "User"
                rev_txt += f"{stars(r['rating'])} <i>{escape_html(r.get('review_text','') or '')}</i> — {escape_html(uname)}\n"
        await send_tool_content(user_id, tool, context)
        await query.edit_message_text(
            f"{emoji('UNLOCK')} <b>{escape_html(tool['name'])}</b> — yours!\n\n"
            f"{rev_txt}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [icon_button(fav_text,              callback_data=f"fav_{tool_id}"),
                 icon_button("Review",           callback_data=f"review_{tool_id}", emoji_key="REVIEW")],
                [icon_button("My Tools",         callback_data="show_purchases", emoji_key="pack")],
                [back_btn("show_catalog")],
            ]),
        )
        return

    # Not yet owned
    avg = db.get_avg_rating(tool_id)
    rating_line = f"\n{emoji('STAR')} Rating: <b>{avg:.1f}/5</b>" if avg else ""
    cat_line    = f"\nCategory: <b>{escape_html(tool['category'])}</b>" if tool["category"] else ""

    msg = (
        f"{emoji('LOCK')} <b>{escape_html(tool['name'])}</b>{cat_line}{rating_line}\n\n"
        f"{emoji('paper')} {escape_html(tool['description'])}\n\n"
        f"<b>Unlock with:</b>\n"
    )
    if tool["price_stars"]:
        msg += f"  {emoji('STAR')} <b>{tool['price_stars']}</b> Telegram Stars\n"
    if tool["price_points"]:
        msg += f"  {emoji('POINT')} <b>{tool['price_points']}</b> Points\n"

    buy_row = []
    if tool["price_stars"]:
        buy_row.append(icon_button(f"{tool['price_stars']} Stars", callback_data=f"buystars_{tool_id}", emoji_key="STAR"))
    if tool["price_points"]:
        buy_row.append(icon_button(f"{tool['price_points']} pts",  callback_data=f"buypoints_{tool_id}", emoji_key="POINT"))

    keyboard = []
    if buy_row:
        keyboard.append(buy_row)
    keyboard.append([icon_button(fav_text, callback_data=f"fav_{tool_id}")])
    keyboard.append([back_btn("show_catalog")])

    await query.edit_message_text(msg, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

# ── Buy with Stars ────────────────────────────────────────────────────────────
async def buy_stars(update: Update, context: CallbackContext):
    query   = update.callback_query
    await query.answer()
    tool_id = int(query.data.split("_")[1])
    user_id = query.from_user.id
    tool    = db.get_tool(tool_id)

    if not tool or not tool["price_stars"]:
        await query.answer("Invalid tool.", show_alert=True); return
    if db.user_has_purchased(user_id, tool_id):
        await query.answer("Bro, You already own this!", show_alert=True); return

    await context.bot.send_invoice(
        chat_id=user_id, title=tool["name"],
        description=(tool["description"] or tool["name"])[:255],
        payload=f"stars_{tool_id}", provider_token="", currency="XTR",
        prices=[LabeledPrice("Stars", tool["price_stars"])],
    )
    await query.edit_message_text(
        f"{emoji('STAR')} Invoice sent{emoji('CHECK')}!\n\nComplete the payment to unlock <b>{escape_html(tool['name'])}</b>.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[icon_button("Back to Tool", callback_data=f"tool_{tool_id}", emoji_key="BACK")]]),
    )

async def pre_checkout(update: Update, context: CallbackContext):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: CallbackContext):
    payload = update.message.successful_payment.invoice_payload
    if not payload.startswith("stars_"):
        return
    tool_id = int(payload.split("_")[1])
    user_id = update.effective_user.id
    tool    = db.get_tool(tool_id)

    if tool and not db.user_has_purchased(user_id, tool_id):
        db.record_purchase(user_id, tool_id, "stars")
        await check_and_award(context.bot, user_id, "purchase")
        await send_tool_content(user_id, tool, context)
        await update.message.reply_text(
            f"{emoji('party')} <b>Payment successful!</b>\n\n"
            f"{emoji('GIFT')} <b>{escape_html(tool['name'])}</b>:\n\n{tool['content']}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                icon_button("Browse More",  callback_data="show_catalog", emoji_key="TREASURE"),
                icon_button("My Tools",     callback_data="show_purchases", emoji_key="pack"),
            ]]),
        )
    else:
        await update.message.reply_text(
            f"{emoji('WARNING')}\n\nSorry already owned or unavailable.", parse_mode=ParseMode.HTML
        )

# ── Buy with Points ───────────────────────────────────────────────────────────
async def buy_points_handler(update: Update, context: CallbackContext):
    query   = update.callback_query
    await query.answer()
    tool_id = int(query.data.split("_")[1])
    user_id = query.from_user.id
    tool    = db.get_tool(tool_id)

    if not tool or not tool["price_points"]:
        await query.answer("Invalid tool.", show_alert=True); return
    if db.user_has_purchased(user_id, tool_id):
        await query.answer("You already own this!", show_alert=True); return

    user   = db.get_user(user_id)
    needed = tool["price_points"]
    have   = user["points"]

    if have < needed:
        bot_username = context.bot.username
        await query.edit_message_text(
            f"{emoji('WARNING')} <b>Not enough points!</b>\n\n"
            f"Need: <b>{needed} pts</b>  ·  Have: <b>{have} pts</b>  ·  Short: <b>{needed - have} pts</b>\n\n"
            f"{emoji('PEOPLE')} Invite friends:\n<code>https://t.me/{bot_username}?start=ref{user_id}</code>\n\n"
            f"{emoji('GIFT')} Or claim your daily reward!\n"
            f"{emoji('bulb')} Or suggest a tool for <b>{get_suggestion_reward()} pts</b>!",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [icon_button("Daily Reward",  callback_data="daily_checkin", emoji_key="GIFT")],
                [icon_button("Suggest",       callback_data="suggest_start", emoji_key="bulb")],
                [icon_button("Back to Tool",  callback_data=f"tool_{tool_id}", emoji_key="BACK")],
                [back_btn("show_catalog")],
            ]),
        )
        return

    db.deduct_points(user_id, needed)
    db.record_purchase(user_id, tool_id, "points")
    await check_and_award(context.bot, user_id, "purchase")
    await send_tool_content(user_id, tool, context)
    await query.edit_message_text(
        f"{emoji('party')} <b>Unlocked!</b>  Spent <b>{needed} pts</b>.\n\n"
        f"{emoji('GIFT')} <b>{escape_html(tool['name'])}</b>:\n\n{tool['content']}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            icon_button("Browse More",  callback_data="show_catalog", emoji_key="TREASURE"),
            icon_button("My Tools",     callback_data="show_purchases", emoji_key="pack"),
        ]]),
    )

# ── Info ──────────────────────────────────────────────────────────────────────
@force_join
async def show_info(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"{emoji('INFO')} <b>About Premium Dev Toolbox</b>\n\n"
        f"{emoji('TREASURE')} Hand-picked premium tools for developers.\n"
        f"{emoji('STAR')} Unlock with Telegram Stars or Points.\n"
        f"{emoji('PEOPLE')} Earn points by inviting friends.\n"
        f"{emoji('bulb')} Suggest tools — get rewarded on approval.\n"
        f"{emoji('FIRE')} Check in daily to build your streak & earn.\n"
        f"{emoji('TROPHY')} Unlock achievements as you go.\n"
        f"{emoji('LOCK')} Every tool verified and curated.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[back_btn("show_catalog")]]),
    )

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — Broadcast
# ═══════════════════════════════════════════════════════════════════════════════
async def broadcast_start(update: Update, context: CallbackContext):
    if not is_admin(update):
        await update.message.reply_text(f"{emoji('CANCEL')} Admin only.")
        return ConversationHandler.END
    await update.message.reply_text(
        f"{emoji('BELL')} <b>Broadcast</b>\n\n"
        f"Send the message you want to broadcast to all users.\n\n"
        f"<i>Supports HTML formatting. /cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return BROADCAST_MSG

async def broadcast_send(update: Update, context: CallbackContext):
    text     = update.message.text
    all_users = db.get_all_user_ids()
    sent = failed = 0
    status_msg = await update.message.reply_text(
        f"{emoji('ROCKET')} Broadcasting to {len(all_users)} users…"
    )
    for uid in all_users:
        try:
            await context.bot.send_message(uid, text, parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            failed += 1
    await status_msg.edit_text(
        f"{emoji('CHECK')} Broadcast done!\n\n"
        f"✅ Sent: <b>{sent}</b>  ·  ❌ Failed: <b>{failed}</b>",
        parse_mode=ParseMode.HTML,
    )
    return ConversationHandler.END

# ── Admin — Stats ─────────────────────────────────────────────────────────────
async def admin_stats(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    s = db.get_stats()
    await update.message.reply_text(
        f"{emoji('CHART')} <b>Bot Statistics</b>\n\n"
        f"👤 Total users: <b>{s.get('total_users', 0)}</b>\n"
        f"📦 Total tools: <b>{s.get('total_tools', 0)}</b>\n"
        f"🔓 Total purchases: <b>{s.get('total_purchases', 0)}</b>\n"
        f"💡 Pending suggestions: <b>{s.get('pending_suggestions', 0)}</b>\n"
        f"💬 Total reviews: <b>{s.get('total_reviews', 0)}</b>\n"
        f"🔥 Active streaks: <b>{s.get('active_streaks', 0)}</b>\n"
        f"🏅 Points in circulation: <b>{s.get('total_points', 0)}</b>",
        parse_mode=ParseMode.HTML,
    )

# ── Admin — User Info / Ban / Award ──────────────────────────────────────────
async def user_info(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    if not context.args:
        await update.message.reply_text(f"Usage: /userinfo &lt;user_id&gt;", parse_mode=ParseMode.HTML)
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid user ID.")
        return
    u = db.get_user(uid)
    if not u:
        await update.message.reply_text(f"{emoji('CANCEL')} User not found.")
        return
    purchases = len(db.get_user_purchases(uid))
    streak    = db.get_streak(uid)
    unlocked  = db.get_user_achievements(uid)
    banned    = db.is_banned(uid)
    await update.message.reply_text(
        f"{emoji('USER')} <b>User #{uid}</b>\n\n"
        f"Username: @{escape_html(u['username'] or 'N/A')}\n"
        f"Points: <b>{u['points']}</b>\n"
        f"Streak: <b>{streak}d</b>\n"
        f"Purchases: <b>{purchases}</b>\n"
        f"Achievements: <b>{len(unlocked)}</b>\n"
        f"Status: {'🚫 Banned' if banned else '✅ Active'}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            icon_button("🚫 Ban" if not banned else "✅ Unban",
                        callback_data=f"admin_ban_{uid}" if not banned else f"admin_unban_{uid}")
        ]]),
    )

async def ban_user(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /banuser &lt;user_id&gt;", parse_mode=ParseMode.HTML)
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid ID.")
        return
    db.set_banned(uid, True)
    await update.message.reply_text(
        f"{emoji('BAN')} User <b>{uid}</b> banned.", parse_mode=ParseMode.HTML
    )

async def unban_user(update: Update, context: CallbackContext):
    if not is_admin(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /unbanuser &lt;user_id&gt;", parse_mode=ParseMode.HTML)
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid ID.")
        return
    db.set_banned(uid, False)
    await update.message.reply_text(
        f"{emoji('CHECK')} User <b>{uid}</b> unbanned.", parse_mode=ParseMode.HTML
    )

async def admin_ban_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        return
    parts  = query.data.split("_")
    action = parts[1]   # ban | unban
    uid    = int(parts[2])
    db.set_banned(uid, action == "ban")
    msg = f"{emoji('BAN')} Banned" if action == "ban" else f"{emoji('CHECK')} Unbanned"
    await query.edit_message_text(f"{msg} user <b>{uid}</b>.", parse_mode=ParseMode.HTML)

async def award_points_start(update: Update, context: CallbackContext):
    if not is_admin(update):
        await update.message.reply_text(f"{emoji('CANCEL')} Admin only.")
        return ConversationHandler.END
    await update.message.reply_text(
        f"{emoji('POINT')} <b>Award Points</b>\n\nSend the <b>User ID</b> to award points to:\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return AWARD_USER_ID

@force_join
async def award_points_user(update: Update, context: CallbackContext):
    try:
        uid = int(update.message.text)
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid ID. Send a number:")
        return AWARD_USER_ID
    if not db.get_user(uid):
        await update.message.reply_text(f"{emoji('CANCEL')} User not found. Try again:")
        return AWARD_USER_ID
    context.user_data["award_uid"] = uid
    await update.message.reply_text(
        f"{emoji('POINT')} How many points to award to user <b>{uid}</b>?\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return AWARD_AMOUNT

async def award_points_amount(update: Update, context: CallbackContext):
    try:
        amount = int(update.message.text)
        assert amount > 0
    except (ValueError, AssertionError):
        await update.message.reply_text(f"{emoji('CANCEL')} Send a positive number{emoji('TEETH')}:")
        return AWARD_AMOUNT
    uid = context.user_data["award_uid"]
    db.add_points(uid, amount, "admin_award")
    await check_and_award(context.bot, uid, "points")
    try:
        await context.bot.send_message(
            uid,
            f"{emoji('GIFT')} An admin awarded you <b>{amount} points</b>! {emoji('party')}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    await update.message.reply_text(
        f"{emoji('CHECK')} Awarded <b>{amount} pts</b> to user <b>{uid}</b>.",
        parse_mode=ParseMode.HTML,
    )
    context.user_data.clear()
    return ConversationHandler.END

# ── Admin — Set Rewards ───────────────────────────────────────────────────────
async def set_invite_points(update: Update, context: CallbackContext):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text(
            f"Current invite reward: <b>{get_invite_points()} pts</b>\nUsage: /setinvitepoints &lt;n&gt;",
            parse_mode=ParseMode.HTML,
        ); return
    try: pts = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid."); return
    db.set_setting("invite_points", str(pts))
    await update.message.reply_text(f"{emoji('CHECK')} Invite reward → <b>{pts} pts</b>", parse_mode=ParseMode.HTML)

async def set_suggestion_reward(update: Update, context: CallbackContext):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text(
            f"Current suggestion reward: <b>{get_suggestion_reward()} pts</b>\nUsage: /set_suggestion_reward &lt;n&gt;",
            parse_mode=ParseMode.HTML,
        ); return
    try: r = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid."); return
    db.set_setting("suggestion_reward", str(r))
    await update.message.reply_text(f"{emoji('CHECK')} Suggestion reward → <b>{r} pts</b>", parse_mode=ParseMode.HTML)

async def set_checkin_reward(update: Update, context: CallbackContext):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text(
            f"Current check-in reward: <b>{get_checkin_reward()} pts</b>\nUsage: /set_checkin_reward &lt;n&gt;",
            parse_mode=ParseMode.HTML,
        ); return
    try: r = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid."); return
    db.set_setting("checkin_reward", str(r))
    await update.message.reply_text(f"{emoji('CHECK')} Check-in reward → <b>{r} pts</b>", parse_mode=ParseMode.HTML)

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — Add Tool Conversation
# ═══════════════════════════════════════════════════════════════════════════════
_ADD_STEPS = 6

async def add_tool_start(update: Update, context: CallbackContext):
    if not is_admin(update):
        await update.message.reply_text(f"{emoji('CANCEL')} Admin only.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        step_header(1, _ADD_STEPS, "Tool Name") +
        "Send the <b>name</b> of the new tool.\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return ADD_TOOL_NAME

async def add_tool_name(update: Update, context: CallbackContext):
    context.user_data["tname"] = update.message.text.strip()
    await update.message.reply_text(
        step_header(2, _ADD_STEPS, "Description") +
        "Send a short <b>description</b>.\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return ADD_TOOL_DESC

async def add_tool_desc(update: Update, context: CallbackContext):
    context.user_data["tdesc"] = update.message.text.strip()
    await update.message.reply_text(
        step_header(3, _ADD_STEPS, "Category") +
        "Send a <b>category</b> (e.g. Python, AI, Productivity, just pick bro) or type <b>skip</b>:\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return ADD_TOOL_CAT

async def add_tool_cat(update: Update, context: CallbackContext):
    val = update.message.text.strip()
    context.user_data["tcat"] = "" if val.lower() == "skip" else val
    keyboard = InlineKeyboardMarkup([[
        icon_button("Stars Only",  callback_data="type_stars", emoji_key="STAR"),
        icon_button("Points Only", callback_data="type_points", emoji_key="POINT"),
        icon_button("⭐🏅 Both",      callback_data="type_both"),
    ], [cancel_btn()]])
    await update.message.reply_text(
        step_header(4, _ADD_STEPS, "Payment Method") +
        f"How can users unlock this tool?\n\n<b>Tip:</b> Points is better",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
    return ADD_TOOL_TYPE

async def add_tool_type(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    ptype = query.data.split("_")[1]
    context.user_data["ttype"] = ptype
    if ptype in ("stars", "both"):
        await query.edit_message_text(
            step_header(5, _ADD_STEPS, "Stars Price") +
            "Enter the <b>Stars</b> price (positive number):\n\n<i>/cancel to abort.</i>",
            parse_mode=ParseMode.HTML,
        )
        return ADD_TOOL_PRICE_STARS
    else:
        await query.edit_message_text(
            step_header(5, _ADD_STEPS, "Points Price") +
            "Enter the <b>Points</b> price (positive number):\n\n<i>/cancel to abort.</i>",
            parse_mode=ParseMode.HTML,
        )
        return ADD_TOOL_PRICE_POINTS

async def add_tool_price_stars(update: Update, context: CallbackContext):
    try:
        price = int(update.message.text); assert price > 0
    except (ValueError, AssertionError):
        await update.message.reply_text(f"{emoji('CANCEL')} Positive number please:")
        return ADD_TOOL_PRICE_STARS
    context.user_data["tprice_stars"] = price
    if context.user_data.get("ttype") == "both":
        await update.message.reply_text(
            step_header(5, _ADD_STEPS, "Points Price") +
            f"Stars → <b>{price}</b>. Now enter the <b>Points</b> price:\n\n<i>/cancel to abort.</i>",
            parse_mode=ParseMode.HTML,
        )
        return ADD_TOOL_PRICE_POINTS
    await update.message.reply_text(
        step_header(6, _ADD_STEPS, "Content") +
        "Send the <b>tool content</b> (link, text, instructions…):\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return ADD_TOOL_CONTENT

@force_join
async def add_tool_content_file(update: Update, context: CallbackContext):
    """Handle file submission when admin adds a tool."""
    d      = context.user_data
    stars_ = d.get("tprice_stars", 0)
    points = d.get("tprice_points", 0)

    # Determine file type and build content string
    # In add_tool_content_file and suggest_content_file
    if update.message.document:
        file_type = "document"
        file_id = update.message.document.file_id
        content = f"[DOCUMENT:{file_id}]"
    elif update.message.photo:
        file_type = "photo"
        file_id = update.message.photo[-1].file_id
        content = f"[PHOTO:{file_id}]"
    elif update.message.video:
        file_type = "video"
        file_id = update.message.video.file_id
        content = f"[VIDEO:{file_id}]"
    else:
        # unsupported
        return ADD_TOOL_CONTENT

    # Save full_content to DB

    caption = update.message.caption or ""
    full_content = f"{content}\n{caption}" if caption else content

    # Save tool
    db.add_tool(d["tname"], d["tdesc"], stars_, points, 0, "", full_content,
                category=d.get("tcat", ""))

    price_parts = ([f"{emoji('STAR')} {stars_}"] if stars_ else []) + \
                  ([f"{emoji('POINT')} {points}"] if points else [])
    await update.message.reply_text(
        f"{emoji('CHECK')} <b>Tool added!</b>\n\n"
        f"Name: <b>{escape_html(d['tname'])}</b>\n"
        f"Category: <b>{escape_html(d.get('tcat','') or 'General')}</b>\n"
        f"Price: {' | '.join(price_parts) or 'Free'}\n"
        f"Type: {file_type}",
        parse_mode=ParseMode.HTML,
    )
    context.user_data.clear()
    return ConversationHandler.END

async def add_tool_price_points(update: Update, context: CallbackContext):
    try:
        price = int(update.message.text); assert price > 0
    except (ValueError, AssertionError):
        await update.message.reply_text(f"{emoji('CANCEL')} Positive number please:")
        return ADD_TOOL_PRICE_POINTS
    context.user_data["tprice_points"] = price
    await update.message.reply_text(
        step_header(6, _ADD_STEPS, "Content") +
        "Send the <b>tool content</b> (link, text, instructions…):\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return ADD_TOOL_CONTENT

async def add_tool_content(update: Update, context: CallbackContext):
    d      = context.user_data
    stars_ = d.get("tprice_stars", 0)
    points = d.get("tprice_points", 0)
    db.add_tool(d["tname"], d["tdesc"], stars_, points, 0, "", update.message.text,
                category=d["tcat", ""])
    price_parts = ([f"{emoji('STAR')} {stars_}"] if stars_ else []) + ([f"{emoji('POINT')} {points}"] if points else [])
    await update.message.reply_text(
        f"{emoji('CHECK')} <b>Tool added!</b>\n\n"
        f"Name: <b>{escape_html(d['tname'])}</b>\n"
        f"Category: <b>{escape_html(d.get('tcat','') or 'General')}</b>\n"
        f"Price: {' | '.join(price_parts) or 'Free'}",
        parse_mode=ParseMode.HTML,
    )
    context.user_data.clear()
    return ConversationHandler.END

# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN — Edit Tool Conversation
# ═══════════════════════════════════════════════════════════════════════════════
async def edit_tool_start(update: Update, context: CallbackContext):
    if not is_admin(update):
        await update.message.reply_text(f"{emoji('CANCEL')} Admin only.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        f"{emoji('EDIT')} <b>Edit Tool</b>\n\nSend the <b>Tool ID</b>. Use /listtools to see IDs.\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return EDIT_TOOL_ID

async def edit_tool_id(update: Update, context: CallbackContext):
    try:
        tool_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid ID. Send a number:\n<i>/cancel to abort.</i>", parse_mode=ParseMode.HTML)
        return EDIT_TOOL_ID
    tool = db.get_tool(tool_id)
    if not tool:
        await update.message.reply_text(f"{emoji('CANCEL')} Tool #{tool_id} not found.\n<i>/cancel to abort.</i>", parse_mode=ParseMode.HTML)
        return EDIT_TOOL_ID
    context.user_data["edit_tool_id"] = tool_id
    keyboard = InlineKeyboardMarkup([
        [icon_button("Name",        callback_data="editf_name", emoji_key="name"),
         icon_button("Description", callback_data="editf_desc", emoji_key="LIST")],
        [icon_button("Category",   callback_data="editf_category", emoji_key="TAG"),
         icon_button("Content",     callback_data="editf_content", emoji_key="EDIT")],
        [icon_button("Stars Price",  callback_data="editf_stars", emoji_key="STAR"),
         icon_button("Points Price", callback_data="editf_points", emoji_key="POINT")],
        [cancel_btn()],
    ])
    await update.message.reply_text(
        f"{emoji('INFO')} <b>Tool #{tool_id} — {escape_html(tool['name'])}</b>\n"
        f"{emoji('STAR')} {tool['price_stars'] or 0}  {emoji('POINT')} {tool['price_points'] or 0}  {emoji('TAG')} {tool['category','General']}\n\n"
        f"Which field to edit?",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )
    return EDIT_TOOL_FIELD

async def edit_tool_field(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    field = query.data.split("_")[1]
    context.user_data["edit_field"] = field
    hints = {
        "name":     "Send the <b>new name</b>:",
        "desc":     "Send the <b>new description</b>:",
        "category": "Send the <b>new category</b> (or 'skip' to clear):",
        "stars":    "Send the <b>new Stars price</b> (0 to disable):",
        "points":   "Send the <b>new Points price</b> (0 to disable):",
        "content":  "Send the <b>new content</b>:",
    }
    await query.edit_message_text(
        f"{emoji('EDIT')} {hints.get(field, 'Send new value:')}\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return EDIT_TOOL_VALUE

async def edit_tool_value(update: Update, context: CallbackContext):
    tool_id = context.user_data["edit_tool_id"]
    field   = context.user_data["edit_field"]
    value   = update.message.text.strip()
    if field in ("stars", "points"):
        try:
            value = int(value); assert value >= 0
        except (ValueError, AssertionError):
            await update.message.reply_text(f"{emoji('CANCEL')} Non-negative number:\n<i>/cancel to abort.</i>", parse_mode=ParseMode.HTML)
            return EDIT_TOOL_VALUE
    elif field == "category" and value.lower() == "skip":
        value = ""
    db.update_tool_field(tool_id, field, value)
    await update.message.reply_text(
        f"{emoji('CHECK')} Tool <b>#{tool_id}</b> — <i>{field}</i> updated.", parse_mode=ParseMode.HTML
    )
    context.user_data.clear()
    return ConversationHandler.END

async def edit_cancel(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(f"{emoji('CANCEL')} Edit cancelled.", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

# ── Admin — List / Remove ─────────────────────────────────────────────────────
async def list_tools(update: Update, context: CallbackContext):
    if not is_admin(update): return
    tools_list = db.get_all_active_tools()
    if not tools_list:
        await update.message.reply_text(f"{emoji('pack')} No tools yet."); return
    lines = [f"{emoji('LIST')} <b>All Tools</b>\n"]
    for t in tools_list:
        prices = ([f"{t['price_stars']}⭐"] if t["price_stars"] else []) + \
                 ([f"{t['price_points']}🏅"] if t["price_points"] else [])
        cat  = t["category"] or "General"
        lines.append(f"<b>#{t['id']}</b>  [{cat}]  {escape_html(t['name'])}  —  {' | '.join(prices) or 'Free'}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def remove_tool(update: Update, context: CallbackContext):
    if not is_admin(update): return
    if not context.args:
        await update.message.reply_text(f"Usage: /removetool &lt;id&gt;", parse_mode=ParseMode.HTML); return
    try: tool_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(f"{emoji('CANCEL')} Invalid ID."); return
    tool = db.get_tool(tool_id)
    if not tool:
        await update.message.reply_text(f"{emoji('CANCEL')} Tool #{tool_id} not found."); return
    db.delete_tool(tool_id)
    await update.message.reply_text(
        f"{emoji('DELETE')} <b>{escape_html(tool['name'])}</b> removed.", parse_mode=ParseMode.HTML
    )

# ═══════════════════════════════════════════════════════════════════════════════
# USER — Suggest Tool Conversation
# ═══════════════════════════════════════════════════════════════════════════════
_SUGG_STEPS = 4
@force_join
async def suggest_start(update: Update, context: CallbackContext):
    context.user_data.clear()
    text = (
        step_header(1, _SUGG_STEPS, "Tool Name") +
        "What's the <b>name</b> of the tool you want to suggest?\n\n<i>/cancel to abort.</i>"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return SUGGEST_NAME

@force_join
async def suggest_name(update: Update, context: CallbackContext):
    context.user_data["sugg_name"] = update.message.text.strip()
    await update.message.reply_text(
        step_header(2, _SUGG_STEPS, "Description") +
        "Write a short <b>description</b> — what it does and why it's useful:\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return SUGGEST_DESC

async def suggest_desc(update: Update, context: CallbackContext):
    context.user_data["sugg_desc"] = update.message.text.strip()
    keyboard = InlineKeyboardMarkup([[
        icon_button("Stars",    callback_data="sugg_type_stars", emoji_key="STAR"),
        icon_button("Points",  callback_data="sugg_type_points", emoji_key="POINT"),
        icon_button("⭐🏅 Both",  callback_data="sugg_type_both"),
    ], [cancel_btn()]])
    await update.message.reply_text(
        step_header(3, _SUGG_STEPS, "Payment Type") + "What payment method do you suggest?",
        parse_mode=ParseMode.HTML, reply_markup=keyboard,
    )
    return SUGGEST_TYPE

async def suggest_choose_type(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    ptype = query.data.split("_")[2]
    context.user_data["sugg_ptype"] = ptype
    label = "Stars" if ptype in ("stars", "both") else "Points"
    await query.edit_message_text(
        step_header(4, _SUGG_STEPS, f"{label} Price") +
        f"Suggest a <b>{label}</b> price (positive number):\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return SUGGEST_ENTER_PRICE

async def suggest_enter_price(update: Update, context: CallbackContext):
    ptype = context.user_data.get("sugg_ptype", "stars")
    try:
        price = int(update.message.text); assert price > 0
    except (ValueError, AssertionError):
        await update.message.reply_text(f"{emoji('CANCEL')} Positive number please:\n<i>/cancel to abort.</i>", parse_mode=ParseMode.HTML)
        return SUGGEST_ENTER_PRICE
    if ptype in ("stars", "both"):
        context.user_data["sugg_price_stars"] = price
        if ptype == "both" and "sugg_price_points" not in context.user_data:
            context.user_data["sugg_ptype"] = "points"
            await update.message.reply_text(
                f"Stars → <b>{price}</b>. Now the <b>Points</b> price:\n\n<i>/cancel to abort.</i>",
                parse_mode=ParseMode.HTML,
            )
            return SUGGEST_ENTER_PRICE
    else:
        context.user_data["sugg_price_points"] = price
    await update.message.reply_text(
        step_header(_SUGG_STEPS, _SUGG_STEPS, "Content") +
        "Share the <b>tool content</b> or link:\n\n<i>/cancel to abort.</i>",
        parse_mode=ParseMode.HTML,
    )
    return SUGGEST_CONTENT

@force_join
async def suggest_content(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    name    = context.user_data.get("sugg_name", "")
    desc    = context.user_data.get("sugg_desc", "")
    stars_  = context.user_data.get("sugg_price_stars", 0)
    points  = context.user_data.get("sugg_price_points", 0)
    content = update.message.text.strip()
    db.save_suggestion(user_id, name, desc, stars_, points, 0, "", content)
    await update.message.reply_text(
        f"{emoji('CHECK')} <b>Suggestion submitted!</b>\n\n"
        f"Thanks {emoji('party')}  You'll earn <b>{get_suggestion_reward()} pts</b> if approved!",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[icon_button("Back to Catalog", callback_data="show_catalog", emoji_key="BACK")]]),
    )
    suggs   = db.get_pending_suggestions()
    sugg    = next((s for s in suggs if s["name"] == name and s["user_id"] == user_id), None)
    sugg_id = sugg["id"] if sugg else 0
    label   = f"@{update.effective_user.username}" if update.effective_user.username else str(user_id)
    await context.bot.send_message(
        ADMIN_ID,
        f"{emoji('bulb')} <b>New Tool Suggestion</b>\n\n"
        f"From: {escape_html(label)}\nName: {escape_html(name)}\nDesc: {escape_html(desc)}\n"
        f"Price: {emoji('STAR')}{stars_}  {emoji('POINT')}{points}\nContent: {escape_html(content[:120])}{'…' if len(content)>120 else ''}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            icon_button("Approve", callback_data=f"approvesugg_{sugg_id}", emoji_key="CHECK"),
            icon_button("Reject",  callback_data=f"rejectsugg_{sugg_id}", emoji_key="CANCEL"),
        ]]),
    )
    context.user_data.clear()
    return ConversationHandler.END

@force_join
async def suggest_content_file(update: Update, context: CallbackContext):
    """Handle file submissions for suggestions"""
    user_id = update.effective_user.id
    name = context.user_data.get("sugg_name", "")
    desc = context.user_data.get("sugg_desc", "")
    stars_ = context.user_data.get("sugg_price_stars", 0)
    points = context.user_data.get("sugg_price_points", 0)

    # Extract file details
    # In add_tool_content_file and suggest_content_file
    if update.message.document:
        file_type = "document"
        file_id = update.message.document.file_id
        content = f"[DOCUMENT:{file_id}]"
    elif update.message.photo:
        file_type = "photo"
        file_id = update.message.photo[-1].file_id
        content = f"[PHOTO:{file_id}]"
    elif update.message.video:
        file_type = "video"
        file_id = update.message.video.file_id
        content = f"[VIDEO:{file_id}]"
    else:
        await update.message.reply_text(
            f"{emoji('CANCEL')} Unsupported file type. Please send a photo, document or video.",
            parse_mode=ParseMode.HTML
        )
        # unsupported
        return SUGGEST_CONTENT

    caption = update.message.caption or ""
    full_content = f"{content}\n{caption}" if caption else content

    db.save_suggestion(user_id, name, desc, stars_, points, 0, "", full_content)

    await update.message.reply_text(
        f"{emoji('CHECK')} <b>Suggestion submitted!</b>\n\n"
        f"Type: {file_type}\n"
        f"Thanks {emoji('party')}  You'll earn <b>{get_suggestion_reward()} pts</b> if approved!",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [icon_button("Back to Catalog", emoji_key="BACK", callback_data="show_catalog")]
        ]),
    )

    # Notify admin (same as before)
    suggs = db.get_pending_suggestions()
    sugg = next((s for s in suggs if s["name"] == name and s["user_id"] == user_id), None)
    sugg_id = sugg["id"] if sugg else 0
    label = f"@{update.effective_user.username}" if update.effective_user.username else str(user_id)

    await context.bot.send_message(
        ADMIN_ID,
        f"{emoji('bulb')} <b>New Tool Suggestion</b>\n\n"
        f"From: {escape_html(label)}\n"
        f"Name: {escape_html(name)}\n"
        f"Desc: {escape_html(desc)}\n"
        f"Price: {emoji('STAR')}{stars_}  {emoji('POINT')}{points}\n"
        f"Content: {file_type.upper()} with caption: {escape_html(caption[:120])}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            icon_button("Approve", emoji_key="CHECK", callback_data=f"approvesugg_{sugg_id}"),
            icon_button("Reject", emoji_key="CANCEL", callback_data=f"rejectsugg_{sugg_id}"),
        ]]),
    )

    context.user_data.clear()
    return ConversationHandler.END
# ── Approve / Reject Suggestion ───────────────────────────────────────────────
async def approve_suggestion(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        await query.answer("Unauthorized.", show_alert=True); return
    sugg_id = int(query.data.split("_")[1])
    suggs   = db.get_pending_suggestions()
    sugg    = next((s for s in suggs if s["id"] == sugg_id), None)
    if not sugg:
        await query.edit_message_text(f"{emoji('CANCEL')} Already handled.", parse_mode=ParseMode.HTML); return
    db.add_tool(sugg["name"], sugg["description"],
                sugg.get("price_stars", 0), sugg.get("price_points", 0),
                0, "", sugg["content"])
    db.update_suggestion_status(sugg["id"], "approved")
    reward = get_suggestion_reward()
    db.add_points(sugg["user_id"], reward, "tool_suggestion")
    await check_and_award(context.bot, sugg["user_id"], "suggestion_approved")
    try:
        await context.bot.send_message(
            sugg["user_id"],
            f"{emoji('ROCKET')} <b>{escape_html(sugg['name'])}</b> was approved!\n"
            f"{emoji('POINT')} <b>+{reward} pts</b> — thank you! {emoji('party')}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[icon_button("💎 Browse Tools", callback_data="show_catalog")]]),
        )
    except Exception:
        pass
    await query.edit_message_text(
        f"{emoji('CHECK')} <b>{escape_html(sugg['name'])}</b> approved and added!", parse_mode=ParseMode.HTML
    )

async def reject_suggestion(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        await query.answer("Unauthorized.", show_alert=True); return
    sugg_id = int(query.data.split("_")[1])
    suggs   = db.get_pending_suggestions()
    sugg    = next((s for s in suggs if s["id"] == sugg_id), None)
    if sugg:
        db.update_suggestion_status(sugg["id"], "rejected")
        try:
            await context.bot.send_message(
                sugg["user_id"],
                f"{emoji('CANCEL')} <b>{escape_html(sugg['name'])}</b> wasn't approved.\n\nKeep contributing! {emoji('HEART')}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [icon_button("Suggest Another", callback_data="suggest_start", emoji_key="bulb")],
                    [icon_button("Browse Tools",    callback_data="show_catalog", emoji_key="TREASURE")],
                ]),
            )
        except Exception:
            pass
        await query.edit_message_text(
            f"{emoji('CANCEL')} <b>{escape_html(sugg['name'])}</b> rejected.", parse_mode=ParseMode.HTML
        )
    else:
        await query.edit_message_text(f"{emoji('CANCEL')} Not found.", parse_mode=ParseMode.HTML)

async def add_points_cmd(update: Update, context: CallbackContext):
    """Admin only: /add <user_id> <amount> - award points instantly."""
    if not is_admin(update):
        await update.message.reply_text(f"{emoji('CANCEL')} Admin only.")
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            f"{emoji('WARNING')} Usage: /add <user_id> <amount>\n\nExample: /add 123456789 100",
            parse_mode=ParseMode.HTML
        )
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            f"{emoji('CANCEL')} Invalid user ID or amount. Both must be positive numbers.",
            parse_mode=ParseMode.HTML
        )
        return

    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text(
            f"{emoji('CANCEL')} User {user_id} not found in database.",
            parse_mode=ParseMode.HTML
        )
        return

    # Award points
    db.add_points(user_id, amount, "admin_add")
    await check_and_award(context.bot, user_id, "points")

    # Notify user if possible
    try:
        await context.bot.send_message(
            user_id,
            f"{emoji('GIFT')} An admin added <b>{amount} points</b> to your balance! {emoji('party')}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"{emoji('CHECK')} Added <b>{amount} points</b> to user <b>{user_id}</b>.\n"
        f"New balance: <b>{user['points'] + amount}</b>",
        parse_mode=ParseMode.HTML
    )
# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # ── Conversations ─────────────────────────────────────────────────────────
    add_tool_conv = ConversationHandler(
        entry_points=[CommandHandler("addtool", add_tool_start)],
        states={
            ADD_TOOL_NAME:         [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tool_name)],
            ADD_TOOL_DESC:         [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tool_desc)],
            ADD_TOOL_CAT:          [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tool_cat)],
            ADD_TOOL_TYPE:         [CallbackQueryHandler(add_tool_type, pattern="^type_")],
            ADD_TOOL_PRICE_STARS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tool_price_stars)],
            ADD_TOOL_PRICE_POINTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tool_price_points)],
            ADD_TOOL_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_tool_content),
                MessageHandler(filters.PHOTO | filters.Document.ALL & ~filters.COMMAND | filters.VIDEO, add_tool_content_file),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_all),
                   CallbackQueryHandler(conv_cancel_callback, pattern="^conv_cancel$")],
        allow_reentry=True,
    )

    suggest_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(suggest_start, pattern="^suggest_start$"),
            CommandHandler("suggest", suggest_start),
        ],
        states={
            SUGGEST_NAME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, suggest_name)],
            SUGGEST_DESC:        [MessageHandler(filters.TEXT & ~filters.COMMAND, suggest_desc)],
            SUGGEST_TYPE:        [CallbackQueryHandler(suggest_choose_type, pattern="^sugg_type_")],
            SUGGEST_ENTER_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, suggest_enter_price)],
            SUGGEST_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, suggest_content),
                MessageHandler(filters.PHOTO | filters.Document.ALL & ~filters.COMMAND | filters.VIDEO, suggest_content_file),
			],
        },
        fallbacks=[CommandHandler("cancel", cancel_all),
                   CallbackQueryHandler(conv_cancel_callback, pattern="^conv_cancel$")],
        allow_reentry=True,
    )

    edit_tool_conv = ConversationHandler(
        entry_points=[CommandHandler("edittool", edit_tool_start)],
        states={
            EDIT_TOOL_ID:    [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_tool_id)],
            EDIT_TOOL_FIELD: [CallbackQueryHandler(edit_tool_field, pattern="^editf_(?!cancel$)")],
            EDIT_TOOL_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_tool_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel_all),
                   CallbackQueryHandler(edit_cancel,          pattern="^editf_cancel$"),
                   CallbackQueryHandler(conv_cancel_callback, pattern="^conv_cancel$")],
        allow_reentry=True,
    )

    broadcast_conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel_all)],
        allow_reentry=True,
    )

    search_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(search_start, pattern="^search_start$"),
            CommandHandler("search", search_start),
        ],
        states={
            SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_query)],
        },
        fallbacks=[CommandHandler("cancel", cancel_all)],
        allow_reentry=True,
    )

    review_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(review_start, pattern="^review_")],
        states={
            REVIEW_RATING: [CallbackQueryHandler(review_rating, pattern="^rate_")],
            REVIEW_TEXT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, review_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel_all),
                   CallbackQueryHandler(conv_cancel_callback, pattern="^conv_cancel$")],
        allow_reentry=True,
    )

    award_conv = ConversationHandler(
        entry_points=[CommandHandler("awardpoints", award_points_start)],
        states={
            AWARD_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, award_points_user)],
            AWARD_AMOUNT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, award_points_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel_all)],
        allow_reentry=True,
    )

    # ── Commands ──────────────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start",                 start))
    app.add_handler(CommandHandler("help",                  help_command))
    app.add_handler(CommandHandler("tools",                 tools))
    app.add_handler(CommandHandler("points",                points_command))
    app.add_handler(CommandHandler("add", add_points_cmd))
    app.add_handler(CommandHandler("my_purchases",          my_purchases))
    app.add_handler(CommandHandler("favorites",             show_favorites))
    app.add_handler(CommandHandler("checkin",               daily_checkin))
    app.add_handler(CommandHandler("leaderboard",           show_leaderboard))
    app.add_handler(CommandHandler("achievements",          show_achievements))
    app.add_handler(CommandHandler("listtools",             list_tools))
    app.add_handler(CommandHandler("removetool",            remove_tool))
    app.add_handler(CommandHandler("stats",                 admin_stats))
    app.add_handler(CommandHandler("userinfo",              user_info))
    app.add_handler(CommandHandler("banuser",               ban_user))
    app.add_handler(CommandHandler("unbanuser",             unban_user))
    app.add_handler(CommandHandler("setinvitepoints",       set_invite_points))
    app.add_handler(CommandHandler("set_suggestion_reward", set_suggestion_reward))
    app.add_handler(CommandHandler("set_checkin_reward",    set_checkin_reward))
    app.add_handler(InlineQueryHandler(inline_query))

    # ── Conversations ─────────────────────────────────────────────────────────
    app.add_handler(add_tool_conv)
    app.add_handler(suggest_conv)
    app.add_handler(edit_tool_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(search_conv)
    app.add_handler(review_conv)
    app.add_handler(award_conv)

    # ── Callbacks (most specific first) ──────────────────────────────────────
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(approve_suggestion,  pattern="^approvesugg_"))
    app.add_handler(CallbackQueryHandler(reject_suggestion,   pattern="^rejectsugg_"))
    app.add_handler(CallbackQueryHandler(admin_ban_callback,  pattern="^admin_(ban|unban)_"))
    app.add_handler(CallbackQueryHandler(tool_detail,         pattern="^tool_"))
    app.add_handler(CallbackQueryHandler(toggle_favorite,     pattern="^fav_"))
    app.add_handler(CallbackQueryHandler(buy_stars,           pattern="^buystars_"))
    app.add_handler(CallbackQueryHandler(buy_points_handler,  pattern="^buypoints_"))
    app.add_handler(CallbackQueryHandler(show_catalog, pattern="^catalog_page_"))
    app.add_handler(CallbackQueryHandler(show_category, pattern="^cat_.*_page_"))
    app.add_handler(CallbackQueryHandler(show_catalog,        pattern="^show_catalog$"))
    app.add_handler(CallbackQueryHandler(show_info,           pattern="^show_info$"))
    app.add_handler(CallbackQueryHandler(show_points,         pattern="^show_points$"))
    app.add_handler(CallbackQueryHandler(show_purchases,      pattern="^show_purchases$"))
    app.add_handler(CallbackQueryHandler(show_favorites,      pattern="^show_favorites$"))
    app.add_handler(CallbackQueryHandler(show_leaderboard,    pattern="^show_leaderboard$"))
    app.add_handler(CallbackQueryHandler(show_achievements,   pattern="^show_achievements$"))
    app.add_handler(CallbackQueryHandler(show_categories,     pattern="^show_categories$"))
    app.add_handler(CallbackQueryHandler(show_category,       pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(daily_checkin,       pattern="^daily_checkin$"))

    # ── Payments ──────────────────────────────────────────────────────────────
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    logger.info("🤖 Bot starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
