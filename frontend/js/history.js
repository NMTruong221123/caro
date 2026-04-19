import { getMatchHistory } from "./api.js";
import { requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: false });
if (!session) {
    throw new Error("Unauthorized");
}
initTopbar();

const historyList = document.getElementById("historyList");
const historyStatus = document.getElementById("historyStatus");

function setStatus(message, isError = false) {
    if (!historyStatus) {
        return;
    }
    historyStatus.textContent = message;
    historyStatus.style.color = isError ? "#fecaca" : "#a7f3d0";
}

function formatResult(item) {
    if (item.isDraw) {
        return "Hoa";
    }
    return item.meWon ? "Thang" : "Thua";
}

function formatOpponents(item) {
    const names = (item.opponents || []).map((op) => op.username).filter(Boolean);
    if (!names.length) {
        return "Khong co doi thu";
    }
    return names.join(", ");
}

function renderHistory(items) {
    if (!historyList) {
        return;
    }

    historyList.innerHTML = "";
    if (!items.length) {
        historyList.textContent = "Chua co tran nao de hien thi.";
        return;
    }

    for (const item of items) {
        const card = document.createElement("section");
        card.className = "screen-card";
        const result = formatResult(item);
        const createdAt = item.createdAt ? new Date(String(item.createdAt).replace(" ", "T")).toLocaleString("vi-VN") : "";

        card.innerHTML = `
            <h2>#${item.id} - ${String(item.matchType || "casual").toUpperCase()} (${result})</h2>
            <p class="small-status">Doi thu: ${formatOpponents(item)}</p>
            <p class="small-status">Ban: ${item.boardSize}x${item.boardSize} | Win: ${item.winLength} | Nuoc di: ${item.movesCount}</p>
            <p class="small-status">Phong: ${item.roomCode || "N/A"} | Luc: ${createdAt || "N/A"}</p>
            <div class="inline-actions">
                <button type="button" data-match-id="${item.id}">Xem replay</button>
                <button type="button" class="ghost-btn" data-action="copy" data-room-code="${item.roomCode || ""}">Copy room</button>
            </div>
        `;

        card.querySelector("button[data-match-id]")?.addEventListener("click", () => {
            window.location.href = `/replay.html?matchId=${encodeURIComponent(item.id)}`;
        });

        card.querySelector("button[data-action='copy']")?.addEventListener("click", async (event) => {
            const target = event.currentTarget;
            if (!(target instanceof HTMLButtonElement)) {
                return;
            }
            const roomCode = String(target.getAttribute("data-room-code") || "").trim();
            if (!roomCode) {
                setStatus("Tran nay khong co ma phong de copy.", true);
                return;
            }
            try {
                await navigator.clipboard.writeText(roomCode);
                setStatus(`Da copy ma phong ${roomCode}.`);
            } catch (_error) {
                setStatus("Khong copy duoc ma phong.", true);
            }
        });

        historyList.appendChild(card);
    }
}

async function loadHistory() {
    setStatus("Dang tai lich su tran...");
    try {
        const data = await getMatchHistory(session.token, 50);
        const items = Array.isArray(data.items) ? data.items : [];
        renderHistory(items);
        setStatus(`Da tai ${items.length} tran.`);
    } catch (error) {
        setStatus(error.message || "Khong tai duoc lich su tran", true);
    }
}

document.getElementById("reloadHistoryBtn")?.addEventListener("click", loadHistory);
document.getElementById("backHomeBtn")?.addEventListener("click", () => {
    window.location.href = "/home.html";
});

loadHistory();

