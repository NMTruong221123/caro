import { getAdminSummary, updateAdminChatFilter } from "./api.js";
import { requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: false }) || { token: "" };
initTopbar();

const adminTokenInput = document.getElementById("adminTokenInput");
const adminStatus = document.getElementById("adminStatus");
const adminStatsText = document.getElementById("adminStatsText");
const activeRoomsList = document.getElementById("activeRoomsList");
const topErrorsList = document.getElementById("topErrorsList");
const securityEventsList = document.getElementById("securityEventsList");
const adminBannedWordsInput = document.getElementById("adminBannedWordsInput");

const TOKEN_KEY = "caro_admin_token";

function currentToken() {
    return String(adminTokenInput?.value || "").trim();
}

function setStatus(message, isError = false) {
    if (!adminStatus) {
        return;
    }
    adminStatus.textContent = message;
    adminStatus.style.color = isError ? "#fecaca" : "#a7f3d0";
}

function renderList(target, items, formatter) {
    if (!target) {
        return;
    }
    target.innerHTML = "";
    if (!items.length) {
        target.textContent = "Khong co du lieu.";
        return;
    }
    for (const item of items) {
        const row = document.createElement("p");
        row.className = "small-status";
        row.textContent = formatter(item);
        target.appendChild(row);
    }
}

async function loadDashboard() {
    const token = currentToken();
    if (token) {
        localStorage.setItem(TOKEN_KEY, token);
    }
    setStatus("Dang tai dashboard...");
    try {
        const data = await getAdminSummary(token, session.token);
        const stats = data.stats || {};
        if (adminStatsText) {
            adminStatsText.textContent = `Online users: ${stats.onlineUsers || 0} | Open sockets: ${stats.openSockets || 0} | Active rooms: ${stats.activeRooms || 0} | Rank queue: ${stats.rankQueueSize || 0}`;
        }

        renderList(activeRoomsList, data.activeRooms || [], (item) => {
            return `#${item.id} | ${item.code} | ${item.status} | ${item.room_type} | ${item.players_count}/${item.max_players}`;
        });

        renderList(topErrorsList, data.topErrors || [], (item) => {
            return `[${item.source}] x${item.count}: ${item.message}`;
        });

        renderList(securityEventsList, data.securityEvents || [], (item) => {
            return `${item.kind} | uid=${item.userId} | ip=${item.ipAddress || "N/A"} | ${item.message}`;
        });

        const customWords = data.chatFilter?.customBannedWords || [];
        if (adminBannedWordsInput) {
            adminBannedWordsInput.value = customWords.join("\n");
        }

        setStatus("Tai dashboard thanh cong.");
    } catch (error) {
        setStatus(error.message || "Khong tai duoc dashboard", true);
    }
}

async function saveCustomBannedWords() {
    const token = currentToken();
    const words = String(adminBannedWordsInput?.value || "")
        .replaceAll(",", "\n")
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);

    try {
        const data = await updateAdminChatFilter(token, { customBannedWords: words }, session.token);
        if (adminBannedWordsInput) {
            const saved = Array.isArray(data.customBannedWords) ? data.customBannedWords : [];
            adminBannedWordsInput.value = saved.join("\n");
            setStatus(`Da luu ${saved.length} tu cam custom.`);
        }
    } catch (error) {
        setStatus(error.message || "Luu tu cam that bai", true);
    }
}

document.getElementById("loadAdminBtn")?.addEventListener("click", loadDashboard);
document.getElementById("reloadAdminBtn")?.addEventListener("click", loadDashboard);
document.getElementById("saveAdminBannedBtn")?.addEventListener("click", saveCustomBannedWords);
document.getElementById("backHomeBtn")?.addEventListener("click", () => {
    window.location.href = "/home.html";
});

const savedToken = localStorage.getItem(TOKEN_KEY);
if (savedToken && adminTokenInput) {
    adminTokenInput.value = savedToken;
}

