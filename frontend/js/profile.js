import { getAchievements, getMe, getPublicProfile, updateProfile } from "./api.js";
import { getSession, requireSession, saveSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: true });
initTopbar();
const profileNameLine = document.getElementById("profileNameLine");
const renameInput = document.getElementById("renameInput");
const renameBtn = document.getElementById("renameBtn");
const renameStatus = document.getElementById("renameStatus");
const profileModeLine = document.getElementById("profileModeLine");
const profileRankLine = document.getElementById("profileRankLine");
const achievementSummary = document.getElementById("achievementSummary");
const avatarPicker = document.getElementById("avatarPicker");
const avatarPreview = document.getElementById("avatarPreview");
const saveAvatarBtn = document.getElementById("saveAvatarBtn");
const rankBadge = document.getElementById("profileRankBadge");

const avatarOptions = ["ðŸ™‚", "ðŸ˜Ž", "ðŸ¦Š", "ðŸ¯", "ðŸ¼", "ðŸ§", "ðŸ¦", "ðŸ¸", "ðŸ¤–", "ðŸ²"];

function modeStatText(u) {
    const gamesAi = Number(u.gamesVsAi || 0);
    const gamesRoom = Number(u.gamesVsRoom || 0);
    const gamesRank = Number(u.gamesRanked || 0);
    const aiRate = gamesAi > 0 ? ((Number(u.winsVsAi || 0) * 100) / gamesAi).toFixed(1) : "0.0";
    const roomRate = gamesRoom > 0 ? ((Number(u.winsVsRoom || 0) * 100) / gamesRoom).toFixed(1) : "0.0";
    const rankRate = gamesRank > 0 ? ((Number(u.winsRanked || 0) * 100) / gamesRank).toFixed(1) : "0.0";
    return `AI ${aiRate}% (${u.winsVsAi || 0} thang) | Room ${roomRate}% (${u.winsVsRoom || 0} thang) | Rank ${rankRate}% (${u.winsRanked || 0} thang)`;
}

function renderInfoLines(u) {
    if (profileNameLine) {
        profileNameLine.textContent = `Ten: ${u.username} | ID: ${u.id}`;
    }
    if (profileModeLine) {
        profileModeLine.textContent = `Ty le thang: ${modeStatText(u)}`;
    }
    if (profileRankLine) {
        const rankText = `${u.rankVisual?.displayTier || u.rankTier || "Guest"} ${u.rankVisual?.division || "V"}-${(u.rankVisual?.starsInDivision ?? 0) + 1}*`;
        const streak = Number(u.rankStreak || 0);
        profileRankLine.textContent = streak > 0 ? `Rank: ${rankText} | Streak: ${streak}` : `Rank: ${rankText}`;
    }
}

function setRenameStatus(message, isError = false) {
    if (!renameStatus) {
        return;
    }
    renameStatus.textContent = message;
    renameStatus.style.color = isError ? "#fecaca" : "#a7f3d0";
}

function renderAvatarPicker(currentAvatar) {
    if (!avatarPicker) {
        return;
    }
    avatarPicker.innerHTML = "";
    avatarOptions.forEach((avatar) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "avatar-option";
        button.textContent = avatar;
        if (avatar === currentAvatar) {
            button.classList.add("active");
        }
        button.addEventListener("click", () => {
            avatarPicker.querySelectorAll(".avatar-option").forEach((item) => item.classList.remove("active"));
            button.classList.add("active");
            if (avatarPreview) {
                avatarPreview.textContent = avatar;
            }
        });
        avatarPicker.appendChild(button);
    });
}

function applyRankFrame(userData) {
    if (!avatarPreview) {
        return;
    }
    const selected = String(userData.selectedFrameCode || "").trim();
    const fallback = String(userData.rankVisual?.badgeCode || "bronze").trim();
    const code = selected.startsWith("frame_") ? selected.replace("frame_", "") : fallback;
    avatarPreview.className = "avatar-preview large";
    avatarPreview.classList.add(`rank-frame-${code || "bronze"}`);
    if (rankBadge) {
        const image = String(userData.rankVisual?.badgeImage || "");
        if (image) {
            rankBadge.src = image;
            rankBadge.classList.remove("hidden");
        } else {
            rankBadge.classList.add("hidden");
        }
    }
}

