import { createOnlineRoom, getActiveRoomSession, joinOnlineRoom } from "./api.js";
import { buildStatus, renderBoard, renderLegend } from "./ui.js";
import { getSession, requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: false });
if (!session) {
    throw new Error("Unauthorized");
}
initTopbar();

const token = session.token || "";
const currentUser = session.user || {};

const onlineMaxPlayers = document.getElementById("onlineMaxPlayers");
const createRoomBtn = document.getElementById("createRoomBtn");
const startOnlineBtn = document.getElementById("startOnlineBtn");
const roomCodeInput = document.getElementById("roomCodeInput");
const joinRoomBtn = document.getElementById("joinRoomBtn");
const roomInfo = document.getElementById("roomInfo");
const roomMembers = document.getElementById("roomMembers");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");
const board = document.getElementById("board");
const legend = document.getElementById("legend");
const status = document.getElementById("status");
const victoryModal = document.getElementById("victoryModal");
const victoryText = document.getElementById("victoryText");
const victoryBackBtn = document.getElementById("victoryBackBtn");
const victoryCloseBtn = document.getElementById("victoryCloseBtn");

let socket = null;
let room = null;
let state = null;
let announcedResultKey = "";

function canStartRoom() {
    if (!room || !currentUser) {
        return false;
    }
    return Number(room.ownerUserId) === Number(currentUser.id);
}

function updateStartButtonState() {
    if (!startOnlineBtn) {
        return;
    }
    const enabled = canStartRoom();
    startOnlineBtn.disabled = !enabled;
    startOnlineBtn.title = enabled ? "" : "Chi chu phong moi duoc bat dau";
}

function setRoomInfo(message, isError = false) {
    roomInfo.textContent = message;
    roomInfo.style.color = isError ? "#fecaca" : "#a7f3d0";
}

function setStatus(message, isError = false) {
    status.textContent = message;
    status.style.color = isError ? "#fecaca" : "#bae6fd";
}

function hideVictoryDialog() {
    victoryModal?.classList.add("hidden");
}

function maybeShowMatchResult(matchState) {
    if (!matchState || !["finished", "draw"].includes(String(matchState.status))) {
        return;
    }

    const resultKey = `${matchState.matchId || "na"}:${matchState.status}:${matchState.winner || 0}`;
    if (announcedResultKey === resultKey) {
        return;
    }
    announcedResultKey = resultKey;

    if (!victoryModal || !victoryText) {
        return;
    }

    if (String(matchState.status) === "draw") {
        victoryText.textContent = "Tran dau ket thuc voi ket qua hoa.";
    } else {
        const roomPlayers = matchState.roomPlayers || room?.players || [];
        const winnerInfo = roomPlayers.find((player) => Number(player.player_index) === Number(matchState.winner));
        const winnerName = String(winnerInfo?.username || `P${matchState.winner}`);
        victoryText.textContent = `Chuc mung nguoi choi ${winnerName} da thang!`;
    }

    victoryModal.classList.remove("hidden");
}

