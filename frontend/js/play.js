import { playMove, startMatch } from "./api.js";
import { getSession, requireSession } from "./session.js";
import { buildStatus, renderBoard, renderLegend } from "./ui.js";
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

let state = null;
let waiting = false;

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

if (mode === "ai") {
    startGame();
}