async function init() {
    if (!session) {
        return;
    }

    const params = new URLSearchParams(window.location.search);
    const userIdParam = params.get("userId");
    const sourceParam = (params.get("source") || "").toLowerCase();
    const leaderboardKind = (params.get("kind") || "room").toLowerCase();
    const rankPosParam = params.get("rankPos");

    const backButton = document.getElementById("backHomeBtn");
    if (sourceParam === "leaderboard") {
        backButton.textContent = "Ve BXH";
        backButton.onclick = () => {
            window.location.href = `/leaderboard.html?kind=${encodeURIComponent(leaderboardKind)}`;
        };
    } else {
        backButton.onclick = () => {
            window.location.href = "/home.html";
        };
    }

    if (userIdParam) {
        try {
            const rankPos = rankPosParam && /^\d+$/.test(rankPosParam) ? Number(rankPosParam) : null;
            const data = await getPublicProfile(Number(userIdParam), rankPos);
            const u = data.user;
            renderInfoLines(u);
            if (avatarPreview) {
                avatarPreview.textContent = String(u.avatar || "ðŸ§‘");
            }
            applyRankFrame(u);
            if (achievementSummary) {
                const done = (data.achievements || []).filter((item) => item.completed).length;
                achievementSummary.textContent = `Thanh tuu: ${done}/${(data.achievements || []).length} da hoan thanh.`;
            }
            avatarPicker?.classList.add("hidden");
            saveAvatarBtn?.classList.add("hidden");
            return;
        } catch (error) {
            if (profileNameLine) {
                profileNameLine.textContent = error.message || "Khong tai duoc profile";
            }
        }
    }

    if (session.guest) {
        const u = session.user || {};
        renderInfoLines({ ...u, rankTier: "Guest" });
        if (avatarPreview) {
            avatarPreview.textContent = String(u.avatar || "ðŸ§‘");
        }
        applyRankFrame(u);
        renderAvatarPicker(String(u.avatar || "ðŸ§‘"));
        if (achievementSummary) {
            achievementSummary.textContent = "Tai khoan khach khong mo khoa thanh tuu.";
        }
        if (renameInput) {
            renameInput.disabled = true;
        }
        if (renameBtn) {
            renameBtn.disabled = true;
        }
        setRenameStatus("Tai khoan khach khong doi ten duoc.", true);
        saveAvatarBtn?.addEventListener("click", () => {
            const selected = avatarPicker?.querySelector(".avatar-option.active")?.textContent || "ðŸ§‘";
            const updated = getSession();
            if (!updated) {
                return;
            }
            updated.user = { ...(updated.user || {}), avatar: selected };
            saveSession(updated);
            window.location.reload();
        });
        return;
    }

    try {
        const me = await getMe(session.token);
        saveSession({ ...session, user: me.user });
        const u = me.user;
        if (renameInput) {
            renameInput.value = String(u.username || "");
        }
        renderInfoLines(u);
        if (avatarPreview) {
            avatarPreview.textContent = String(u.avatar || "ðŸ™‚");
        }
        applyRankFrame(u);
        renderAvatarPicker(String(u.avatar || "ðŸ™‚"));

        saveAvatarBtn?.addEventListener("click", async () => {
            const selected = avatarPicker?.querySelector(".avatar-option.active")?.textContent || "ðŸ™‚";
            const updatedProfile = await updateProfile(session.token, { avatar: selected });
            saveSession({ ...session, user: updatedProfile.user });
            window.location.reload();
        });

        renameBtn?.addEventListener("click", async () => {
            const nextUsername = String(renameInput?.value || "").trim();
            if (nextUsername.length < 3 || nextUsername.length > 24) {
                setRenameStatus("Ten moi phai tu 3 den 24 ky tu.", true);
                return;
            }
            if (nextUsername === String(u.username || "")) {
                setRenameStatus("Ten moi trung voi ten hien tai.", true);
                return;
            }

            try {
                const updatedProfile = await updateProfile(session.token, { username: nextUsername });
                const latest = getSession() || session;
                saveSession({ ...latest, user: updatedProfile.user });
                setRenameStatus("Da doi ten thanh cong.");
                window.location.reload();
            } catch (error) {
                setRenameStatus(error.message || "Doi ten that bai", true);
            }
        });

        if (achievementSummary) {
            const achievementData = await getAchievements(session.token);
            const items = achievementData.items || [];
            const done = items.filter((item) => item.completed).length;
            achievementSummary.textContent = `Thanh tuu: ${done}/${items.length} da hoan thanh.`;
        }
    } catch (error) {
        if (profileNameLine) {
            profileNameLine.textContent = error.message || "Khong tai duoc profile";
        }
    }
}

document.getElementById("toMissionsBtn")?.addEventListener("click", () => {
    window.location.href = "/missions.html";
});

document.getElementById("toSettingsBtn")?.addEventListener("click", () => {
    window.location.href = "/settings.html";
});

init();


