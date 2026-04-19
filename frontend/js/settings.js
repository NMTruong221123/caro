import { getChatFilterSettings, getMe, getRankCatalog, updateChatFilterSettings } from "./api.js";
import { requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: true });
initTopbar();

const rankCatalog = document.getElementById("rankCatalog");
const equippedInfo = document.getElementById("equippedInfo");
const customBannedWordsInput = document.getElementById("customBannedWordsInput");
const saveBannedWordsBtn = document.getElementById("saveBannedWordsBtn");
const reloadBannedWordsBtn = document.getElementById("reloadBannedWordsBtn");
const bannedWordsStatus = document.getElementById("bannedWordsStatus");


function setBannedWordsStatus(message, isError = false) {
    if (!bannedWordsStatus) {
        return;
    }
    bannedWordsStatus.textContent = message;
    bannedWordsStatus.style.color = isError ? "#fecaca" : "#a7f3d0";
}


async function loadBannedWords() {
    if (!customBannedWordsInput || session?.guest) {
        return;
    }
    try {
        const data = await getChatFilterSettings(session.token);
        const words = Array.isArray(data.customBannedWords) ? data.customBannedWords : [];
        customBannedWordsInput.value = words.join("\n");
        setBannedWordsStatus(`Dang co ${words.length} tu cam tuy chinh.`);
    } catch (error) {
        setBannedWordsStatus(error.message || "Khong tai duoc tu cam", true);
    }
}


async function saveBannedWords() {
    if (!customBannedWordsInput || session?.guest) {
        return;
    }

    const raw = String(customBannedWordsInput.value || "");
    const words = raw
        .replaceAll(",", "\n")
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);

    try {
        const data = await updateChatFilterSettings(session.token, {
            customBannedWords: words,
        });
        const saved = Array.isArray(data.customBannedWords) ? data.customBannedWords : [];
        customBannedWordsInput.value = saved.join("\n");
        setBannedWordsStatus(`Da luu ${saved.length} tu cam tuy chinh.`);
    } catch (error) {
        setBannedWordsStatus(error.message || "Luu tu cam that bai", true);
    }
}

async function init() {
    if (!session) {
        return;
    }

    try {
        const data = await getRankCatalog();
        if (rankCatalog) {
            rankCatalog.innerHTML = "";
            for (const item of data.items || []) {
                const card = document.createElement("div");
                card.className = "rank-card";
                card.innerHTML = `
                    <img src="${item.badgeImage}" class="rank-badge large" alt="${item.display}">
                    <h3>${item.display}</h3>
                    <p class="small-status">Danh hieu: ${item.title}</p>
                    <p class="small-status">Khung: ${item.frameDescription}</p>
                `;
                rankCatalog.appendChild(card);
            }
        }

        if (!session.guest) {
            const me = await getMe(session.token);
            const user = me.user || {};
            equippedInfo.textContent = `Dang deo: danh hieu=${user.selectedTitleName || "chua co"} | frame=${user.selectedFrameCode || "chua co"}`;
            await loadBannedWords();
        } else {
            equippedInfo.textContent = "Tai khoan khach khong trang bi duoc danh hieu tu rank.";
            if (customBannedWordsInput) {
                customBannedWordsInput.disabled = true;
            }
            if (saveBannedWordsBtn) {
                saveBannedWordsBtn.disabled = true;
            }
            if (reloadBannedWordsBtn) {
                reloadBannedWordsBtn.disabled = true;
            }
            setBannedWordsStatus("Tai khoan khach khong the chinh sua tu cam.", true);
        }
    } catch (error) {
        if (rankCatalog) {
            rankCatalog.textContent = error.message || "Khong tai duoc du lieu rank";
        }
    }
}

document.getElementById("backProfileBtn")?.addEventListener("click", () => {
    window.location.href = "/profile.html";
});

saveBannedWordsBtn?.addEventListener("click", saveBannedWords);
reloadBannedWordsBtn?.addEventListener("click", loadBannedWords);

init();


