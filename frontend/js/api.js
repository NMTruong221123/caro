export const headers = {
    "Content-Type": "application/json",
};

export function authHeaders(token) {
    if (!token) {
        return headers;
    }
    return {
        ...headers,
        Authorization: `Bearer ${token}`,
    };
}

async function parseResponse(response) {
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.error || "Server error");
    }
    return data;
}

export async function startMatch(payload, token = "") {
    const response = await fetch("/api/game/start", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(payload),
    });

    return parseResponse(response);
}

export async function playMove(payload, token = "") {
    const response = await fetch("/api/game/move", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(payload),
    });

    return parseResponse(response);
}

export async function getMatchState(matchId) {
    const response = await fetch(`/api/game/state/${matchId}`);
    return parseResponse(response);
}

export async function registerUser(payload) {
    const response = await fetch("/api/user/register", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
    });
    return parseResponse(response);
}

export async function loginUser(payload) {
    const response = await fetch("/api/user/login", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
    });
    return parseResponse(response);
}

export async function getMe(token) {
    const response = await fetch("/api/user/me", {
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function getLeaderboard(limit = 10, kind = "room") {
    const response = await fetch(`/api/user/leaderboard?limit=${limit}&kind=${encodeURIComponent(kind)}`);
    return parseResponse(response);
}

export async function createOnlineRoom(token, payload) {
    const response = await fetch("/api/online/room/create", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(payload),
    });
    return parseResponse(response);
}

export async function joinOnlineRoom(token, payload) {
    const response = await fetch("/api/online/room/join", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify(payload),
    });
    return parseResponse(response);
}

export async function getActiveRoomSession(token) {
    const response = await fetch("/api/online/room/active", {
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function getAchievements(token) {
    const response = await fetch("/api/user/achievements", {
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function updateProfile(token, payload) {
    const response = await fetch("/api/user/profile", {
        method: "PATCH",
        headers: authHeaders(token),
        body: JSON.stringify(payload),
    });
    return parseResponse(response);
}

export async function getPublicProfile(userId, rankPos = null) {
    const query = rankPos ? `?rankPos=${encodeURIComponent(rankPos)}` : "";
    const response = await fetch(`/api/user/public/${encodeURIComponent(userId)}${query}`);
    return parseResponse(response);
}

export async function getMailbox(token) {
    const response = await fetch("/api/user/mailbox", {
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function claimMailboxItem(token, mailId) {
    const response = await fetch(`/api/user/mailbox/${encodeURIComponent(mailId)}/claim`, {
        method: "POST",
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function claimAllMailboxItems(token) {
    const response = await fetch("/api/user/mailbox/claim-all", {
        method: "POST",
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function getInventory(token) {
    const response = await fetch("/api/user/inventory", {
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function equipInventoryItem(token, itemCode) {
    const response = await fetch("/api/user/inventory/equip", {
        method: "POST",
        headers: authHeaders(token),
        body: JSON.stringify({ itemCode }),
    });
    return parseResponse(response);
}

export async function getRankCatalog() {
    const response = await fetch("/api/user/rank-catalog");
    return parseResponse(response);
}

export async function getMatchHistory(token, limit = 30) {
    const response = await fetch(`/api/user/matches?limit=${encodeURIComponent(limit)}`, {
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function getMatchReplay(token, matchId) {
    const response = await fetch(`/api/user/matches/${encodeURIComponent(matchId)}/replay`, {
        headers: authHeaders(token),
    });
    return parseResponse(response);
}

export async function getAdminSummary(adminToken = "", userToken = "") {
    const requestHeaders = {};
    if (adminToken) {
        requestHeaders["X-Admin-Token"] = String(adminToken);
    }
    if (userToken) {
        requestHeaders.Authorization = `Bearer ${userToken}`;
    }

    const response = await fetch("/api/admin/summary", {
        headers: requestHeaders,
    });
    return parseResponse(response);
}

export async function updateAdminChatFilter(adminToken = "", payload = {}, userToken = "") {
    const requestHeaders = {
        ...headers,
    };
    if (adminToken) {
        requestHeaders["X-Admin-Token"] = String(adminToken);
    }
    if (userToken) {
        requestHeaders.Authorization = `Bearer ${userToken}`;
    }

    const response = await fetch("/api/admin/chat-filter", {
        method: "PATCH",
        headers: requestHeaders,
        body: JSON.stringify(payload),
    });
    return parseResponse(response);
}


export async function getChatFilterSettings(token) {
    const response = await fetch("/api/user/chat-filter", {
        headers: authHeaders(token),
    });
    return parseResponse(response);
}


export async function updateChatFilterSettings(token, payload) {
    const response = await fetch("/api/user/chat-filter", {
        method: "PATCH",
        headers: authHeaders(token),
        body: JSON.stringify(payload),
    });
    return parseResponse(response);
}
