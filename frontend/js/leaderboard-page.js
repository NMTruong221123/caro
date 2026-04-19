import { getLeaderboard, getMe } from "./api.js";
import { renderLeaderboard } from "./ui.js";
import { getSession, requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: true });
initTopbar();

const target = document.getElementById("leaderboard");
const selfRankText = document.getElementById("selfRankText");
let meId = null;

async function resolveMeId() {
    if (!session) {
        return null;
    }
    if (session.guest) {
        return null;
    }
    try {
        const me = await getMe(session.token);
        return Number(me.user?.id);
    } catch (_error) {
        return Number(getSession()?.user?.id);
    }
}

function buildSelfRankLine(kind, items) {
    if (!selfRankText) {
        return;
    }
    if (session?.guest) {
        selfRankText.textContent = "Tai khoan khach khong co thu hang BXH online.";
        return;
    }

    const idx = items.findIndex((item) => Number(item.id) === Number(meId));
    if (idx < 0) {
        selfRankText.textContent = "Top cua ban: Ngoai top 100";
        return;
    }

    const user = items[idx];
    const rankNo = idx + 1;
    if (kind === "ai") {
        selfRankText.textContent = `Top cua ban: #${rankNo} | ${user.wins_vs_ai || 0} thang voi may`;
        return;
    }
    if (kind === "rank") {
        selfRankText.textContent = `Top cua ban: #${rankNo} | ${user.displayTier || user.rank_tier} ${user.division || "V"}-${(user.starsInDivision ?? 0) + 1}*`;
        return;
    }
    selfRankText.textContent = `Top cua ban: #${rankNo} | ${user.wins_vs_room || 0} thang phong`;
}

async function load(kind) {
    try {
        const data = await getLeaderboard(100, kind);
        const items = data.items || [];
        renderLeaderboard(target, items, kind, (item) => {
            const targetId = Number(item.id);
            if (!Number.isFinite(targetId)) {
                return;
            }
            const params = new URLSearchParams();
            params.set("userId", String(targetId));
            params.set("source", "leaderboard");
            params.set("kind", kind);
            if (kind === "rank" && item.rankPosition) {
                params.set("rankPos", String(item.rankPosition));
            }
            window.location.href = `/profile.html?${params.toString()}`;
        });
        buildSelfRankLine(kind, items);
    } catch (error) {
        target.textContent = error.message || "Khong tai duoc BXH";
    }
}

document.getElementById("tabAi")?.addEventListener("click", () => load("ai"));
document.getElementById("tabRoom")?.addEventListener("click", () => load("room"));
document.getElementById("tabRank")?.addEventListener("click", () => load("rank"));
document.getElementById("backHomeBtn")?.addEventListener("click", () => {
    window.location.href = "/home.html";
});

resolveMeId().then((id) => {
    meId = id;
    const params = new URLSearchParams(window.location.search);
    const initialKind = (params.get("kind") || "room").toLowerCase();
    load(["ai", "room", "rank"].includes(initialKind) ? initialKind : "room");
});


