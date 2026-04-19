import { claimAllMailboxItems, claimMailboxItem, getMailbox } from "./api.js";
import { requireSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: false });
initTopbar();

const mailList = document.getElementById("mailList");
const claimAllBtn = document.getElementById("claimAllBtn");
let allItems = [];
let activeFilter = "all";

function applyFilter(items) {
    if (activeFilter === "title") {
        return items.filter((mail) => String(mail.item_type || "") === "title");
    }
    if (activeFilter === "frame") {
        return items.filter((mail) => String(mail.item_type || "") === "frame");
    }
    return items;
}

function setFilterState(filter) {
    activeFilter = filter;
    document.getElementById("filterAllBtn")?.classList.toggle("ghost-btn", filter !== "all");
    document.getElementById("filterTitleBtn")?.classList.toggle("ghost-btn", filter !== "title");
    document.getElementById("filterFrameBtn")?.classList.toggle("ghost-btn", filter !== "frame");
    renderMail(applyFilter(allItems));
}

function renderMail(items) {
    if (!mailList) {
        return;
    }
    mailList.innerHTML = "";
    if (!items.length) {
        mailList.textContent = "Chua co thu moi.";
        return;
    }

    items.forEach((mail) => {
        const row = document.createElement("div");
        row.className = "mail-item";
        const payload = mail.item_payload || {};
        row.innerHTML = `
            <div class="mail-main">
                <strong>${mail.title}</strong>
                <p>${mail.content}</p>
                ${payload.image ? `<img src="${payload.image}" class="rank-badge" alt="rank badge">` : ""}
                <span class="small-status">${mail.item_name || ""}</span>
            </div>
            <button type="button" ${mail.claimed ? "disabled" : ""}>${mail.claimed ? "Da nhan" : "Nhan"}</button>
        `;
        row.querySelector("button")?.addEventListener("click", async () => {
            await claimMailboxItem(session.token, mail.id);
            await load();
        });
        mailList.appendChild(row);
    });
}

async function load() {
    try {
        const data = await getMailbox(session.token);
        allItems = data.items || [];
        renderMail(applyFilter(allItems));
    } catch (error) {
        if (mailList) {
            mailList.textContent = error.message || "Khong tai duoc thu";
        }
    }
}

claimAllBtn?.addEventListener("click", async () => {
    await claimAllMailboxItems(session.token);
    await load();
});

document.getElementById("filterAllBtn")?.addEventListener("click", () => setFilterState("all"));
document.getElementById("filterTitleBtn")?.addEventListener("click", () => setFilterState("title"));
document.getElementById("filterFrameBtn")?.addEventListener("click", () => setFilterState("frame"));

document.getElementById("backHomeBtn")?.addEventListener("click", () => {
    window.location.href = "/home.html";
});

load();


