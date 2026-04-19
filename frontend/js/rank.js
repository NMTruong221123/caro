import { buildStatus, renderBoard, renderLegend } from "./ui.js";
import { getActiveRoomSession } from "./api.js";
import { requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: false });
if (!session) {
    throw new Error("Unauthorized");
}
initTopbar();

const token = session.token || "";
const queueBtn = document.getElementById("queueBtn");
const queueInfo = document.getElementById("queueInfo");
const board = document.getElementById("board");
const legend = document.getElementById("legend");
const status = document.getElementById("status");
const vsCard = document.getElementById("vsCard");
const vsText = document.getElementById("vsText");

let socket = null;
let searching = false;
let roomCode = "";
let state = null;
let remain = 120;
let timer = null;

function rankText(player) {
    const displayTier = String(player?.displayTier || player?.rank_tier || "Bronze");
    const division = String(player?.division || "V");
    const starsInDivision = Number(player?.starsInDivision ?? 0) + 1;
    return `${displayTier} ${division}-${starsInDivision}*`;
}

function setQueueInfo(msg, isError = false) {
    queueInfo.textContent = msg;
    queueInfo.style.color = isError ? "#fecaca" : "#a7f3d0";
}

function setStatus(msg, isError = false) {
    status.textContent = msg;
    status.style.color = isError ? "#fecaca" : "#bae6fd";
}

function startCountdown() {
    clearInterval(timer);
    remain = 120;
    timer = setInterval(() => {
        remain -= 1;
        if (!searching) {
            clearInterval(timer);
            return;
        }
        setQueueInfo(`Dang ghep tran... ${remain}s`);
        if (remain <= 0) {
            searching = false;
            queueBtn.textContent = "Tim tran rank";
            socket.emit("rank_queue_cancel");
            setQueueInfo("Ghep tran khong thanh cong do khong co nguoi choi.", true);
            clearInterval(timer);
        }
    }, 1000);
}

function ensureSocket() {
    if (socket?.connected) {
        return socket;
    }
    socket = window.io({ auth: { token }, transports: ["websocket", "polling"] });

    socket.on("connect", async () => {
        if (roomCode) {
            socket.emit("join_room", { code: roomCode });
            return;
        }

        try {
            const active = await getActiveRoomSession(token);
            const sessionPayload = active?.session;
            if (!sessionPayload?.room?.code) {
                return;
            }

            roomCode = String(sessionPayload.room.code || "");
            state = sessionPayload.state || null;
            setQueueInfo(`Da reconnect vao tran dang choi: ${roomCode}`);
            socket.emit("join_room", { code: roomCode });

            if (state) {
                renderLegend(legend, state.players || []);
                renderBoard(board, state, onCellClick);
                setStatus(buildStatus(state));
            }
        } catch (_error) {
            // Ignore when no active room is available.
        }
    });

    socket.on("room_error", (payload) => setQueueInfo(payload?.error || "Loi", true));
    socket.on("rank_queue_waiting", () => {
        searching = true;
        queueBtn.textContent = "Huy tim tran";
        startCountdown();
    });
    socket.on("rank_queue_timeout", (payload) => {
        searching = false;
        queueBtn.textContent = "Tim tran rank";
        clearInterval(timer);
        setQueueInfo(payload?.message || "Het thoi gian tim tran", true);
    });
    socket.on("rank_queue_canceled", () => {
        searching = false;
        queueBtn.textContent = "Tim tran rank";
        clearInterval(timer);
        setQueueInfo("Da huy tim tran rank.");
    });

    socket.on("rank_queue_matched", (payload) => {
        searching = false;
        queueBtn.textContent = "Tim tran rank";
        clearInterval(timer);
        roomCode = String(payload?.code || "");
        setQueueInfo(`Ghep tran thanh cong: ${roomCode}`);
    });

    socket.on("room_state", (payload) => {
        if (payload.room?.code) {
            roomCode = payload.room.code;
            const players = payload.room.players || [];
            if (players.length >= 2) {
                vsCard.classList.remove("hidden");
                const p1 = players[0];
                const p2 = players[1];
                vsText.textContent = `${p1.username} (${rankText(p1)}) VS ${p2.username} (${rankText(p2)})`;
            }
        }
        if (payload.state) {
            state = payload.state;
            renderLegend(legend, state.players);
            renderBoard(board, state, onCellClick);
            setStatus(buildStatus(state));
        }
    });

    return socket;
}

function onQueueToggle() {
    const io = ensureSocket();
    if (!searching) {
        io.emit("rank_queue_join");
    } else {
        io.emit("rank_queue_cancel");
    }
}

function onCellClick(row, col) {
    if (!state || state.status !== "playing" || !roomCode) {
        return;
    }
    ensureSocket().emit("room_move", { code: roomCode, row, col });
}

queueBtn?.addEventListener("click", onQueueToggle);
document.getElementById("backModesBtn")?.addEventListener("click", () => {
    window.location.href = "/modes.html";
});

ensureSocket();


