import json
import math
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from werkzeug.security import generate_password_hash

from config.settings import (
    ELO_ESTABLISHED_GAMES,
    ELO_K_ESTABLISHED,
    ELO_K_NEW,
    ELO_K_VETERAN,
    ELO_NEW_PLAYER_GAMES,
)
from config.settings import DB_PATH, SCHEMA_PATH


RANK_TIERS: list[tuple[str, int]] = [
    ("Bronze", 25),
    ("Silver", 25),
    ("Platinum", 25),
    ("Diamond", 25),
    ("Master", 25),
]
_TIER_INDEX = {name: idx for idx, (name, _stars) in enumerate(RANK_TIERS)}
_ROMAN_DIVISIONS = ["V", "IV", "III", "II", "I"]

RANK_META: Dict[str, Dict[str, str]] = {
    "Bronze": {
        "display": "Dong",
        "title": "Chien Binh Tap Su",
        "frame": "Khung nau dat, tho rap nhu kim loai gi set",
        "image": "/assets/images/ranks/bronze.png",
    },
    "Silver": {
        "display": "Bac",
        "title": "Chien Binh Kien Cuong",
        "frame": "Khung bac sang, gon gang, phong cach binh si",
        "image": "/assets/images/ranks/silver.png",
    },
    "Platinum": {
        "display": "Bach Kim",
        "title": "Hiep Si Tinh Anh",
        "frame": "Khung trang anh kim, hoa van tinh xao",
        "image": "/assets/images/ranks/platinum.png",
    },
    "Diamond": {
        "display": "Kim Cuong",
        "title": "Thu Linh Bat Khuat",
        "frame": "Khung xanh lam trong, diem kim cuong",
        "image": "/assets/images/ranks/diamond.png",
    },
    "Master": {
        "display": "Cao Thu",
        "title": "Bac Thay Chien Tran",
        "frame": "Khung vang rong uon, lua xanh",
        "image": "/assets/images/ranks/master.png",
    },
    "Challenger": {
        "display": "Thach Dau",
        "title": "Chien Than Thach Dau",
        "frame": "Khung do ruc, lua bung chay",
        "image": "/assets/images/ranks/challenger.png",
    },
    "King": {
        "display": "King",
        "title": "Vua Bat Diet",
        "frame": "Khung vang kham ngoc, hoa tiet hoang gia",
        "image": "/assets/images/ranks/king.png",
    },
}

_SQLITE_INT_MAX = 9_223_372_036_854_775_807
_BUILTIN_ADMIN_USERNAME = "ADMIN"
_BUILTIN_ADMIN_PASSWORD = "123456"
_BUILTIN_ADMIN_RANK_STARS = 999_999_999_999_999_999


def _safe_sqlite_int(value: int) -> int:
    return max(-_SQLITE_INT_MAX, min(_SQLITE_INT_MAX, int(value)))


def _normalized_username(value: str) -> str:
    return str(value or "").strip().upper()


def is_reserved_username(username: str) -> bool:
    return _normalized_username(username) == _BUILTIN_ADMIN_USERNAME


def _tier_name(value: str) -> str:
    if value == "Gold":
        return "Platinum"
    if value in _TIER_INDEX:
        return value
    return "Bronze"


def _rank_cap_for_tier(tier: str) -> Optional[int]:
    normalized_tier = _tier_name(tier)
    if normalized_tier == "Master":
        return None
    tier_index = _TIER_INDEX.get(normalized_tier, 0)
    return max(0, int(RANK_TIERS[tier_index][1]) - 1)


def normalize_rank_state(tier: str, stars: int, streak: int = 0) -> tuple[str, int, int]:
    normalized_tier = _tier_name(str(tier or "Bronze"))
    cap = _rank_cap_for_tier(normalized_tier)
    raw_stars = int(stars)
    if cap is None:
        normalized_stars = max(0, raw_stars)
    else:
        normalized_stars = max(0, min(cap, raw_stars))
    normalized_streak = max(0, int(streak))
    return normalized_tier, normalized_stars, normalized_streak


def _rank_sort_value(tier: str, stars: int, streak: int) -> int:
    normalized_tier, normalized_stars, normalized_streak = normalize_rank_state(tier, stars, streak)
    idx = _TIER_INDEX.get(normalized_tier, 0)
    return _safe_sqlite_int(idx * 1000 + normalized_stars * 10 + normalized_streak)


