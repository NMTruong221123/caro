const SESSION_KEY = "caro_session";

function randomId(prefix = "guest") {
    return `${prefix}_${Math.random().toString(36).slice(2, 8)}`;
}

export function getSession() {
    try {
        const raw = localStorage.getItem(SESSION_KEY);
        if (!raw) {
            return null;
        }
        return JSON.parse(raw);
    } catch (_error) {
        return null;
    }
}

export function saveSession(session) {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession() {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem("caro_token");
}

export function isTokenInvalidError(error) {
    const message = String(error?.message || "").toLowerCase();
    return message.includes("token khong hop le") || message.includes("unauthorized") || message.includes("401");
}

export function handleTokenInvalidError(error) {
    if (!isTokenInvalidError(error)) {
        return false;
    }
    clearSession();
    window.location.href = "/?reason=session_expired";
    return true;
}

export function createGuestSession() {
    const guest = {
        id: randomId(),
        username: `Khach_${Math.random().toString(10).slice(2, 6)}`,
        wins: 0,
        losses: 0,
        draws: 0,
        gamesPlayed: 0,
        winsVsAi: 0,
        winsVsRoom: 0,
        winsRanked: 0,
        gamesVsAi: 0,
        gamesVsRoom: 0,
        gamesRanked: 0,
        rankTier: "Guest",
        rankStars: 0,
        rankStreak: 0,
        avatar: "🧑",
    };
    const session = {
        guest: true,
        token: "",
        user: guest,
    };
    saveSession(session);
    return session;
}

export function requireSession({ allowGuest = true } = {}) {
    const session = getSession();
    if (!session) {
        window.location.href = "/";
        return null;
    }
    if (!session.guest && !String(session.token || "").trim()) {
        clearSession();
        window.location.href = "/";
        return null;
    }
    if (!allowGuest && session.guest) {
        window.location.href = "/modes.html";
        return null;
    }
    return session;
}
