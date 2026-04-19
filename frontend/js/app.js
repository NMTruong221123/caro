import {
    createOnlineRoom,
    getLeaderboard,
    getMe,
    joinOnlineRoom,
    loginUser,
    playMove,
    registerUser,
    startMatch,
} from "./api.js";
import { buildStatus, renderBoard, renderLeaderboard, renderLegend } from "./ui.js";

const modeSelect = document.getElementById("modeSelect");
const aiLevelWrap = document.getElementById("aiLevelWrap");
const aiLevel = document.getElementById("aiLevel");
const playersWrap = document.getElementById("playersWrap");
const playersCount = document.getElementById("playersCount");
const onlineMaxPlayersWrap = document.getElementById("onlineMaxPlayersWrap");
const onlineMaxPlayers = document.getElementById("onlineMaxPlayers");
const onlineControls = document.getElementById("onlineControls");
const createRoomBtn = document.getElementById("createRoomBtn");
const joinRoomBtn = document.getElementById("joinRoomBtn");
const startOnlineBtn = document.getElementById("startOnlineBtn");
const roomCodeInput = document.getElementById("roomCodeInput");
const roomInfo = document.getElementById("roomInfo");
const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");
const roomMembers = document.getElementById("roomMembers");
const joinRankBtn = document.getElementById("joinRankBtn");

const boardSize = document.getElementById("boardSize");
const startBtn = document.getElementById("startBtn");
const boardElement = document.getElementById("board");
const statusElement = document.getElementById("status");
const legendElement = document.getElementById("legend");
const leaderboardElement = document.getElementById("leaderboard");
const leaderboardType = document.getElementById("leaderboardType");

const usernameInput = document.getElementById("usernameInput");
const passwordInput = document.getElementById("passwordInput");
const registerBtn = document.getElementById("registerBtn");
const loginBtn = document.getElementById("loginBtn");
const authStatus = document.getElementById("authStatus");
const victoryModal = document.getElementById("victoryModal");
const victoryText = document.getElementById("victoryText");
const victoryCloseBtn = document.getElementById("victoryCloseBtn");

let currentState = null;
let waiting = false;
let authToken = localStorage.getItem("caro_token") || "";
let currentUser = null;
let currentRoom = null;
let socket = null;
let announcedMatchResultId = null;
let rankSearching = false;


function setRankQueueUI(searching) {
    rankSearching = searching;
    if (!joinRankBtn) {
        return;
    }
    joinRankBtn.textContent = searching ? "Huy tim tran" : "Tim tran rank";
}