def _rank_division(stars: int, tier: str = "Bronze") -> tuple[str, int]:
    cap = _rank_cap_for_tier(tier)
    normalized = max(0, int(stars)) if cap is None else max(0, min(cap, int(stars)))

    # Highest tier keeps growing stars at division I (no 5-star cap).
    if cap is None:
        if normalized < 20:
            block = normalized // 5
            division = _ROMAN_DIVISIONS[block]
            return division, normalized % 5
        return "I", normalized - 20

    block = min(len(_ROMAN_DIVISIONS) - 1, normalized // 5)
    division = _ROMAN_DIVISIONS[block]
    return division, normalized % 5


def rank_badge_info(tier: str, stars: int, rank_position: Optional[int] = None) -> Dict[str, Any]:
    normalized_tier, normalized_stars, _normalized_streak = normalize_rank_state(tier, stars, 0)
    badge_key = normalized_tier
    if rank_position is not None and rank_position <= 10:
        badge_key = "King"
    elif rank_position is not None and rank_position <= 100:
        badge_key = "Challenger"

    info = RANK_META.get(badge_key, RANK_META["Bronze"])
    division, stars_in_division = _rank_division(normalized_stars, normalized_tier)
    return {
        "badgeCode": badge_key.lower(),
        "displayTier": info["display"],
        "rankTitle": info["title"],
        "frameDescription": info["frame"],
        "badgeImage": info["image"],
        "division": division,
        "starsInDivision": stars_in_division,
    }


def _title_from_item_code(item_code: str) -> str:
    code = str(item_code or "").strip().lower()
    if not code.startswith("title_"):
        return ""
    rank_code = code.replace("title_", "", 1)
    for tier_name, meta in RANK_META.items():
        if tier_name.lower() == rank_code:
            return str(meta.get("title") or "")
    return ""


def get_selected_title_name(user_id: int, selected_title_code: str = "") -> str:
    code = str(selected_title_code or "").strip()
    if not code:
        return ""

    conn = _connection()
    try:
        row = conn.execute(
            """
            SELECT item_name
            FROM user_inventory
            WHERE user_id = ? AND item_type = 'title' AND item_code = ?
            LIMIT 1
            """,
            (user_id, code),
        ).fetchone()
        if row and row["item_name"]:
            return str(row["item_name"])
        return _title_from_item_code(code)
    finally:
        conn.close()


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def _migrate_schema(conn: sqlite3.Connection) -> None:
    user_columns = _table_columns(conn, "users")
    if "is_admin" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
    if "password_hash" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "rating" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN rating INTEGER NOT NULL DEFAULT 1000")
    if "wins" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN wins INTEGER NOT NULL DEFAULT 0")
    if "losses" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN losses INTEGER NOT NULL DEFAULT 0")
    if "draws" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN draws INTEGER NOT NULL DEFAULT 0")
    if "games_played" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN games_played INTEGER NOT NULL DEFAULT 0")
    if "wins_vs_ai" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN wins_vs_ai INTEGER NOT NULL DEFAULT 0")
    if "wins_vs_room" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN wins_vs_room INTEGER NOT NULL DEFAULT 0")
    if "wins_ranked" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN wins_ranked INTEGER NOT NULL DEFAULT 0")
    if "rank_points" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN rank_points INTEGER NOT NULL DEFAULT 0")
    if "rank_tier" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN rank_tier TEXT NOT NULL DEFAULT 'Bronze'")
    if "rank_stars" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN rank_stars INTEGER NOT NULL DEFAULT 0")
    if "rank_streak" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN rank_streak INTEGER NOT NULL DEFAULT 0")
    if "games_vs_ai" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN games_vs_ai INTEGER NOT NULL DEFAULT 0")
    if "games_vs_room" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN games_vs_room INTEGER NOT NULL DEFAULT 0")
    if "games_ranked" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN games_ranked INTEGER NOT NULL DEFAULT 0")
    if "avatar" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN avatar TEXT NOT NULL DEFAULT '🙂'")
    if "selected_title_code" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN selected_title_code TEXT NOT NULL DEFAULT ''")
    if "selected_frame_code" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN selected_frame_code TEXT NOT NULL DEFAULT ''")
    if "last_mail_award_at" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN last_mail_award_at DATETIME")

    conn.execute("UPDATE users SET rank_tier = 'Platinum' WHERE rank_tier = 'Gold'")

    conn.execute(
        "UPDATE users SET password_hash = COALESCE(password_hash, 'temporary') WHERE password_hash IS NULL"
    )

    # Clean up legacy or corrupted rank data so stars cannot remain out of tier bounds.
    users = conn.execute("SELECT id, rank_tier, rank_stars, rank_streak FROM users").fetchall()
    for item in users:
        user_id = int(item["id"])
        tier, stars, streak = normalize_rank_state(
            str(item["rank_tier"]),
            int(item["rank_stars"]),
            int(item["rank_streak"]),
        )
        rank_points = _rank_sort_value(tier, stars, streak)
        conn.execute(
            """
            UPDATE users
            SET rank_tier = ?, rank_stars = ?, rank_streak = ?, rank_points = ?
            WHERE id = ?
            """,
            (tier, stars, streak, rank_points, user_id),
        )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_move_heatmap (
            board_size INTEGER NOT NULL,
            row INTEGER NOT NULL,
            col INTEGER NOT NULL,
            picks INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (board_size, row, col)
        )
        """
    )
    match_columns = _table_columns(conn, "matches")
    if "ai_level" not in match_columns:
        conn.execute("ALTER TABLE matches ADD COLUMN ai_level TEXT NOT NULL DEFAULT 'medium'")
    if "match_type" not in match_columns:
        conn.execute("ALTER TABLE matches ADD COLUMN match_type TEXT NOT NULL DEFAULT 'casual'")
    if "created_by_user_id" not in match_columns:
        conn.execute("ALTER TABLE matches ADD COLUMN created_by_user_id INTEGER")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS match_participants (
            match_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            player_index INTEGER NOT NULL,
            room_id INTEGER,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, user_id),
            FOREIGN KEY (match_id) REFERENCES matches(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
        """
    )

    room_columns = _table_columns(conn, "rooms")
    if "room_type" not in room_columns:
        conn.execute("ALTER TABLE rooms ADD COLUMN room_type TEXT NOT NULL DEFAULT 'casual'")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS room_cohosts (
            room_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            granted_by_user_id INTEGER NOT NULL,
            granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (room_id, user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (granted_by_user_id) REFERENCES users(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            title TEXT NOT NULL,
            progress INTEGER NOT NULL DEFAULT 0,
            target INTEGER NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, code),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_mailbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mail_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            item_code TEXT,
            item_name TEXT,
            item_type TEXT,
            item_payload_json TEXT,
            claimed INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            claimed_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_code TEXT NOT NULL,
            item_name TEXT NOT NULL,
            item_type TEXT NOT NULL,
            item_payload_json TEXT,
            equipped INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, item_code),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def init_db_if_missing() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _connection()
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
            conn.executescript(schema_file.read())
        _migrate_schema(conn)
        _ensure_builtin_admin_account(conn)  # Ensure the built-in admin account exists
        conn.commit()
    finally:
        conn.close()


def _ensure_builtin_admin_account(conn: sqlite3.Connection) -> None:
    password_hash = generate_password_hash(_BUILTIN_ADMIN_PASSWORD)
    row = conn.execute(
        "SELECT id FROM users WHERE UPPER(username) = ? LIMIT 1",
        (_BUILTIN_ADMIN_USERNAME,),
    ).fetchone()

    admin_id: int
    if row:
        admin_id = int(row["id"])
    else:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)",
            (_BUILTIN_ADMIN_USERNAME, password_hash),
        )
        admin_id = int(cursor.lastrowid)

    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, admin_id),
    )

    for tier_name, visual in RANK_META.items():
        badge_code = tier_name.lower()
        reward_items = [
            {
                "item_code": f"title_{badge_code}",
                "item_name": str(visual["title"]),
                "item_type": "title",
                "item_payload": {
                    "display": str(visual["title"]),
                    "tier": str(visual["display"]),
                    "image": str(visual["image"]),
                },
            },
            {
                "item_code": f"frame_{badge_code}",
                "item_name": str(visual["display"]),
                "item_type": "frame",
                "item_payload": {
                    "display": str(visual["frame"]),
                    "tier": str(visual["display"]),
                    "image": str(visual["image"]),
                },
            },
        ]

        for item in reward_items:
            conn.execute(
                """
                INSERT INTO user_inventory (user_id, item_code, item_name, item_type, item_payload_json, equipped)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, item_code)
                DO UPDATE SET
                    item_name = excluded.item_name,
                    item_type = excluded.item_type,
                    item_payload_json = excluded.item_payload_json
                """,
                (
                    admin_id,
                    item["item_code"],
                    item["item_name"],
                    item["item_type"],
                    json.dumps(item["item_payload"], ensure_ascii=True),
                    0,
                ),
            )

    conn.execute(
        "UPDATE user_inventory SET equipped = 0 WHERE user_id = ?",
        (admin_id,),
    )
    conn.execute(
        "UPDATE user_inventory SET equipped = 1 WHERE user_id = ? AND item_code IN ('title_king', 'frame_king')",
        (admin_id,),
    )

    rank_points = _rank_sort_value("Master", _BUILTIN_ADMIN_RANK_STARS, 999_999)
    conn.execute(
        """
        UPDATE users
        SET username = ?,
            is_admin = 1,
            rating = ?,
            wins = ?,
            losses = 0,
            draws = ?,
            games_played = ?,
            wins_vs_ai = ?,
            wins_vs_room = ?,
            wins_ranked = ?,
            rank_points = ?,
            rank_tier = 'Master',
            rank_stars = ?,
            rank_streak = ?,
            games_vs_ai = ?,
            games_vs_room = ?,
            games_ranked = ?,
            selected_title_code = 'title_king',
            selected_frame_code = 'frame_king',
            avatar = 'A'
        WHERE id = ?
        """,
        (
            _BUILTIN_ADMIN_USERNAME,
            9_999_999,
            999_999,
            11_111,
            1_111_111,
            333_333,
            555_555,
            444_444,
            rank_points,
            _BUILTIN_ADMIN_RANK_STARS,
            999_999,
            333_333,
            555_555,
            444_444,
            admin_id,
        ),
    )