function ensureSocket() {
    if (socket?.connected) {
        return socket;
    }
    socket = window.io({ auth: { token }, transports: ["websocket", "polling"] });

    socket.on("connect", async () => {
        if (room?.code) {
            socket.emit("join_room", { code: room.code });
            return;
        }

        try {
            const active = await getActiveRoomSession(token);
            const sessionPayload = active?.session;
            if (!sessionPayload?.room?.code) {
                return;
            }
            room = sessionPayload.room;
            state = sessionPayload.state || null;
            announcedResultKey = "";
            hideVictoryDialog();
            roomCodeInput.value = room.code;
            setRoomInfo(`Da tu reconnect vao phong ${room.code}.`);
            updateStartButtonState();
            renderMembers();
            if (state) {
                renderLegend(legend, state.players || []);
                renderBoard(board, state, onCellClick);
                setStatus(buildStatus(state));
                maybeShowMatchResult(state);
            }
            socket.emit("join_room", { code: room.code });
        } catch (_error) {
            // No active room to recover.
        }
    });

    socket.on("room_error", (payload) => setRoomInfo(payload?.error || "Loi phong", true));
    socket.on("room_state", (payload) => {
        if (payload.room) {
            room = payload.room;
            roomCodeInput.value = room.code;
            setRoomInfo(`Phong ${room.code} (${room.players.length}/${room.maxPlayers})`);
            updateStartButtonState();
            renderMembers();
        }
        if (payload.state) {
            state = payload.state;
            if (!state.roomPlayers && room?.players) {
                state.roomPlayers = room.players;
            }
            renderLegend(legend, state.players);
            renderBoard(board, state, onCellClick);
            setStatus(buildStatus(state));
            maybeShowMatchResult(state);
        }
    });

    socket.on("room_chat_history", (payload) => {
        chatMessages.innerHTML = "";
        for (const item of payload?.messages || []) {
            appendMessage(item, true);
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });

    socket.on("room_chat_message", (payload) => appendMessage(payload));

    socket.on("room_kicked", (payload) => {
        const kickedCode = String(payload?.code || "").toUpperCase();
        if (room?.code && kickedCode === String(room.code).toUpperCase()) {
            room = null;
            state = null;
            announcedResultKey = "";
            hideVictoryDialog();
            roomMembers.innerHTML = "";
            board.innerHTML = "";
            legend.innerHTML = "";
            updateStartButtonState();
            setRoomInfo(payload?.message || "Ban da bi kick khoi phong", true);
            setStatus("Ban da bi kick khoi phong.", true);
        }
    });

    return socket;
}

function formatTimestamp(value) {
    if (!value) {
        return "";
    }
    const normalized = String(value).replace(" ", "T");
    const dt = new Date(normalized);
    if (Number.isNaN(dt.getTime())) {
        return "";
    }
    return dt.toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
    });
}

function playerRankText(player) {
    const displayTier = String(player?.displayTier || player?.rank_tier || "Bronze");
    const division = String(player?.division || "V");
    const starsInDivision = Number(player?.starsInDivision ?? 0) + 1;
    return `${displayTier} ${division}-${starsInDivision}*`;
}

function shouldStickToBottom() {
    const threshold = 18;
    const distance = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
    return distance <= threshold;
}

