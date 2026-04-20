import { getMatchReplay } from "./api.js";
import { handleTokenInvalidError, requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: false });
if (!session) {
    throw new Error("Unauthorized");
}
initTopbar();

const replayMeta = document.getElementById("replayMeta");
const replayStatus = document.getElementById("replayStatus");
const replayBoard = document.getElementById("replayBoard");
const stepRange = document.getElementById("stepRange");
const prevStepBtn = document.getElementById("prevStepBtn");
const nextStepBtn = document.getElementById("nextStepBtn");
const playPauseBtn = document.getElementById("playPauseBtn");
const resetStepBtn = document.getElementById("resetStepBtn");

const params = new URLSearchParams(window.location.search);
const matchId = Number(params.get("matchId") || 0);

let replay = null;
let currentStep = 0;
let playTimer = null;
let cells = [];

function setStatus(message, isError = false) {
    if (!replayStatus) {
        return;
    }
    replayStatus.textContent = message;
    replayStatus.style.color = isError ? "#fecaca" : "#bae6fd";
}

function clearTimer() {
    if (playTimer) {
        clearInterval(playTimer);
        playTimer = null;
    }
    if (playPauseBtn) {
        playPauseBtn.textContent = "Play";
    }
}

function rebuildBoard() {
    if (!replay || !replayBoard) {
        return;
    }

    const size = Number(replay.boardSize || 15);
    replayBoard.style.setProperty("--size", String(size));
    replayBoard.innerHTML = "";
    cells = [];

    for (let row = 0; row < size; row += 1) {
        const line = [];
        for (let col = 0; col < size; col += 1) {
            const cell = document.createElement("div");
            cell.className = "cell taken";
            const marker = document.createElement("span");
            marker.className = "marker";
            cell.appendChild(marker);
            replayBoard.appendChild(cell);
            line.push(marker);
        }
        cells.push(line);
    }
}

function symbolOfMove(move) {
    const symbol = String(move.shape || "").trim();
    if (symbol) {
        return symbol;
    }
    return Number(move.player || 0) === 1 ? "X" : "O";
}

function applyStep(step) {
    if (!replay) {
        return;
    }

    const size = Number(replay.boardSize || 15);
    for (let r = 0; r < size; r += 1) {
        for (let c = 0; c < size; c += 1) {
            const marker = cells[r]?.[c];
            if (marker) {
                marker.textContent = "";
                marker.style.color = "#f8fafc";
            }
        }
    }

    const upto = Math.max(0, Math.min(step, replay.moves.length));
    for (let i = 0; i < upto; i += 1) {
        const move = replay.moves[i];
        const row = Number(move.row || 0);
        const col = Number(move.col || 0);
        const marker = cells[row]?.[col];
        if (!marker) {
            continue;
        }
        marker.textContent = symbolOfMove(move);
        marker.style.color = String(move.color || "#f8fafc");
    }

    currentStep = upto;
    if (stepRange) {
        stepRange.value = String(currentStep);
    }
    setStatus(`Buoc ${currentStep}/${replay.moves.length}`);
}

function playFromCurrent() {
    if (!replay) {
        return;
    }
    if (playTimer) {
        clearTimer();
        return;
    }
    playPauseBtn.textContent = "Pause";
    playTimer = setInterval(() => {
        if (!replay || currentStep >= replay.moves.length) {
            clearTimer();
            return;
        }
        applyStep(currentStep + 1);
    }, 450);
}

async function loadReplay() {
    if (!Number.isFinite(matchId) || matchId <= 0) {
        setStatus("matchId khong hop le", true);
        return;
    }

    setStatus("Dang tai replay...");
    try {
        const data = await getMatchReplay(session.token, matchId);
        replay = data.replay;
        const createdAt = replay.createdAt ? new Date(String(replay.createdAt).replace(" ", "T")).toLocaleString("vi-VN") : "";
        if (replayMeta) {
            replayMeta.textContent = `Tran #${replay.matchId} | ${String(replay.matchType || "casual").toUpperCase()} | ${replay.boardSize}x${replay.boardSize} | Luc: ${createdAt || "N/A"}`;
        }
        if (stepRange) {
            stepRange.min = "0";
            stepRange.max = String((replay.moves || []).length);
            stepRange.value = "0";
        }
        rebuildBoard();
        applyStep(0);
    } catch (error) {
        if (handleTokenInvalidError(error)) {
            return;
        }
        setStatus(error.message || "Khong tai duoc replay", true);
    }
}

prevStepBtn?.addEventListener("click", () => {
    clearTimer();
    applyStep(currentStep - 1);
});

nextStepBtn?.addEventListener("click", () => {
    clearTimer();
    applyStep(currentStep + 1);
});

resetStepBtn?.addEventListener("click", () => {
    clearTimer();
    applyStep(0);
});

playPauseBtn?.addEventListener("click", playFromCurrent);

stepRange?.addEventListener("input", (event) => {
    clearTimer();
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement)) {
        return;
    }
    applyStep(Number(target.value || 0));
});

document.getElementById("backHistoryBtn")?.addEventListener("click", () => {
    window.location.href = "/history.html";
});

loadReplay();