def create_user(username: str, password_hash: str) -> Optional[int]:
    normalized_username = str(username or "").strip()
    if not normalized_username or is_reserved_username(normalized_username):
        return None

    conn = _connection()
    try:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (normalized_username, password_hash),
            )
            conn.commit()
            return int(cursor.lastrowid)
        except sqlite3.IntegrityError:
            return None
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    normalized_username = str(username or "").strip()
    if not normalized_username:
        return None

    conn = _connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (normalized_username,)).fetchone()
        if not row and is_reserved_username(normalized_username):
            row = conn.execute(
                "SELECT * FROM users WHERE UPPER(username) = ?",
                (_BUILTIN_ADMIN_USERNAME,),
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    conn = _connection()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def normalize_user_rank(user_id: int) -> None:
    conn = _connection()
    try:
        row = conn.execute(
            "SELECT rank_tier, rank_stars, rank_streak, rank_points FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return

        tier, stars, streak = normalize_rank_state(
            str(row["rank_tier"]),
            int(row["rank_stars"]),
            int(row["rank_streak"]),
        )
        rank_points = _rank_sort_value(tier, stars, streak)

        if (
            tier != str(row["rank_tier"])
            or stars != int(row["rank_stars"])
            or streak != int(row["rank_streak"])
            or rank_points != int(row["rank_points"])
        ):
            conn.execute(
                """
                UPDATE users
                SET rank_tier = ?, rank_stars = ?, rank_streak = ?, rank_points = ?
                WHERE id = ?
                """,
                (tier, stars, streak, rank_points, user_id),
            )
            conn.commit()
    finally:
        conn.close()


def update_user_avatar(user_id: int, avatar: str) -> None:
    conn = _connection()
    try:
        conn.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar, user_id))
        conn.commit()
    finally:
        conn.close()


