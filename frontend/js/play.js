import { playMove, startMatch } from "./api.js";
import { getSession, requireSession } from "./session.js";
import { adjustBoardZoom, buildStatus, makeZoomControlsDraggable, renderBoard, renderLegend, setBoardZoom } from "./ui.js";
import { initTopbar } from "./topbar.js?v=20260419n";

requireSession({ allowGuest: true });
initTopbar();
const session = getSession();
const token = session?.guest ? "" : session?.token || "";

const params = new URLSearchParams(window.location.search);
const mode = String(params.get("mode") || "ai");

const playTitle = document.getElementById("playTitle");
const aiLevelWrap = document.getElementById("aiLevelWrap");
const aiLevel = document.getElementById("aiLevel");
const playersWrap = document.getElementById("playersWrap");
const playersCount = document.getElementById("playersCount");
const boardSize = document.getElementById("boardSize");
const startBtn = document.getElementById("startBtn");
const board = document.getElementById("board");
const legend = document.getElementById("legend");
const status = document.getElementById("status");
const zoomInBtn = document.getElementById("zoomInBtn");
const zoomOutBtn = document.getElementById("zoomOutBtn");
const zoomValue = document.getElementById("zoomValue");
const zoomControls = document.querySelector(".board-zoom-controls");
const victoryModal = document.getElementById("victoryModal");
const victoryText = document.getElementById("victoryText");
const victoryBackBtn = document.getElementById("victoryBackBtn");
const victoryCloseBtn = document.getElementById("victoryCloseBtn");

let state = null;
let waiting = false;
let announcedResultKey = "";

function updateZoomLabel(zoom) {
    if (zoomValue) {
        zoomValue.textContent = `${Math.round(Number(zoom || 1) * 100)}%`;
    }
}

function setStatus(message, isError = false) {
    if (!status) {
        return;
    }
    status.textContent = message;
    status.style.color = isError ? "#fecaca" : "#bae6fd";
}

function paint() {
    if (!state) {
        return;
    }
    renderLegend(legend, state.players);
    renderBoard(board, state, onCellClick);
    setStatus(buildStatus(state));
    maybeShowMatchResult(state);
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
        let winnerName = `P${matchState.winner}`;
        if (String(matchState.mode) === "ai") {
            winnerName = Number(matchState.winner) === 1 ? "Ban" : "May";
        }
        victoryText.textContent = `Chuc mung nguoi choi ${winnerName} da thang!`;
    }

    victoryModal.classList.remove("hidden");
}

async function startGame() {
    waiting = true;
    startBtn.disabled = true;
    try {
        const payload = {
            mode,
            boardSize: Number(boardSize.value || 15),
            winLength: 5,
            playersCount: Number(playersCount.value || 4),
            aiLevel: String(aiLevel.value || "medium"),
        };
        state = await startMatch(payload, token);
        announcedResultKey = "";
        hideVictoryDialog();
        paint();
    } catch (error) {
        setStatus(error.message || "Khong bat dau duoc tran", true);
    } finally {
        waiting = false;
        startBtn.disabled = false;
    }
}

async function onCellClick(row, col) {
    if (!state || waiting || state.status !== "playing") {
        return;
    }
    waiting = true;
    try {
        state = await playMove({ matchId: state.matchId, row, col }, token);
        paint();
    } catch (error) {
        setStatus(error.message || "Nuoc di khong hop le", true);
    } finally {
        waiting = false;
    }
}

if (playTitle) {
    playTitle.textContent = mode === "multi" ? "Tran Nhom Local" : "Tran Voi May";
}
if (aiLevelWrap) {
    aiLevelWrap.classList.toggle("hidden", mode !== "ai");
}
if (playersWrap) {
    playersWrap.classList.toggle("hidden", mode !== "multi");
}

startBtn?.addEventListener("click", startGame);
document.getElementById("backModesBtn")?.addEventListener("click", () => {
    window.location.href = "/modes.html";
});
victoryBackBtn?.addEventListener("click", () => {
    window.location.href = "/modes.html";
});
victoryCloseBtn?.addEventListener("click", hideVictoryDialog);

if (mode === "ai") {
    startGame();
}

updateZoomLabel(setBoardZoom(board, 1));
makeZoomControlsDraggable(zoomControls, "caro_zoom_widget_play");
zoomInBtn?.addEventListener("click", () => {
    updateZoomLabel(adjustBoardZoom(board, 1));
});
zoomOutBtn?.addEventListener("click", () => {
    updateZoomLabel(adjustBoardZoom(board, -1));
});


