import sqlite3
from datetime import datetime, date, timedelta

class Database:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price_stars INTEGER,
                price_points INTEGER,
                price_bank REAL,
                bank_info TEXT,
                content TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                category TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                points INTEGER DEFAULT 0,
                referrer_id INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_checkin TEXT DEFAULT '',
                streak INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS bank_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tool_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                proof_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS points_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                price_stars INTEGER DEFAULT 0,
                price_points INTEGER DEFAULT 0,
                price_bank REAL DEFAULT 0,
                bank_info TEXT,
                content TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS user_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tool_id INTEGER NOT NULL,
                purchase_type TEXT NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, tool_id)
            );

            CREATE TABLE IF NOT EXISTS favorites (
                user_id INTEGER NOT NULL,
                tool_id INTEGER NOT NULL,
                PRIMARY KEY (user_id, tool_id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tool_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                review_text TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, tool_id)
            );

            CREATE TABLE IF NOT EXISTS achievements (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                PRIMARY KEY (user_id, key)
            );
        """)

    # ────────────────────── Tools ──────────────────────
    def add_tool(self, name, desc, price_stars, price_points, price_bank, bank_info, content, category=''):
        self.conn.execute(
            "INSERT INTO tools (name, description, price_stars, price_points, price_bank, bank_info, content, category) VALUES (?,?,?,?,?,?,?,?)",
            (name, desc, price_stars, price_points, price_bank, bank_info, content, category)
        )
        self.conn.commit()

    def get_all_active_tools(self, category=None):
        if category:
            return self.conn.execute("SELECT * FROM tools WHERE is_active=1 AND category=?", (category,)).fetchall()
        return self.conn.execute("SELECT * FROM tools WHERE is_active=1").fetchall()

    def get_tool(self, tool_id):
        return self.conn.execute("SELECT * FROM tools WHERE id=?", (tool_id,)).fetchone()

    def delete_tool(self, tool_id):
        self.conn.execute("DELETE FROM tools WHERE id=?", (tool_id,))
        self.conn.commit()

    def update_tool_field(self, tool_id: int, field: str, value):
        allowed = ['name', 'description', 'price_stars', 'price_points', 'price_bank', 'bank_info', 'content', 'category']
        if field not in allowed:
            return
        self.conn.execute(f"UPDATE tools SET {field}=? WHERE id=?", (value, tool_id))
        self.conn.commit()

    def set_tool_category(self, tool_id: int, category: str):
        self.conn.execute("UPDATE tools SET category=? WHERE id=?", (category, tool_id))
        self.conn.commit()

    def get_tools_by_category(self, category: str):
        return self.conn.execute("SELECT * FROM tools WHERE is_active=1 AND category=?", (category,)).fetchall()

    def get_all_categories(self):
        rows = self.conn.execute("SELECT DISTINCT category FROM tools WHERE is_active=1 AND category != ''").fetchall()
        return [row['category'] for row in rows]

    def count_tools_in_category(self, category: str):
        row = self.conn.execute("SELECT COUNT(*) FROM tools WHERE is_active=1 AND category=?", (category,)).fetchone()
        return row[0] if row else 0

    def search_tools(self, query: str):
        return self.conn.execute(
            "SELECT * FROM tools WHERE is_active=1 AND (name LIKE ? OR description LIKE ?)",
            (f"%{query}%", f"%{query}%")
        ).fetchall()

    # ────────────────────── Users & Points ──────────────────────
    def add_user_if_not_exists(self, user_id, username):
        self.conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?,?)",
            (user_id, username)
        )
        self.conn.commit()

    def get_user(self, user_id):
        return self.conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()

    def set_referrer(self, user_id, referrer_id):
        self.conn.execute("UPDATE users SET referrer_id=? WHERE user_id=?", (referrer_id, user_id))
        self.conn.commit()

    def add_points(self, user_id, amount, reason="manual"):
        self.conn.execute("UPDATE users SET points = points + ? WHERE user_id=?", (amount, user_id))
        self.conn.execute("INSERT INTO points_log (user_id, amount, reason) VALUES (?,?,?)",
                          (user_id, amount, reason))
        self.conn.commit()

    def deduct_points(self, user_id, amount):
        self.conn.execute("UPDATE users SET points = points - ? WHERE user_id=?", (amount, user_id))
        self.conn.commit()

    def user_has_referrer(self, user_id):
        row = self.conn.execute("SELECT referrer_id FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row and row['referrer_id'] is not None

    def count_referrals(self, user_id: int) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM users WHERE referrer_id=?", (user_id,)).fetchone()
        return row['cnt'] if row else 0

    def get_all_user_ids(self):
        rows = self.conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
        return [row['user_id'] for row in rows]

    # ────────────────────── Purchases ──────────────────────
    def record_purchase(self, user_id: int, tool_id: int, purchase_type: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO user_purchases (user_id, tool_id, purchase_type) VALUES (?, ?, ?)",
            (user_id, tool_id, purchase_type)
        )
        self.conn.commit()

    def user_has_purchased(self, user_id: int, tool_id: int) -> bool:
        cur = self.conn.execute("SELECT 1 FROM user_purchases WHERE user_id=? AND tool_id=?", (user_id, tool_id))
        return cur.fetchone() is not None

    def get_user_purchases(self, user_id: int):
        cur = self.conn.execute("SELECT tool_id, purchase_type FROM user_purchases WHERE user_id=?", (user_id,))
        return cur.fetchall()

    # ────────────────────── Bank Requests ──────────────────────
    def create_bank_request(self, user_id, tool_id, proof_message=None):
        cur = self.conn.execute(
            "INSERT INTO bank_requests (user_id, tool_id, proof_message) VALUES (?,?,?)",
            (user_id, tool_id, proof_message)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_bank_request(self, request_id):
        return self.conn.execute("SELECT * FROM bank_requests WHERE id=?", (request_id,)).fetchone()

    def update_bank_request(self, request_id, status):
        self.conn.execute("UPDATE bank_requests SET status=? WHERE id=?", (status, request_id))
        self.conn.commit()

    def get_pending_requests(self):
        return self.conn.execute("SELECT * FROM bank_requests WHERE status='pending'").fetchall()

    def get_user_bank_requests(self, user_id: int):
        cur = self.conn.execute("SELECT id, tool_id, status FROM bank_requests WHERE user_id=? ORDER BY id DESC", (user_id,))
        return cur.fetchall()

    # ────────────────────── Suggestions ──────────────────────
    def save_suggestion(self, user_id, name, desc, stars, points, bank, bank_info, content):
        self.conn.execute(
            "INSERT INTO suggestions (user_id, name, description, price_stars, price_points, price_bank, bank_info, content, status) VALUES (?,?,?,?,?,?,?,?,'pending')",
            (user_id, name, desc, stars, points, bank, bank_info, content)
        )
        self.conn.commit()

    def get_pending_suggestions(self):
        cur = self.conn.execute("SELECT id, user_id, name, description, price_stars, price_points, price_bank, bank_info, content FROM suggestions WHERE status='pending'")
        return [dict(row) for row in cur.fetchall()]

    def get_suggestion_by_id(self, sugg_id):
        return self.conn.execute("SELECT * FROM suggestions WHERE id=?", (sugg_id,)).fetchone()

    def update_suggestion_status(self, sugg_id, status):
        self.conn.execute("UPDATE suggestions SET status=? WHERE id=?", (status, sugg_id))
        self.conn.commit()

    # ────────────────────── Favorites ──────────────────────
    def add_favorite(self, user_id: int, tool_id: int):
        self.conn.execute("INSERT OR IGNORE INTO favorites (user_id, tool_id) VALUES (?, ?)", (user_id, tool_id))
        self.conn.commit()

    def remove_favorite(self, user_id: int, tool_id: int):
        self.conn.execute("DELETE FROM favorites WHERE user_id=? AND tool_id=?", (user_id, tool_id))
        self.conn.commit()

    def get_favorites(self, user_id: int):
        # Returns list of sqlite3.Row with 'tool_id' key
        cur = self.conn.execute("SELECT tool_id FROM favorites WHERE user_id=?", (user_id,))
        return cur.fetchall()

    def is_favorite(self, user_id: int, tool_id: int) -> bool:
        cur = self.conn.execute("SELECT 1 FROM favorites WHERE user_id=? AND tool_id=?", (user_id, tool_id))
        return cur.fetchone() is not None

    def toggle_favorite(self, user_id: int, tool_id: int) -> bool:
        if self.is_favorite(user_id, tool_id):
            self.remove_favorite(user_id, tool_id)
            return False
        else:
            self.add_favorite(user_id, tool_id)
            return True

    # ────────────────────── Reviews & Ratings ──────────────────────
    def add_review(self, user_id: int, tool_id: int, rating: int, review_text: str = ""):
        self.conn.execute(
            "INSERT OR REPLACE INTO reviews (user_id, tool_id, rating, review_text, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (user_id, tool_id, rating, review_text)
        )
        self.conn.commit()

    def get_reviews(self, tool_id: int, limit: int = 10):
        cur = self.conn.execute(
            "SELECT r.*, u.username FROM reviews r LEFT JOIN users u ON r.user_id = u.user_id WHERE r.tool_id=? ORDER BY r.created_at DESC LIMIT ?",
            (tool_id, limit)
        )
        return cur.fetchall()

    def get_tool_rating(self, tool_id: int) -> dict:
        cur = self.conn.execute("SELECT AVG(rating) as avg, COUNT(*) as count FROM reviews WHERE tool_id=?", (tool_id,))
        row = cur.fetchone()
        return {"average": round(row['avg'], 1) if row['avg'] else 0, "count": row['count'] or 0}

    # Aliases for bot compatibility
    def save_review(self, user_id: int, tool_id: int, rating: int, review_text: str = ""):
        return self.add_review(user_id, tool_id, rating, review_text)

    def get_tool_reviews(self, tool_id: int, limit: int = 10):
        return self.get_reviews(tool_id, limit)

    def get_avg_rating(self, tool_id: int):
        rating_info = self.get_tool_rating(tool_id)
        return rating_info['average']

    # ────────────────────── Daily Check‑in & Streak ──────────────────────
    def checkin(self, user_id: int) -> tuple:
        """Returns (points_earned, new_streak, message)."""
        user = self.get_user(user_id)
        today = date.today().isoformat()
        last = user['last_checkin'] or ''
        streak = user['streak'] or 0

        if last == today:
            return (0, streak, "You've already checked in today!")
        elif last == (date.today() - timedelta(days=1)).isoformat():
            streak += 1
        else:
            streak = 1

        points = 10 + min(streak, 40)
        self.add_points(user_id, points, f"daily_checkin_streak_{streak}")
        self.conn.execute("UPDATE users SET last_checkin=?, streak=? WHERE user_id=?", (today, streak, user_id))
        self.conn.commit()
        return (points, streak, f"Checked in! +{points} points (streak: {streak})")

    # Individual getters for bot's separate check‑in logic
    def get_last_checkin(self, user_id: int):
        user = self.get_user(user_id)
        return user['last_checkin'] if user else ''

    def get_streak(self, user_id: int):
        user = self.get_user(user_id)
        return user['streak'] if user else 0

    def update_checkin(self, user_id: int, date_str: str, new_streak: int):
        self.conn.execute("UPDATE users SET last_checkin=?, streak=? WHERE user_id=?",
                          (date_str, new_streak, user_id))
        self.conn.commit()

    # ────────────────────── Achievements ──────────────────────
    def award_achievement(self, user_id: int, key: str):
        self.conn.execute("INSERT OR IGNORE INTO achievements (user_id, key) VALUES (?, ?)", (user_id, key))
        self.conn.commit()

    def has_achievement(self, user_id: int, key: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM achievements WHERE user_id=? AND key=?", (user_id, key))
        return cur.fetchone() is not None

    def get_achievements(self, user_id: int):
        cur = self.conn.execute("SELECT key FROM achievements WHERE user_id=?", (user_id,))
        return [row['key'] for row in cur.fetchall()]

    def get_user_achievements(self, user_id):
        """Alias for get_achievements."""
        return self.get_achievements(user_id)

    # ────────────────────── User Banning ──────────────────────
    def ban_user(self, user_id: int):
        self.conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))
        self.conn.commit()

    def unban_user(self, user_id: int):
        self.conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))
        self.conn.commit()

    def is_banned(self, user_id: int) -> bool:
        row = self.conn.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row and row['is_banned'] == 1

    def set_banned(self, user_id: int, banned: bool):
        if banned:
            self.ban_user(user_id)
        else:
            self.unban_user(user_id)

    # ────────────────────── Settings ──────────────────────
    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row['value'] if row else default

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        self.conn.commit()

    # ────────────────────── Statistics ──────────────────────
    def get_stats(self):
        stats = {}
        stats['total_users'] = self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats['total_tools'] = self.conn.execute("SELECT COUNT(*) FROM tools WHERE is_active=1").fetchone()[0]
        stats['total_purchases'] = self.conn.execute("SELECT COUNT(*) FROM user_purchases").fetchone()[0]
        stats['pending_suggestions'] = self.conn.execute("SELECT COUNT(*) FROM suggestions WHERE status='pending'").fetchone()[0]
        stats['total_reviews'] = self.conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        stats['active_streaks'] = self.conn.execute("SELECT COUNT(*) FROM users WHERE streak>0").fetchone()[0]
        stats['total_points'] = self.conn.execute("SELECT SUM(points) FROM users").fetchone()[0] or 0
        return stats

    # ────────────────────── Leaderboard ──────────────────────
    def get_leaderboard(self, limit=10):
        return self.conn.execute(
            "SELECT user_id, username, points FROM users WHERE is_banned=0 ORDER BY points DESC LIMIT ?",
            (limit,)
        ).fetchall()
