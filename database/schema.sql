CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    is_admin INTEGER NOT NULL DEFAULT 0,
    password_hash TEXT NOT NULL,
    rating INTEGER NOT NULL DEFAULT 1000,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    draws INTEGER NOT NULL DEFAULT 0,
    games_played INTEGER NOT NULL DEFAULT 0,
    wins_vs_ai INTEGER NOT NULL DEFAULT 0,
    wins_vs_room INTEGER NOT NULL DEFAULT 0,
    wins_ranked INTEGER NOT NULL DEFAULT 0,
    rank_points INTEGER NOT NULL DEFAULT 0,
    rank_tier TEXT NOT NULL DEFAULT 'Bronze',
    rank_stars INTEGER NOT NULL DEFAULT 0,
    rank_streak INTEGER NOT NULL DEFAULT 0,
    games_vs_ai INTEGER NOT NULL DEFAULT 0,
    games_vs_room INTEGER NOT NULL DEFAULT 0,
    games_ranked INTEGER NOT NULL DEFAULT 0,
    avatar TEXT NOT NULL DEFAULT '🙂',
    selected_title_code TEXT NOT NULL DEFAULT '',
    selected_frame_code TEXT NOT NULL DEFAULT '',
    last_mail_award_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    ai_level TEXT NOT NULL DEFAULT 'medium',
    board_size INTEGER NOT NULL,
    win_length INTEGER NOT NULL,
    players_count INTEGER NOT NULL,
    players_json TEXT NOT NULL,
    board_json TEXT NOT NULL,
    current_player INTEGER NOT NULL,
    status TEXT NOT NULL,
    winner INTEGER,
    match_type TEXT NOT NULL DEFAULT 'casual',
    created_by_user_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER NOT NULL,
    turn INTEGER NOT NULL,
    player INTEGER NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    shape TEXT NOT NULL,
    color TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES matches(id)
);

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
);

CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    owner_user_id INTEGER NOT NULL,
    match_id INTEGER,
    max_players INTEGER NOT NULL,
    room_type TEXT NOT NULL DEFAULT 'casual',
    status TEXT NOT NULL DEFAULT 'waiting',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_user_id) REFERENCES users(id),
    FOREIGN KEY (match_id) REFERENCES matches(id)
);

CREATE TABLE IF NOT EXISTS room_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    player_index INTEGER NOT NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(room_id, user_id),
    UNIQUE(room_id, player_index),
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS room_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS room_mutes (
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    muted_by_user_id INTEGER NOT NULL,
    muted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (room_id, user_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (muted_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS room_cohosts (
    room_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    granted_by_user_id INTEGER NOT NULL,
    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (room_id, user_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (granted_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS ai_move_heatmap (
    board_size INTEGER NOT NULL,
    row INTEGER NOT NULL,
    col INTEGER NOT NULL,
    picks INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (board_size, row, col)
);

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
);

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
);

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
);
