import { clearSession, getSession } from "./session.js";

function resolveFrameCode(user) {
    const selected = String(user.selectedFrameCode || "").trim();
    if (selected.startsWith("frame_")) {
        return selected.replace("frame_", "");
    }
    const visualCode = String(user.rankVisual?.badgeCode || "").trim();
    if (visualCode) {
        return visualCode;
    }
    const tier = String(user.rankTier || "bronze").toLowerCase();
    if (tier === "master") {
        return "master";
    }
    if (tier === "platinum") {
        return "platinum";
    }
    if (tier === "diamond") {
        return "diamond";
    }
    if (tier === "silver") {
        return "silver";
    }
    return "bronze";
}

export function initTopbar(options = {}) {
    const {
        showProfile = true,
        showHome = true,
        showHistory = true,
        showMissions = true,
        showLeaderboard = true,
        showMailbox = true,
        showInventory = true,
        showAdmin = true,
    } = options;

    const session = getSession();
    if (!session || document.getElementById("globalTopbar")) {
        return;
    }

    const user = session.user || {};
    const avatar = String(user.avatar || "🧑");
    const username = String(user.username || "Nguoi choi");
    const frameCode = resolveFrameCode(user);
    const rankImage = String(user.rankVisual?.badgeImage || "");
    const rankDisplay = String(user.rankVisual?.displayTier || user.rankTier || "Dong");
    const rankDivision = String(user.rankVisual?.division || "V");
    const starsInDivision = Number(user.rankVisual?.starsInDivision ?? 0) + 1;

    const topbar = document.createElement("header");
    topbar.className = "topbar";
    topbar.id = "globalTopbar";

    topbar.innerHTML = `
        <div class="topbar-brand">Co Caro</div>
        <div class="topbar-actions">
            ${showHome ? '<button type="button" class="topbar-link" data-nav="home">Trang chu</button>' : ""}
            ${showHistory ? '<button type="button" class="topbar-link" data-nav="history">Lich su</button>' : ""}
            ${showLeaderboard ? '<button type="button" class="topbar-link" data-nav="leaderboard">BXH</button>' : ""}
            ${showMissions ? '<button type="button" class="topbar-link" data-nav="missions">Nhiem vu</button>' : ""}
            ${showMailbox ? '<button type="button" class="topbar-link" data-nav="mailbox">Thu</button>' : ""}
            ${showInventory ? '<button type="button" class="topbar-link" data-nav="inventory">Tui do</button>' : ""}
            ${showAdmin ? '<button type="button" class="topbar-link" data-nav="admin">Admin</button>' : ""}
            ${showProfile ? '<button type="button" class="avatar-chip rank-frame-' + frameCode + '" id="avatarChip"><span class="avatar-dot rank-frame-' + frameCode + '">' + avatar + '</span><span class="avatar-name">' + username + '</span></button>' : ""}
        </div>
    `;

    document.body.prepend(topbar);

    const navMap = {
        home: "/home.html",
        history: "/history.html",
        leaderboard: "/leaderboard.html",
        missions: "/missions.html",
        mailbox: "/mailbox.html",
        inventory: "/inventory.html",
        admin: "/admin.html",
    };

    topbar.querySelectorAll(".topbar-link").forEach((button) => {
        button.addEventListener("click", () => {
            const target = button.getAttribute("data-nav") || "";
            const href = navMap[target];
            if (href) {
                window.location.href = href;
            }
        });
    });

    const avatarChip = document.getElementById("avatarChip");
    if (!avatarChip) {
        return;
    }

    const menu = document.createElement("div");
    menu.className = "profile-menu hidden";
    menu.innerHTML = `
        <div class="profile-menu-header">
            <div class="avatar-preview rank-frame-${frameCode}">${avatar}</div>
            <div>
                <div class="profile-name">${username}</div>
                <div class="profile-rank">${rankDisplay} ${rankDivision}-${starsInDivision}*</div>
            </div>
        </div>
        ${rankImage ? `<img src="${rankImage}" alt="rank" class="rank-badge large">` : ""}
        <button type="button" data-action="profile">Xem profile</button>
        <button type="button" data-action="logout" class="danger">Dang xuat</button>
    `;
    topbar.appendChild(menu);

    avatarChip.addEventListener("click", () => {
        menu.classList.toggle("hidden");
    });

    menu.querySelector('[data-action="profile"]')?.addEventListener("click", () => {
        window.location.href = "/profile.html";
    });

    menu.querySelector('[data-action="logout"]')?.addEventListener("click", () => {
        clearSession();
        window.location.href = "/";
    });

    window.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }
        if (!menu.contains(target) && !avatarChip.contains(target)) {
            menu.classList.add("hidden");
        }
    });
}