function updateStartOnlinePermission() {
    if (!currentRoom || !currentUser) {
        startOnlineBtn.disabled = true;
        return;
    }
    const isOwner = Number(currentRoom.ownerUserId) === Number(currentUser.id);
    startOnlineBtn.disabled = !isOwner;
    if (!isOwner) {
        startOnlineBtn.title = "Chi chu phong duoc bat dau";
    } else {
        startOnlineBtn.title = "";
    }
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

function shouldStickToBottom() {
    const threshold = 18;
    const distance = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight;
    return distance <= threshold;
}

function updateModeUI() {
    const isMulti = modeSelect.value === "multi";
    const isAi = modeSelect.value === "ai";
    const isOnline = modeSelect.value === "online";
    const isRanked = modeSelect.value === "ranked";

    playersWrap.classList.toggle("hidden", !isMulti);
    aiLevelWrap.classList.toggle("hidden", !isAi);
    onlineMaxPlayersWrap.classList.toggle("hidden", !isOnline);
    onlineControls.classList.toggle("hidden", !(isOnline || isRanked));
    if (joinRankBtn) {
        joinRankBtn.classList.toggle("hidden", !isRanked);
        setRankQueueUI(rankSearching && isRanked);
    }
    createRoomBtn.classList.toggle("hidden", isRanked);
    joinRoomBtn.classList.toggle("hidden", isRanked);
    startOnlineBtn.classList.toggle("hidden", isRanked);
    roomCodeInput.closest("label")?.classList.toggle("hidden", isRanked);
    startBtn.classList.toggle("hidden", isOnline || isRanked);
}

function showStatus(message, isError = false) {
    statusElement.textContent = message;
    statusElement.style.color = isError ? "#fecaca" : "#bae6fd";
}

function paintState() {
    if (!currentState) {
        return;
    }

    renderLegend(legendElement, currentState.players);
    renderBoard(boardElement, currentState, handleCellClick);
    showStatus(buildStatus(currentState));
    maybeShowVictoryDialog(currentState);
}

function hideVictoryDialog() {
    victoryModal?.classList.add("hidden");
}

function maybeShowVictoryDialog(state) {
    if (!state || state.status !== "finished") {
        return;
    }
    if (announcedMatchResultId === state.matchId) {
        return;
    }

    const roomPlayers = state.roomPlayers || [];
    const winnerPlayer = roomPlayers.find((item) => Number(item.player_index) === Number(state.winner));
    const winnerName = winnerPlayer?.username || (state.mode === "ai" ? currentUser?.username : null) || `P${state.winner}`;
    const winnerToken = state.players?.[Number(state.winner) - 1]?.shape?.toUpperCase() || `P${state.winner}`;

    const iWonOnline = currentUser && winnerPlayer && Number(winnerPlayer.user_id) === Number(currentUser.id);
    const iWonVsAi = currentUser && state.mode === "ai" && Number(state.winner) === 1;
    const iWon = Boolean(iWonOnline || iWonVsAi);
    if (iWon && victoryText && victoryModal) {
        victoryText.textContent = `Chuc mung nguoi choi ${winnerToken} (${winnerName}) da thang, ban da duoc +1 diem vao diem BXH.`;
        victoryModal.classList.remove("hidden");
    }
    announcedMatchResultId = state.matchId;
}

function setAuthStatus(message, isError = false) {
    authStatus.textContent = message;
    authStatus.style.color = isError ? "#fecaca" : "#c7d2fe";
}

function setRoomInfo(message, isError = false) {
    roomInfo.textContent = message;
    roomInfo.style.color = isError ? "#fecaca" : "#a7f3d0";
}

function renderRoomMembers() {
    roomMembers.innerHTML = "";
    if (!currentRoom?.players) {
        return;
    }

    const isOwner = !!(currentRoom && currentUser && Number(currentRoom.ownerUserId) === Number(currentUser.id));
    const me = currentRoom.players.find((player) => Number(player.user_id) === Number(currentUser?.id));
    const canModerate = isOwner || Number(me?.is_co_host) === 1;

    currentRoom.players.forEach((player) => {
        const row = document.createElement("div");
        row.className = "room-member";

        const meta = document.createElement("div");
        meta.className = "meta";
        const ownerTag = Number(player.user_id) === Number(currentRoom.ownerUserId) ? " [Chu phong]" : "";
        const coHostTag = Number(player.is_co_host) === 1 ? " [Co-host]" : "";
        const muteTag = Number(player.is_muted) === 1 ? " [Muted]" : "";
        meta.textContent = `P${player.player_index} - ${player.username}${ownerTag}${coHostTag}${muteTag} | ELO ${player.rating}`;
        row.appendChild(meta);

        if (canModerate && Number(player.user_id) !== Number(currentUser.id)) {
            const actions = document.createElement("div");
            actions.className = "member-actions";

            const muteBtn = document.createElement("button");
            muteBtn.type = "button";
            const isMuted = Number(player.is_muted) === 1;
            muteBtn.textContent = isMuted ? "Unmute" : "Mute";
            muteBtn.addEventListener("click", () => {
                const realtime = ensureSocket();
                realtime?.emit("room_owner_mute", {
                    code: currentRoom.code,
                    targetUserId: Number(player.user_id),
                    muted: !isMuted,
                });
            });

            const kickBtn = document.createElement("button");
            kickBtn.type = "button";
            kickBtn.textContent = "Kick";
            kickBtn.addEventListener("click", () => {
                const realtime = ensureSocket();
                realtime?.emit("room_owner_kick", {
                    code: currentRoom.code,
                    targetUserId: Number(player.user_id),
                });
            });

            actions.appendChild(muteBtn);
            actions.appendChild(kickBtn);

            if (isOwner && Number(player.user_id) !== Number(currentRoom.ownerUserId)) {
                const coHostBtn = document.createElement("button");
                coHostBtn.type = "button";
                const enabled = Number(player.is_co_host) === 1;
                coHostBtn.textContent = enabled ? "Bo co-host" : "Set co-host";
                coHostBtn.addEventListener("click", () => {
                    const realtime = ensureSocket();
                    realtime?.emit("room_owner_set_cohost", {
                        code: currentRoom.code,
                        targetUserId: Number(player.user_id),
                        enabled: !enabled,
                    });
                });
                actions.appendChild(coHostBtn);
            }

            row.appendChild(actions);
        }

        roomMembers.appendChild(row);
    });
}

function renderChatMessages(messages) {
    chatMessages.innerHTML = "";
    messages.forEach((item) => appendChatMessage(item, true));
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendChatMessage(item, forceScroll = false) {
    const stick = forceScroll || shouldStickToBottom();

    const row = document.createElement("div");
    row.className = "chat-item";

    const who = document.createElement("span");
    who.className = "who";
    who.textContent = `${item.username}: `;

    const msg = document.createElement("span");
    msg.textContent = item.message;

    const time = document.createElement("span");
    time.className = "time";
    time.textContent = formatTimestamp(item.createdAt || item.created_at);

    row.appendChild(who);
    row.appendChild(msg);
    row.appendChild(time);
    chatMessages.appendChild(row);

    if (stick) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

async function refreshLeaderboard() {
    try {
        const kind = leaderboardType?.value || "room";
        const data = await getLeaderboard(10, kind);
        renderLeaderboard(leaderboardElement, data.items || [], kind);
    } catch (_error) {
        leaderboardElement.textContent = "Khong tai duoc leaderboard.";
    }
}

function ensureSocket() {
    if (!authToken) {
        return null;
    }
    if (socket && socket.connected) {
        return socket;
    }

    socket = window.io({
        auth: { token: authToken },
        transports: ["websocket", "polling"],
    });

    socket.on("connect", () => setRoomInfo("Da ket noi realtime."));
    socket.on("room_error", (payload) => setRoomInfo(payload?.error || "Loi phong", true));
    socket.on("room_state", (payload) => {
        if (payload.room) {
            currentRoom = payload.room;
            roomCodeInput.value = payload.room.code;
            setRoomInfo(`Phong ${payload.room.code}: ${payload.room.players.length}/${payload.room.maxPlayers}`);
            updateStartOnlinePermission();
            renderRoomMembers();
        }
        if (payload.state) {
            currentState = payload.state;
            if (!currentState.roomPlayers && payload.room?.players) {
                currentState.roomPlayers = payload.room.players;
            }
            paintState();
            if (currentState.status !== "playing") {
                refreshLeaderboard();
            }
        }
    });

    socket.on("rank_queue_waiting", (payload) => {
        setRankQueueUI(true);
        const size = Number(payload?.queueSize || 1);
        setRoomInfo(`Dang tim tran rank... Hang doi hien co ${size} nguoi.`);
    });

    socket.on("rank_queue_timeout", (payload) => {
        setRankQueueUI(false);
        setRoomInfo(payload?.message || "Tim tran rank da het thoi gian", true);
    });

    socket.on("rank_queue_canceled", () => {
        setRankQueueUI(false);
        setRoomInfo("Da huy tim tran rank.");
    });

    socket.on("rank_queue_matched", (payload) => {
        setRankQueueUI(false);
        if (payload?.code) {
            roomCodeInput.value = payload.code;
            setRoomInfo(`Da ghep tran rank: ${payload.code}`);
        }
    });

    socket.on("room_chat_history", (payload) => {
        if (!payload || !Array.isArray(payload.messages)) {
            return;
        }
        renderChatMessages(payload.messages);
    });

    socket.on("room_chat_message", (payload) => {
        if (!payload) {
            return;
        }
        appendChatMessage(payload);
    });

    socket.on("room_kicked", (payload) => {
        if (payload?.code && currentRoom?.code === payload.code) {
            currentRoom = null;
            currentState = null;
            roomMembers.innerHTML = "";
            chatMessages.innerHTML = "";
            updateStartOnlinePermission();
            setRoomInfo(payload.message || "Ban da bi kick khoi phong", true);
            showStatus("Ban da bi kick khoi phong.", true);
        }
    });

    return socket;
}

async function handleCellClick(row, col) {
    if (!currentState || waiting || currentState.status !== "playing") {
        return;
    }

    if (modeSelect.value === "online" || modeSelect.value === "ranked") {
        if (!socket || !currentRoom) {
            showStatus("Ban chua vao phong online.", true);
            return;
        }
        socket.emit("room_move", {
            code: currentRoom.code,
            row,
            col,
        });
        return;
    }

    waiting = true;
    try {
        const updated = await playMove({
            matchId: currentState.matchId,
            row,
            col,
        }, authToken);

        currentState = updated;
        paintState();
    } catch (error) {
        showStatus(error.message, true);
    } finally {
        waiting = false;
    }
}

async function handleStart() {
    if (modeSelect.value === "online" || modeSelect.value === "ranked") {
        return;
    }

    waiting = true;
    startBtn.disabled = true;

    const payload = {
        mode: modeSelect.value,
        playersCount: Number(playersCount.value),
        boardSize: Number(boardSize.value),
        winLength: 5,
        aiLevel: aiLevel.value,
    };

    try {
        currentState = await startMatch(payload, authToken);
        paintState();
    } catch (error) {
        showStatus(error.message, true);
    } finally {
        waiting = false;
        startBtn.disabled = false;
    }
}

function handleJoinRankQueue() {
    if (!authToken) {
        setRoomInfo("Can dang nhap de choi rank.", true);
        return;
    }

    const realtime = ensureSocket();
    if (!realtime) {
        return;
    }

    if (rankSearching) {
        realtime.emit("rank_queue_cancel");
        return;
    }

    realtime.emit("rank_queue_join");
}

async function handleRegister() {
    try {
        const result = await registerUser({
            username: usernameInput.value.trim(),
            password: passwordInput.value.trim(),
        });
        setAuthStatus(`Dang ky thanh cong: ${result.user.username}`);
        refreshLeaderboard();
    } catch (error) {
        setAuthStatus(error.message, true);
    }
}

async function handleLogin() {
    try {
        const result = await loginUser({
            username: usernameInput.value.trim(),
            password: passwordInput.value.trim(),
        });
        authToken = result.token;
        currentUser = result.user;
        localStorage.setItem("caro_token", authToken);
        setAuthStatus(`Xin chao ${currentUser.username} | ELO ${currentUser.rating}`);
        ensureSocket();
    } catch (error) {
        setAuthStatus(error.message, true);
    }
}

async function restoreLogin() {
    if (!authToken) {
        return;
    }
    try {
        const data = await getMe(authToken);
        currentUser = data.user;
        setAuthStatus(`Xin chao ${currentUser.username} | ELO ${currentUser.rating}`);
        ensureSocket();
    } catch (_error) {
        localStorage.removeItem("caro_token");
        authToken = "";
    }
}

async function handleCreateRoom() {
    if (!authToken) {
        setRoomInfo("Can dang nhap de tao phong.", true);
        return;
    }

    try {
        const payload = {
            maxPlayers: Number(onlineMaxPlayers.value),
        };
        const data = await createOnlineRoom(authToken, payload);
        currentRoom = data.room;
        roomCodeInput.value = currentRoom.code;
        setRoomInfo(`Da tao phong ${currentRoom.code}`);
        updateStartOnlinePermission();
        renderRoomMembers();

        const realtime = ensureSocket();
        realtime?.emit("join_room", { code: currentRoom.code });
    } catch (error) {
        setRoomInfo(error.message, true);
    }
}

async function handleJoinRoom() {
    if (!authToken) {
        setRoomInfo("Can dang nhap de vao phong.", true);
        return;
    }

    const code = roomCodeInput.value.trim().toUpperCase();
    if (!code) {
        setRoomInfo("Nhap ma phong truoc.", true);
        return;
    }

    try {
        const data = await joinOnlineRoom(authToken, { code });
        currentRoom = data.room;
        setRoomInfo(`Da vao phong ${currentRoom.code}`);
        updateStartOnlinePermission();
        renderRoomMembers();

        const realtime = ensureSocket();
        realtime?.emit("join_room", { code });
    } catch (error) {
        setRoomInfo(error.message, true);
    }
}

function handleStartOnline() {
    if (!currentRoom) {
        setRoomInfo("Can tao hoac vao phong truoc.", true);
        return;
    }
    if (!currentUser || Number(currentRoom.ownerUserId) !== Number(currentUser.id)) {
        setRoomInfo("Chi chu phong moi duoc bat dau tran.", true);
        return;
    }

    const realtime = ensureSocket();
    realtime?.emit("start_room_game", {
        code: currentRoom.code,
        boardSize: Number(boardSize.value),
        winLength: 5,
    });
}

function handleSendChat() {
    const realtime = ensureSocket();
    if (!realtime || !currentRoom) {
        setRoomInfo("Can vao phong de chat.", true);
        return;
    }

    const message = chatInput.value.trim();
    if (!message) {
        return;
    }

    realtime.emit("room_chat", {
        code: currentRoom.code,
        message,
    });
    chatInput.value = "";
}

function bindEvents() {
    const required = [
        modeSelect,
        startBtn,
        registerBtn,
        loginBtn,
        createRoomBtn,
        joinRoomBtn,
        startOnlineBtn,
        joinRankBtn,
        sendChatBtn,
        chatInput,
        leaderboardType,
        victoryCloseBtn,
    ];
    if (required.some((item) => !item)) {
        console.error("Khong tim thay mot so phan tu UI, bo qua bind su kien.");
        return false;
    }

    modeSelect.addEventListener("change", updateModeUI);
    startBtn.addEventListener("click", handleStart);
    registerBtn.addEventListener("click", handleRegister);
    loginBtn.addEventListener("click", handleLogin);
    createRoomBtn.addEventListener("click", handleCreateRoom);
    joinRoomBtn.addEventListener("click", handleJoinRoom);
    startOnlineBtn.addEventListener("click", handleStartOnline);
    joinRankBtn.addEventListener("click", handleJoinRankQueue);
    sendChatBtn.addEventListener("click", handleSendChat);
    leaderboardType.addEventListener("change", refreshLeaderboard);
    victoryCloseBtn.addEventListener("click", hideVictoryDialog);
    chatInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            handleSendChat();
        }
    });

    return true;
}

function initApp() {
    if (!bindEvents()) {
        return;
    }
    updateModeUI();
    restoreLogin();
    refreshLeaderboard();
    updateStartOnlinePermission();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp, { once: true });
} else {
    initApp();
}
