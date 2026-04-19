import { getMe } from "./api.js";
import { requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: true });
initTopbar();

const welcomeText = document.getElementById("welcomeText");
const equippedTitleText = document.getElementById("equippedTitleText");
const profileSummary = document.getElementById("profileSummary");
const aiStat = document.getElementById("aiStat");
const roomStat = document.getElementById("roomStat");
const rankStat = document.getElementById("rankStat");
const progressStat = document.getElementById("progressStat");
const homeRankBadge = document.getElementById("homeRankBadge");
const homeRankTitle = document.getElementById("homeRankTitle");

const TITLE_FROM_CODE = {
    bronze: "Chien Binh Tap Su",
    silver: "Chien Binh Kien Cuong",
    platinum: "Hiep Si Tinh Anh",
    diamond: "Thu Linh Bat Khuat",
    master: "Bac Thay Chien Tran",
    challenger: "Chien Than Thach Dau",
    king: "Vua Bat Diet",
};

function titleFromCode(code) {
    const normalized = String(code || "").trim().toLowerCase();
    if (!normalized.startsWith("title_")) {
        return "";
    }
    const key = normalized.replace("title_", "");
    return TITLE_FROM_CODE[key] || "";
}

if (session) {
    const user = session.user || {};
    welcomeText.textContent = session.guest
        ? `Xin chao ${user.username} (Khach)`
        : `Xin chao ${user.username}`;

    const renderSummary = (u) => {
        const gamesAi = Number(u.gamesVsAi || 0);
        const gamesRoom = Number(u.gamesVsRoom || 0);
        const gamesRank = Number(u.gamesRanked || 0);
        const aiRate = gamesAi > 0 ? ((Number(u.winsVsAi || 0) * 100) / gamesAi).toFixed(1) : "0.0";
        const roomRate = gamesRoom > 0 ? ((Number(u.winsVsRoom || 0) * 100) / gamesRoom).toFixed(1) : "0.0";
        const rankRate = gamesRank > 0 ? ((Number(u.winsRanked || 0) * 100) / gamesRank).toFixed(1) : "0.0";
        const equippedTitle = String(u.selectedTitleName || titleFromCode(u.selectedTitleCode) || u.rankVisual?.rankTitle || "Tan thu");
        if (equippedTitleText) {
            equippedTitleText.textContent = `Danh hieu dang deo: ${equippedTitle}`;
        }
        profileSummary.textContent = `ID: ${u.id} | Rank: ${u.rankVisual?.displayTier || u.rankTier || "Dong"} ${u.rankVisual?.division || "V"}-${(u.rankVisual?.starsInDivision ?? 0) + 1}*`;
        if (aiStat) {
            aiStat.textContent = `${aiRate}% (${u.winsVsAi || 0}/${gamesAi})`;
        }
        if (roomStat) {
            roomStat.textContent = `${roomRate}% (${u.winsVsRoom || 0}/${gamesRoom})`;
        }
        if (rankStat) {
            rankStat.textContent = `${rankRate}% (${u.winsRanked || 0}/${gamesRank})`;
        }
        if (progressStat) {
            progressStat.textContent = `${u.rankVisual?.rankTitle || "Tan thu"}`;
        }
        if (homeRankBadge) {
            const image = String(u.rankVisual?.badgeImage || "");
            if (image) {
                homeRankBadge.src = image;
                homeRankBadge.classList.remove("hidden");
            } else {
                homeRankBadge.classList.add("hidden");
            }
        }
        if (homeRankTitle) {
            homeRankTitle.textContent = `${u.rankVisual?.displayTier || "Dong"} - ${u.rankVisual?.rankTitle || "Chien Binh Tap Su"}`;
        }
    };

    if (session.guest) {
        renderSummary(user);
    } else {
        getMe(session.token)
            .then((data) => renderSummary(data.user || user))
            .catch(() => renderSummary(user));
    }
}

document.getElementById("toModesBtn")?.addEventListener("click", () => {
    window.location.href = "/modes.html";
});

document.getElementById("toSettingsBtn")?.addEventListener("click", () => {
    window.location.href = "/settings.html";
});

document.getElementById("toHistoryBtn")?.addEventListener("click", () => {
    window.location.href = "/history.html";
});

document.getElementById("toAdminBtn")?.addEventListener("click", () => {
    window.location.href = "/admin.html";
});