def update_username(user_id: int, username: str) -> str:
    normalized_username = str(username or "").strip()
    if not normalized_username:
        return "invalid"

    conn = _connection()
    try:
        row = conn.execute(
            "SELECT username FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return "not_found"

        current_username = str(row["username"])
        current_is_builtin_admin = is_reserved_username(current_username)

        if is_reserved_username(normalized_username):
            if not current_is_builtin_admin:
                return "reserved"
            normalized_username = _BUILTIN_ADMIN_USERNAME
        elif current_is_builtin_admin:
            return "reserved"

        try:
            cursor = conn.execute("UPDATE users SET username = ? WHERE id = ?", (normalized_username, user_id))
            conn.commit()
            if cursor.rowcount <= 0:
                return "not_found"
            return "updated"
        except sqlite3.IntegrityError:
            return "exists"
    finally:
        conn.close()


def get_public_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    conn = _connection()
    try:
        row = conn.execute(
            """
            SELECT id, username, rating, wins, losses, draws, games_played,
                     wins_vs_ai, wins_vs_room, wins_ranked, rank_points, rank_tier, rank_stars, rank_streak, avatar,
                     games_vs_ai, games_vs_room, games_ranked, selected_title_code, selected_frame_code
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_session(user_id: int, ttl_hours: int = 168) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
    conn = _connection()
    try:
        conn.execute(
            "INSERT INTO user_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires_at),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    conn = _connection()
    try:
        row = conn.execute(
            """
            SELECT u.*
            FROM user_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND (s.expires_at IS NULL OR s.expires_at > ?)
            """,
            (token, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_leaderboard(limit: int = 20, kind: str = "room") -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        if kind == "ai":
            order_by = "wins_vs_ai DESC, rating DESC, games_played DESC"
        elif kind == "rank":
            order_by = "rank_points DESC, rating DESC, games_played DESC"
        else:
            order_by = "wins_vs_room DESC, rating DESC, games_played DESC"

        rows = conn.execute(
            """
                 SELECT id, username, rating, wins, losses, draws, games_played, wins_vs_ai, wins_vs_room,
                     wins_ranked, rank_points, rank_tier, rank_stars, rank_streak, avatar,
                     games_vs_ai, games_vs_room, games_ranked
            FROM users
            ORDER BY """
            + order_by
            + """
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items = [dict(row) for row in rows]
        if kind == "rank":
            items.sort(
                key=lambda item: _rank_sort_value(
                    _tier_name(str(item.get("rank_tier", "Bronze"))),
                    int(item.get("rank_stars", 0)),
                    int(item.get("rank_streak", 0)),
                ),
                reverse=True,
            )
            for index, item in enumerate(items, start=1):
                visual = rank_badge_info(
                    str(item.get("rank_tier", "Bronze")),
                    int(item.get("rank_stars", 0)),
                    rank_position=index,
                )
                item.update(visual)
                item["rankPosition"] = index
            return items[:limit]
        for item in items:
            visual = rank_badge_info(
                str(item.get("rank_tier", "Bronze")),
                int(item.get("rank_stars", 0)),
                rank_position=None,
            )
            item.update(visual)
        return items
    finally:
        conn.close()


def _update_rank_progress(conn: sqlite3.Connection, user_id: int, won: bool, lost: bool, draw: bool) -> tuple[str, int, int]:
    row = conn.execute(
        "SELECT rank_tier, rank_stars, rank_streak FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return ("Bronze", 0, 0)

    tier, stars, streak = normalize_rank_state(
        str(row["rank_tier"]),
        int(row["rank_stars"]),
        int(row["rank_streak"]),
    )
    tier_index = _TIER_INDEX.get(tier, 0)
    tier_cap = _rank_cap_for_tier(tier)

    if won:
        streak += 1
        if tier_cap is None:
            stars += 1
        elif stars < tier_cap:
            stars += 1
        elif tier_index < len(RANK_TIERS) - 1 and streak >= 2:
            tier_index += 1
            stars = 0
            streak = 0
    elif lost:
        streak = 0
        if stars > 0:
            stars -= 1
        elif tier_index > 0:
            tier_index -= 1
            stars = int(RANK_TIERS[tier_index][1]) - 1
    elif draw:
        streak = 0

    next_tier = RANK_TIERS[tier_index][0]
    rank_points = _rank_sort_value(next_tier, stars, streak)

    conn.execute(
        """
        UPDATE users
        SET rank_tier = ?, rank_stars = ?, rank_streak = ?, rank_points = ?
        WHERE id = ?
        """,
        (next_tier, stars, streak, rank_points, user_id),
    )
    return next_tier, stars, streak


def update_rating_after_match(user_id: int, won: bool = False, lost: bool = False, draw: bool = False) -> None:
    conn = _connection()
    try:
        delta = 0
        if won:
            delta = 25
        elif lost:
            delta = -15
        elif draw:
            delta = 5

        conn.execute(
            """
            UPDATE users
            SET rating = MAX(100, rating + ?),
                wins = wins + ?,
                losses = losses + ?,
                draws = draws + ?,
                games_played = games_played + 1
            WHERE id = ?
            """,
            (delta, 1 if won else 0, 1 if lost else 0, 1 if draw else 0, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def _expected_score(player_rating: int, opponent_rating: float) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (opponent_rating - player_rating) / 400.0))


def _k_factor_for_games(games_played: int) -> int:
    if games_played < ELO_NEW_PLAYER_GAMES:
        return ELO_K_NEW
    if games_played < ELO_ESTABLISHED_GAMES:
        return ELO_K_ESTABLISHED
    return ELO_K_VETERAN


def apply_elo_results(
    room_players: List[Dict[str, Any]],
    winner_index: Optional[int],
    is_draw: bool,
    ranked: bool = False,
) -> None:
    if not room_players:
        return

    player_count = len(room_players)
    if player_count < 2:
        return

    conn = _connection()
    try:
        for player in room_players:
            current_rating = int(player["rating"])
            pid = int(player["player_index"])

            opponents = [int(other["rating"]) for other in room_players if int(other["player_index"]) != pid]
            avg_opponent = sum(opponents) / len(opponents)
            expected = _expected_score(current_rating, avg_opponent)
            k_factor = _k_factor_for_games(int(player.get("games_played", 0)))

            actual = 0.5 if is_draw else (1.0 if winner_index == pid else 0.0)
            delta = int(round(k_factor * (actual - expected)))
            new_rating = max(100, current_rating + delta)

            won = not is_draw and winner_index == pid
            lost = not is_draw and winner_index is not None and winner_index != pid

            conn.execute(
                """
                UPDATE users
                SET rating = ?,
                    wins = wins + ?,
                    losses = losses + ?,
                    draws = draws + ?,
                    wins_vs_room = wins_vs_room + ?,
                    wins_ranked = wins_ranked + ?,
                    games_vs_room = games_vs_room + 1,
                    games_ranked = games_ranked + ?,
                    games_played = games_played + 1
                WHERE id = ?
                """,
                (
                    new_rating,
                    1 if won else 0,
                    1 if lost else 0,
                    1 if is_draw else 0,
                    1 if won else 0,
                    1 if (won and ranked) else 0,
                    1 if ranked else 0,
                    int(player["user_id"]),
                ),
            )

            if ranked:
                _update_rank_progress(
                    conn,
                    int(player["user_id"]),
                    won=won,
                    lost=lost,
                    draw=is_draw,
                )

        conn.commit()
    finally:
        conn.close()


def apply_forfeit_loss(
    kicked_player: Dict[str, Any],
    opponents: List[Dict[str, Any]],
    ranked: bool = False,
) -> None:
    if not kicked_player or not opponents:
        return

    user_id = int(kicked_player["user_id"])
    current_rating = int(kicked_player.get("rating", 1000))
    games_played = int(kicked_player.get("games_played", 0))

    avg_opponent = sum(int(item.get("rating", 1000)) for item in opponents) / len(opponents)
    expected = _expected_score(current_rating, avg_opponent)
    k_factor = _k_factor_for_games(games_played)
    delta = int(round(k_factor * (0.0 - expected)))
    new_rating = max(100, current_rating + delta)

    conn = _connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET rating = ?,
                losses = losses + 1,
                games_vs_room = games_vs_room + 1,
                games_ranked = games_ranked + ?,
                games_played = games_played + 1
            WHERE id = ?
            """,
            (
                new_rating,
                1 if ranked else 0,
                user_id,
            ),
        )

        if ranked:
            _update_rank_progress(conn, user_id, won=False, lost=True, draw=False)

        conn.commit()
    finally:
        conn.close()


def create_match(
    mode: str,
    board_size: int,
    win_length: int,
    players_count: int,
    players: List[Dict[str, str]],
    board: List[List[int]],
    current_player: int,
    ai_level: str = "medium",
    match_type: str = "casual",
    created_by_user_id: Optional[int] = None,
) -> int:
    conn = _connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO matches (
                mode, ai_level, board_size, win_length, players_count, players_json,
                board_json, current_player, status, winner, match_type, created_by_user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'playing', NULL, ?, ?)
            """,
            (
                mode,
                ai_level,
                board_size,
                win_length,
                players_count,
                json.dumps(players),
                json.dumps(board),
                current_player,
                match_type,
                created_by_user_id,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_match(match_id: int) -> Optional[Dict[str, Any]]:
    conn = _connection()
    try:
        row = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def save_move(
    match_id: int,
    turn: int,
    player: int,
    row: int,
    col: int,
    shape: str,
    color: str,
) -> None:
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO moves (match_id, turn, player, row, col, shape, color)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (match_id, turn, player, row, col, shape, color),
        )
        conn.commit()
    finally:
        conn.close()


def count_moves(match_id: int) -> int:
    conn = _connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS move_count FROM moves WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        return int(row["move_count"])
    finally:
        conn.close()


def list_moves(match_id: int) -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        rows = conn.execute(
            "SELECT * FROM moves WHERE match_id = ? ORDER BY turn ASC, id ASC",
            (match_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def create_match_participants(match_id: int, participants: List[Dict[str, Any]]) -> None:
    if not participants:
        return

    conn = _connection()
    try:
        for item in participants:
            user_id = int(item.get("user_id", 0) or 0)
            player_index = int(item.get("player_index", 0) or 0)
            room_id = item.get("room_id")
            if user_id <= 0 or player_index <= 0:
                continue

            conn.execute(
                """
                INSERT INTO match_participants (match_id, user_id, player_index, room_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(match_id, user_id)
                DO UPDATE SET player_index = excluded.player_index, room_id = excluded.room_id
                """,
                (match_id, user_id, player_index, room_id),
            )
        conn.commit()
    finally:
        conn.close()


def list_user_match_history(user_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        rows = conn.execute(
            """
            SELECT
                m.id,
                m.mode,
                m.match_type,
                m.board_size,
                m.win_length,
                m.players_count,
                m.status,
                m.winner,
                m.created_at,
                m.updated_at,
                mp.player_index,
                r.code AS room_code,
                COUNT(mv.id) AS moves_count
            FROM match_participants mp
            JOIN matches m ON m.id = mp.match_id
            LEFT JOIN rooms r ON r.id = mp.room_id
            LEFT JOIN moves mv ON mv.match_id = m.id
            WHERE mp.user_id = ?
            GROUP BY m.id, mp.player_index, r.code
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

        items: list[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            match_id = int(item["id"])
            players = conn.execute(
                """
                SELECT mp.player_index, mp.user_id, u.username
                FROM match_participants mp
                JOIN users u ON u.id = mp.user_id
                WHERE mp.match_id = ?
                ORDER BY mp.player_index ASC
                """,
                (match_id,),
            ).fetchall()

            participants = [dict(player) for player in players]
            me_index = int(item.get("player_index") or 0)
            winner_index = item.get("winner")
            winner_user = next(
                (player for player in participants if int(player["player_index"]) == int(winner_index or 0)),
                None,
            )
            opponents = [
                {"userId": int(player["user_id"]), "username": str(player["username"])}
                for player in participants
                if int(player["player_index"]) != me_index
            ]
            me_won = winner_index is not None and int(winner_index) == me_index
            is_draw = str(item.get("status", "")) == "draw"

            items.append(
                {
                    "id": match_id,
                    "mode": item.get("mode"),
                    "matchType": item.get("match_type", "casual"),
                    "boardSize": int(item.get("board_size") or 0),
                    "winLength": int(item.get("win_length") or 0),
                    "playersCount": int(item.get("players_count") or 0),
                    "status": item.get("status"),
                    "winner": int(winner_index) if winner_index is not None else None,
                    "winnerUsername": str(winner_user["username"]) if winner_user else "",
                    "playerIndex": me_index,
                    "meWon": bool(me_won),
                    "isDraw": bool(is_draw),
                    "movesCount": int(item.get("moves_count") or 0),
                    "roomCode": str(item.get("room_code") or ""),
                    "createdAt": item.get("created_at"),
                    "updatedAt": item.get("updated_at"),
                    "opponents": opponents,
                }
            )

        return items
    finally:
        conn.close()


def get_match_replay(match_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    conn = _connection()
    try:
        participant = conn.execute(
            "SELECT player_index FROM match_participants WHERE match_id = ? AND user_id = ?",
            (match_id, user_id),
        ).fetchone()
        if not participant:
            return None

        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not match:
            return None

        participants = conn.execute(
            """
            SELECT mp.player_index, mp.user_id, u.username
            FROM match_participants mp
            JOIN users u ON u.id = mp.user_id
            WHERE mp.match_id = ?
            ORDER BY mp.player_index ASC
            """,
            (match_id,),
        ).fetchall()

        moves = conn.execute(
            "SELECT * FROM moves WHERE match_id = ? ORDER BY turn ASC, id ASC",
            (match_id,),
        ).fetchall()

        parsed_match = dict(match)
        return {
            "match": parsed_match,
            "participants": [dict(item) for item in participants],
            "moves": [dict(item) for item in moves],
            "viewerPlayerIndex": int(participant["player_index"]),
        }
    finally:
        conn.close()


def get_active_room_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    conn = _connection()
    try:
        row = conn.execute(
            """
            SELECT r.*
            FROM room_players rp
            JOIN rooms r ON r.id = rp.room_id
            WHERE rp.user_id = ? AND r.status = 'playing'
            ORDER BY r.id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_active_rooms(limit: int = 30) -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        rows = conn.execute(
            """
            SELECT r.id, r.code, r.status, r.room_type, r.max_players, r.match_id, r.created_at,
                   COUNT(rp.user_id) AS players_count
            FROM rooms r
            LEFT JOIN room_players rp ON rp.room_id = r.id
            WHERE r.status IN ('waiting', 'playing')
            GROUP BY r.id
            ORDER BY r.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_match(
    match_id: int,
    board: List[List[int]],
    current_player: int,
    status: str,
    winner: Optional[int],
) -> None:
    conn = _connection()
    try:
        conn.execute(
            """
            UPDATE matches
            SET board_json = ?, current_player = ?, status = ?, winner = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(board), current_player, status, winner, match_id),
        )
        conn.commit()
    finally:
        conn.close()


def create_room(code: str, owner_user_id: int, max_players: int, room_type: str = "casual") -> int:
    conn = _connection()
    try:
        cursor = conn.execute(
            "INSERT INTO rooms (code, owner_user_id, max_players, room_type) VALUES (?, ?, ?, ?)",
            (code, owner_user_id, max_players, room_type),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def get_room_by_code(code: str) -> Optional[Dict[str, Any]]:
    conn = _connection()
    try:
        row = conn.execute("SELECT * FROM rooms WHERE code = ?", (code,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def add_player_to_room(room_id: int, user_id: int) -> Optional[int]:
    conn = _connection()
    try:
        existing = conn.execute(
            "SELECT player_index FROM room_players WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        ).fetchone()
        if existing:
            return int(existing["player_index"])

        max_index_row = conn.execute(
            "SELECT COALESCE(MAX(player_index), 0) AS max_index FROM room_players WHERE room_id = ?",
            (room_id,),
        ).fetchone()
        player_index = int(max_index_row["max_index"]) + 1

        room = conn.execute("SELECT max_players FROM rooms WHERE id = ?", (room_id,)).fetchone()
        if not room or player_index > int(room["max_players"]):
            return None

        conn.execute(
            "INSERT INTO room_players (room_id, user_id, player_index) VALUES (?, ?, ?)",
            (room_id, user_id, player_index),
        )
        conn.commit()
        return player_index
    finally:
        conn.close()


def list_room_players(room_id: int) -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        rows = conn.execute(
            """
            SELECT
                rp.player_index,
                u.id AS user_id,
                u.username,
                u.rating,
                u.games_played,
                u.rank_tier,
                u.rank_stars,
                u.rank_streak,
                CASE WHEN rm.user_id IS NULL THEN 0 ELSE 1 END AS is_muted,
                CASE WHEN rc.user_id IS NULL THEN 0 ELSE 1 END AS is_co_host
            FROM room_players rp
            JOIN users u ON u.id = rp.user_id
            LEFT JOIN room_mutes rm ON rm.room_id = rp.room_id AND rm.user_id = rp.user_id
            LEFT JOIN room_cohosts rc ON rc.room_id = rp.room_id AND rc.user_id = rp.user_id
            WHERE rp.room_id = ?
            ORDER BY rp.player_index ASC
            """,
            (room_id,),
        ).fetchall()
        players: list[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            tier, stars, streak = normalize_rank_state(
                str(item.get("rank_tier", "Bronze")),
                int(item.get("rank_stars", 0)),
                int(item.get("rank_streak", 0)),
            )
            visual = rank_badge_info(tier, stars)
            item["rank_tier"] = tier
            item["rank_stars"] = stars
            item["rank_streak"] = streak
            item.update(visual)
            players.append(item)
        return players
    finally:
        conn.close()


def set_room_match(room_id: int, match_id: int) -> None:
    conn = _connection()
    try:
        conn.execute(
            "UPDATE rooms SET match_id = ?, status = 'playing' WHERE id = ?",
            (match_id, room_id),
        )
        conn.commit()
    finally:
        conn.close()


def transfer_room_owner(room_id: int, old_owner_user_id: int, new_owner_user_id: int) -> None:
    conn = _connection()
    try:
        conn.execute(
            "UPDATE rooms SET owner_user_id = ? WHERE id = ?",
            (new_owner_user_id, room_id),
        )

        # New owner should not stay flagged as co-host.
        conn.execute(
            "DELETE FROM room_cohosts WHERE room_id = ? AND user_id = ?",
            (room_id, new_owner_user_id),
        )

        # Previous owner remains as co-host for smooth handover.
        conn.execute(
            """
            INSERT INTO room_cohosts (room_id, user_id, granted_by_user_id)
            VALUES (?, ?, ?)
            ON CONFLICT(room_id, user_id)
            DO UPDATE SET granted_by_user_id = excluded.granted_by_user_id, granted_at = CURRENT_TIMESTAMP
            """,
            (room_id, old_owner_user_id, new_owner_user_id),
        )

        conn.commit()
    finally:
        conn.close()


def finish_room(room_id: int) -> None:
    conn = _connection()
    try:
        conn.execute("UPDATE rooms SET status = 'finished' WHERE id = ?", (room_id,))
        conn.commit()
    finally:
        conn.close()


def save_room_message(room_id: int, user_id: int, message: str) -> Dict[str, Any]:
    conn = _connection()
    try:
        cursor = conn.execute(
            "INSERT INTO room_messages (room_id, user_id, message) VALUES (?, ?, ?)",
            (room_id, user_id, message),
        )
        message_id = int(cursor.lastrowid)
        row = conn.execute(
            """
            SELECT rm.id, rm.room_id, rm.user_id, rm.message, rm.created_at, u.username
            FROM room_messages rm
            JOIN users u ON u.id = rm.user_id
            WHERE rm.id = ?
            """,
            (message_id,),
        ).fetchone()
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def list_room_messages(room_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        rows = conn.execute(
            """
            SELECT rm.id, rm.room_id, rm.user_id, rm.message, rm.created_at, u.username
            FROM room_messages rm
            JOIN users u ON u.id = rm.user_id
            WHERE rm.room_id = ?
            ORDER BY rm.id DESC
            LIMIT ?
            """,
            (room_id, limit),
        ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items
    finally:
        conn.close()


def remove_player_from_room(room_id: int, user_id: int) -> bool:
    conn = _connection()
    try:
        cursor = conn.execute(
            "DELETE FROM room_players WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        )
        conn.execute(
            "DELETE FROM room_mutes WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        )
        conn.execute(
            "DELETE FROM room_cohosts WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def set_room_cohost(room_id: int, user_id: int, granted_by_user_id: int, enabled: bool) -> None:
    conn = _connection()
    try:
        if enabled:
            conn.execute(
                """
                INSERT INTO room_cohosts (room_id, user_id, granted_by_user_id)
                VALUES (?, ?, ?)
                ON CONFLICT(room_id, user_id)
                DO UPDATE SET granted_by_user_id = excluded.granted_by_user_id, granted_at = CURRENT_TIMESTAMP
                """,
                (room_id, user_id, granted_by_user_id),
            )
        else:
            conn.execute(
                "DELETE FROM room_cohosts WHERE room_id = ? AND user_id = ?",
                (room_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def is_room_cohost(room_id: int, user_id: int) -> bool:
    conn = _connection()
    try:
        row = conn.execute(
            "SELECT 1 AS has_role FROM room_cohosts WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        ).fetchone()
        return bool(row)
    finally:
        conn.close()


def set_room_mute(room_id: int, user_id: int, muted_by_user_id: int, muted: bool) -> None:
    conn = _connection()
    try:
        if muted:
            conn.execute(
                """
                INSERT INTO room_mutes (room_id, user_id, muted_by_user_id)
                VALUES (?, ?, ?)
                ON CONFLICT(room_id, user_id)
                DO UPDATE SET muted_by_user_id = excluded.muted_by_user_id, muted_at = CURRENT_TIMESTAMP
                """,
                (room_id, user_id, muted_by_user_id),
            )
        else:
            conn.execute(
                "DELETE FROM room_mutes WHERE room_id = ? AND user_id = ?",
                (room_id, user_id),
            )
        conn.commit()
    finally:
        conn.close()


def is_user_muted_in_room(room_id: int, user_id: int) -> bool:
    conn = _connection()
    try:
        row = conn.execute(
            "SELECT 1 AS muted FROM room_mutes WHERE room_id = ? AND user_id = ?",
            (room_id, user_id),
        ).fetchone()
        return bool(row)
    finally:
        conn.close()


def get_app_setting(key: str, default_value: str = "") -> str:
    conn = _connection()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if not row:
            return default_value
        return str(row["value"] or default_value)
    finally:
        conn.close()


def set_app_setting(key: str, value: str) -> None:
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_custom_banned_words() -> List[str]:
    raw = get_app_setting("custom_banned_words", default_value="[]")
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
        return [str(item).strip().lower() for item in data if str(item).strip()]
    except json.JSONDecodeError:
        return []


def set_custom_banned_words(words: List[str]) -> List[str]:
    cleaned: List[str] = []
    seen: set[str] = set()
    for word in words:
        item = str(word).strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        cleaned.append(item)

    set_app_setting("custom_banned_words", json.dumps(cleaned, ensure_ascii=True))
    return cleaned


def record_ai_result(user_id: int, won: bool, draw: bool = False) -> None:
    conn = _connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET wins_vs_ai = wins_vs_ai + ?,
                wins = wins + ?,
                losses = losses + ?,
                draws = draws + ?,
                games_vs_ai = games_vs_ai + 1,
                games_played = games_played + 1
            WHERE id = ?
            """,
            (
                1 if won else 0,
                1 if won else 0,
                0 if (won or draw) else 1,
                1 if draw else 0,
                user_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_user_achievement(
    user_id: int,
    code: str,
    title: str,
    progress: int,
    target: int,
    level: int,
    completed: bool,
) -> None:
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO user_achievements (user_id, code, title, progress, target, level, completed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, code)
            DO UPDATE SET
                title = excluded.title,
                progress = excluded.progress,
                target = excluded.target,
                level = excluded.level,
                completed = excluded.completed,
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, code, title, progress, target, level, 1 if completed else 0),
        )
        conn.commit()
    finally:
        conn.close()


def list_user_achievements(user_id: int) -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        rows = conn.execute(
            """
            SELECT code, title, progress, target, level, completed, updated_at
            FROM user_achievements
            WHERE user_id = ?
            ORDER BY level ASC, code ASC
            """,
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _rank_position(conn: sqlite3.Connection, user_id: int) -> Optional[int]:
    rows = conn.execute(
        "SELECT id, rank_tier, rank_stars, rank_streak FROM users"
    ).fetchall()
    items = [dict(row) for row in rows]
    items.sort(
        key=lambda item: _rank_sort_value(
            _tier_name(str(item.get("rank_tier", "Bronze"))),
            int(item.get("rank_stars", 0)),
            int(item.get("rank_streak", 0)),
        ),
        reverse=True,
    )
    for index, item in enumerate(items, start=1):
        if int(item.get("id", 0)) == user_id:
            return index
    return None


def grant_weekly_rank_mail(user_id: int) -> None:
    conn = _connection()
    try:
        user = conn.execute(
            "SELECT rank_tier, rank_stars, last_mail_award_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            return

        last_award_raw = user["last_mail_award_at"]
        if last_award_raw:
            try:
                last_award = datetime.fromisoformat(str(last_award_raw))
                if datetime.now(timezone.utc) - last_award < timedelta(days=7):
                    return
            except ValueError:
                pass

        position = _rank_position(conn, user_id)
        visual = rank_badge_info(
            str(user["rank_tier"]),
            int(user["rank_stars"]),
            rank_position=position,
        )

        reward_items = [
            {
                "item_code": f"title_{visual['badgeCode']}",
                "item_name": visual["rankTitle"],
                "item_type": "title",
                "item_payload": {
                    "display": visual["rankTitle"],
                    "tier": visual["displayTier"],
                    "image": visual["badgeImage"],
                },
            },
            {
                "item_code": f"frame_{visual['badgeCode']}",
                "item_name": visual["displayTier"],
                "item_type": "frame",
                "item_payload": {
                    "display": visual["frameDescription"],
                    "tier": visual["displayTier"],
                    "image": visual["badgeImage"],
                },
            },
        ]

        for item in reward_items:
            conn.execute(
                """
                INSERT INTO user_mailbox (
                    user_id, mail_type, title, content,
                    item_code, item_name, item_type, item_payload_json
                )
                VALUES (?, 'weekly_rank', ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    f"Thuong rank tuan - {visual['displayTier']}",
                    "Danh hieu va khung cua ban da duoc gui vao thu. Vat pham la vinh vien.",
                    item["item_code"],
                    item["item_name"],
                    item["item_type"],
                    json.dumps(item["item_payload"]),
                ),
            )

        conn.execute(
            "UPDATE users SET last_mail_award_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_mailbox(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        rows = conn.execute(
            """
            SELECT id, mail_type, title, content, item_code, item_name, item_type,
                   item_payload_json, claimed, created_at, claimed_at
            FROM user_mailbox
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()

        items = []
        for row in rows:
            item = dict(row)
            payload = item.get("item_payload_json")
            item["item_payload"] = json.loads(payload) if payload else None
            items.append(item)
        return items
    finally:
        conn.close()


def claim_mail_item(user_id: int, mail_id: int) -> Optional[Dict[str, Any]]:
    conn = _connection()
    try:
        row = conn.execute(
            """
            SELECT id, item_code, item_name, item_type, item_payload_json, claimed
            FROM user_mailbox
            WHERE id = ? AND user_id = ?
            """,
            (mail_id, user_id),
        ).fetchone()
        if not row:
            return None

        item = dict(row)
        if int(item.get("claimed", 0)) == 1:
            return {"alreadyClaimed": True}

        item_code = str(item.get("item_code") or "")
        item_name = str(item.get("item_name") or "")
        item_type = str(item.get("item_type") or "")
        payload_json = str(item.get("item_payload_json") or "")

        if item_code and item_type:
            conn.execute(
                """
                INSERT INTO user_inventory (user_id, item_code, item_name, item_type, item_payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, item_code)
                DO NOTHING
                """,
                (user_id, item_code, item_name, item_type, payload_json),
            )

        conn.execute(
            "UPDATE user_mailbox SET claimed = 1, claimed_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            (mail_id, user_id),
        )
        conn.commit()
        return {"claimed": True, "itemCode": item_code}
    finally:
        conn.close()


def claim_all_mail_items(user_id: int) -> Dict[str, Any]:
    conn = _connection()
    claimed_count = 0
    try:
        rows = conn.execute(
            """
            SELECT id, item_code, item_name, item_type, item_payload_json
            FROM user_mailbox
            WHERE user_id = ? AND claimed = 0
            ORDER BY id ASC
            """,
            (user_id,),
        ).fetchall()

        for row in rows:
            item = dict(row)
            item_code = str(item.get("item_code") or "")
            item_name = str(item.get("item_name") or "")
            item_type = str(item.get("item_type") or "")
            payload_json = str(item.get("item_payload_json") or "")

            if item_code and item_type:
                conn.execute(
                    """
                    INSERT INTO user_inventory (user_id, item_code, item_name, item_type, item_payload_json)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, item_code)
                    DO NOTHING
                    """,
                    (user_id, item_code, item_name, item_type, payload_json),
                )

            conn.execute(
                "UPDATE user_mailbox SET claimed = 1, claimed_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (int(item["id"]), user_id),
            )
            claimed_count += 1

        conn.commit()
        return {"claimedCount": claimed_count}
    finally:
        conn.close()


def list_inventory(user_id: int) -> List[Dict[str, Any]]:
    conn = _connection()
    try:
        rows = conn.execute(
            """
            SELECT item_code, item_name, item_type, item_payload_json, equipped, created_at
            FROM user_inventory
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            payload = item.get("item_payload_json")
            item["item_payload"] = json.loads(payload) if payload else None
            items.append(item)
        return items
    finally:
        conn.close()


def equip_inventory_item(user_id: int, item_code: str) -> bool:
    conn = _connection()
    try:
        row = conn.execute(
            "SELECT item_type FROM user_inventory WHERE user_id = ? AND item_code = ?",
            (user_id, item_code),
        ).fetchone()
        if not row:
            return False

        item_type = str(row["item_type"])
        conn.execute(
            "UPDATE user_inventory SET equipped = 0 WHERE user_id = ? AND item_type = ?",
            (user_id, item_type),
        )
        conn.execute(
            "UPDATE user_inventory SET equipped = 1 WHERE user_id = ? AND item_code = ?",
            (user_id, item_code),
        )

        if item_type == "title":
            conn.execute("UPDATE users SET selected_title_code = ? WHERE id = ?", (item_code, user_id))
        elif item_type == "frame":
            conn.execute("UPDATE users SET selected_frame_code = ? WHERE id = ?", (item_code, user_id))

        conn.commit()
        return True
    finally:
        conn.close()


def learn_ai_human_move(board_size: int, row: int, col: int) -> None:
    conn = _connection()
    try:
        conn.execute(
            """
            INSERT INTO ai_move_heatmap (board_size, row, col, picks)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(board_size, row, col)
            DO UPDATE SET picks = picks + 1
            """,
            (board_size, row, col),
        )
        conn.commit()
    finally:
        conn.close()


def get_ai_heatmap(board_size: int) -> Dict[tuple[int, int], int]:
    conn = _connection()
    try:
        rows = conn.execute(
            "SELECT row, col, picks FROM ai_move_heatmap WHERE board_size = ?",
            (board_size,),
        ).fetchall()
        return {(int(item["row"]), int(item["col"])): int(item["picks"]) for item in rows}
    finally:
        conn.close()