function appendMessage(item, forceScroll = false) {
    const stick = forceScroll || shouldStickToBottom();

    const div = document.createElement("div");
    div.className = Number(item?.userId || 0) === 0 || item?.system ? "chat-item chat-item-system" : "chat-item";

    const who = document.createElement("span");
    who.className = "who";
    who.textContent = `${item.username}:`;

    const msg = document.createElement("span");
    msg.textContent = ` ${item.message}`;

    const time = document.createElement("span");
    time.className = "time";
    time.textContent = formatTimestamp(item.createdAt || item.created_at);

    div.appendChild(who);
    div.appendChild(msg);
    div.appendChild(time);
    chatMessages.appendChild(div);
    if (stick) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function renderMembers() {
    roomMembers.innerHTML = "";
    if (!room?.players) {
        return;
    }
    const isOwner = Number(room.ownerUserId) === Number(currentUser.id);
    const me = room.players.find((p) => Number(p.user_id) === Number(currentUser.id));
    const canModerate = isOwner || Number(me?.is_co_host) === 1;

    room.players.forEach((player) => {
        const row = document.createElement("div");
        row.className = "room-member";
        const meta = document.createElement("div");
        meta.className = "meta";
        const ownerTag = Number(player.user_id) === Number(room.ownerUserId) ? " [Chu phong]" : "";
        const coHostTag = Number(player.is_co_host) === 1 ? " [Co-host]" : "";
        const muteTag = Number(player.is_muted) === 1 ? " [Muted]" : "";
        meta.textContent = `${player.username}${ownerTag}${coHostTag}${muteTag} | ${playerRankText(player)}`;
        row.appendChild(meta);

        if (canModerate && Number(player.user_id) !== Number(currentUser.id)) {
            const actions = document.createElement("div");
            actions.className = "member-actions";

            const muteBtn = document.createElement("button");
            muteBtn.type = "button";
            muteBtn.textContent = Number(player.is_muted) === 1 ? "Unmute" : "Mute";
            muteBtn.onclick = () => ensureSocket().emit("room_owner_mute", {
                code: room.code,
                targetUserId: Number(player.user_id),
                muted: Number(player.is_muted) !== 1,
            });

            const kickBtn = document.createElement("button");
            kickBtn.type = "button";
            kickBtn.textContent = "Kick";
            kickBtn.onclick = () => ensureSocket().emit("room_owner_kick", {
                code: room.code,
                targetUserId: Number(player.user_id),
            });

            actions.appendChild(muteBtn);
            actions.appendChild(kickBtn);

            if (isOwner && Number(player.user_id) !== Number(room.ownerUserId)) {
                const coHostBtn = document.createElement("button");
                coHostBtn.type = "button";
                const enabled = Number(player.is_co_host) === 1;
                coHostBtn.textContent = enabled ? "Bo co-host" : "Set co-host";
                coHostBtn.onclick = () => ensureSocket().emit("room_owner_set_cohost", {
                    code: room.code,
                    targetUserId: Number(player.user_id),
                    enabled: !enabled,
                });
                actions.appendChild(coHostBtn);

                if (enabled) {
                    const transferBtn = document.createElement("button");
                    transferBtn.type = "button";
                    transferBtn.textContent = "Chuyen chu phong";
                    transferBtn.onclick = () => ensureSocket().emit("room_owner_transfer", {
                        code: room.code,
                        targetUserId: Number(player.user_id),
                    });
                    actions.appendChild(transferBtn);
                }
            }

            row.appendChild(actions);
        }
        roomMembers.appendChild(row);
    });
}

async function onCreateRoom() {
    try {
        const data = await createOnlineRoom(token, { maxPlayers: Number(onlineMaxPlayers.value || 4) });
        room = data.room;
        announcedResultKey = "";
        hideVictoryDialog();
        roomCodeInput.value = room.code;
        updateStartButtonState();
        ensureSocket().emit("join_room", { code: room.code });
    } catch (error) {
        setRoomInfo(error.message || "Khong tao duoc phong", true);
    }
}

async function onJoinRoom() {
    const code = String(roomCodeInput.value || "").trim().toUpperCase();
    if (!code) {
        setRoomInfo("Nhap ma phong", true);
        return;
    }
    try {
        const data = await joinOnlineRoom(token, { code });
        room = data.room;
        announcedResultKey = "";
        hideVictoryDialog();
        updateStartButtonState();
        ensureSocket().emit("join_room", { code });
    } catch (error) {
        setRoomInfo(error.message || "Khong vao duoc phong", true);
    }
}

function onStartRoom() {
    if (!room) {
        setRoomInfo("Can tao hoac vao phong truoc.", true);
        return;
    }

    if (!canStartRoom()) {
        setRoomInfo("Chi chu phong moi duoc bat dau tran.", true);
        return;
    }

    if ((room.players || []).length < 2) {
        setRoomInfo("Can it nhat 2 nguoi trong phong de bat dau.", true);
        return;
    }

    ensureSocket().emit("start_room_game", {
        code: room.code,
        boardSize: 15,
        winLength: 5,
    });
}

function onSendChat() {
    const message = String(chatInput.value || "").trim();
    if (!message || !room) {
        return;
    }
    ensureSocket().emit("room_chat", { code: room.code, message });
    chatInput.value = "";
}

function onCellClick(row, col) {
    if (!room || !state || state.status !== "playing") {
        return;
    }
    ensureSocket().emit("room_move", { code: room.code, row, col });
}

createRoomBtn?.addEventListener("click", onCreateRoom);
joinRoomBtn?.addEventListener("click", onJoinRoom);
startOnlineBtn?.addEventListener("click", onStartRoom);
sendChatBtn?.addEventListener("click", onSendChat);
chatInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        onSendChat();
    }
});

document.getElementById("backModesBtn")?.addEventListener("click", () => {
    window.location.href = "/modes.html";
});
victoryBackBtn?.addEventListener("click", () => {
    window.location.href = "/modes.html";
});
victoryCloseBtn?.addEventListener("click", hideVictoryDialog);

ensureSocket();
updateStartButtonState();

const prefilledCode = new URLSearchParams(window.location.search).get("code");
if (prefilledCode) {
    roomCodeInput.value = String(prefilledCode).toUpperCase();
    onJoinRoom();
}


