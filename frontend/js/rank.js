import { adjustBoardZoom, buildStatus, makeZoomControlsDraggable, renderBoard, renderLegend, setBoardZoom } from "./ui.js";
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
const zoomInBtn = document.getElementById("zoomInBtn");
const zoomOutBtn = document.getElementById("zoomOutBtn");
const zoomValue = document.getElementById("zoomValue");
const zoomControls = document.querySelector(".board-zoom-controls");
const vsCard = document.getElementById("vsCard");
const vsText = document.getElementById("vsText");
const victoryModal = document.getElementById("victoryModal");
const victoryText = document.getElementById("victoryText");
const victoryBackBtn = document.getElementById("victoryBackBtn");
const victoryCloseBtn = document.getElementById("victoryCloseBtn");

let socket = null;
let searching = false;
let roomCode = "";
let state = null;
let remain = 120;
let timer = null;
let announcedResultKey = "";
let queueLocked = false;

function syncQueueButton() {
    if (!queueBtn) {
        return;
    }

    if (queueLocked) {
        queueBtn.disabled = true;
        queueBtn.textContent = "Dang trong tran";
        return;
    }

    queueBtn.disabled = false;
    queueBtn.textContent = searching ? "Huy tim tran" : "Tim tran rank";
}

function updateZoomLabel(zoom) {
    if (zoomValue) {
        zoomValue.textContent = `${Math.round(Number(zoom || 1) * 100)}%`;
    }
}

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

function hideVictoryDialog() {
    victoryModal?.classList.add("hidden");
}

function resetRankViewAndBackToQueue() {
    clearInterval(timer);
    searching = false;
    roomCode = "";
    state = null;
    queueLocked = false;
    announcedResultKey = "";
    hideVictoryDialog();

    vsCard?.classList.add("hidden");
    if (vsText) {
        vsText.textContent = "";
    }
    if (board) {
        board.innerHTML = "";
    }
    if (legend) {
        legend.innerHTML = "";
    }
    setStatus("San sang tim tran moi.");
    setQueueInfo("Ban co the tim tran rank moi.");
    syncQueueButton();
    window.location.href = "/rank.html";
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
        victoryText.textContent = "Tran rank ket thuc voi ket qua hoa.";
    } else {
        const roomPlayers = matchState.roomPlayers || [];
        const winnerInfo = roomPlayers.find((player) => Number(player.player_index) === Number(matchState.winner));
        const winnerName = String(winnerInfo?.username || `P${matchState.winner}`);
        victoryText.textContent = `Chuc mung nguoi choi ${winnerName} da thang!`;
    }

    victoryModal.classList.remove("hidden");
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
            queueLocked = false;
            syncQueueButton();
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
            announcedResultKey = "";
            hideVictoryDialog();
            queueLocked = true;
            searching = false;
            syncQueueButton();
            setQueueInfo(`Da reconnect vao tran dang choi: ${roomCode}`);
            socket.emit("join_room", { code: roomCode });

            if (state) {
                renderLegend(legend, state.players || []);
                renderBoard(board, state, onCellClick);
                setStatus(buildStatus(state));
                maybeShowMatchResult(state);
            }
        } catch (_error) {
            // Ignore when no active room is available.
        }
    });

    socket.on("room_error", (payload) => setQueueInfo(payload?.error || "Loi", true));
    socket.on("rank_queue_waiting", () => {
        searching = true;
        queueLocked = false;
        syncQueueButton();
        startCountdown();
    });
    socket.on("rank_queue_timeout", (payload) => {
        searching = false;
        queueLocked = false;
        syncQueueButton();
        clearInterval(timer);
        setQueueInfo(payload?.message || "Het thoi gian tim tran", true);
    });
    socket.on("rank_queue_canceled", () => {
        searching = false;
        queueLocked = false;
        syncQueueButton();
        clearInterval(timer);
        setQueueInfo("Da huy tim tran rank.");
    });

    socket.on("rank_queue_matched", (payload) => {
        searching = false;
        queueLocked = true;
        syncQueueButton();
        clearInterval(timer);
        roomCode = String(payload?.code || "");
        announcedResultKey = "";
        hideVictoryDialog();
        setQueueInfo(`Ghep tran thanh cong: ${roomCode}`);
    });

    socket.on("room_state", (payload) => {
        if (payload.room?.code) {
            roomCode = payload.room.code;
            queueLocked = true;
            searching = false;
            syncQueueButton();
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
            maybeShowMatchResult(state);
        }
    });

    return socket;
}

function onQueueToggle() {
    if (queueLocked || roomCode) {
        return;
    }
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
victoryBackBtn?.addEventListener("click", () => {
    window.location.href = "/modes.html";
});
victoryCloseBtn?.addEventListener("click", resetRankViewAndBackToQueue);

ensureSocket();
syncQueueButton();
updateZoomLabel(setBoardZoom(board, 1));
makeZoomControlsDraggable(zoomControls, "caro_zoom_widget_rank");
zoomInBtn?.addEventListener("click", () => {
    updateZoomLabel(adjustBoardZoom(board, 1));
});
zoomOutBtn?.addEventListener("click", () => {
    updateZoomLabel(adjustBoardZoom(board, -1));
});


