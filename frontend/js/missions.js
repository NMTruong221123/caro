import { getAchievements } from "./api.js";
import { requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: true });
initTopbar();
const missionList = document.getElementById("missionList");

async function init() {
    if (!session) {
        return;
    }

    if (session.guest) {
        missionList.textContent = "Tai khoan khach chua co he thong nhiem vu luu tru. Dang nhap de mo khoa.";
        return;
    }

    try {
        const data = await getAchievements(session.token);
        missionList.innerHTML = "";
        for (const item of data.items || []) {
            const row = document.createElement("div");
            row.className = "leaderboard-item";
            const done = item.completed ? "[Da dat]" : "[Dang lam]";
            row.textContent = `${done} ${item.title}: ${item.progress}/${item.target}`;
            missionList.appendChild(row);
        }
    } catch (error) {
        missionList.textContent = error.message || "Khong tai duoc thanh tuu";
    }
}

document.getElementById("backProfileBtn")?.addEventListener("click", () => {
    window.location.href = "/profile.html";
});

init();


