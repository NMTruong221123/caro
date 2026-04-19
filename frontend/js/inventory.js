import { equipInventoryItem, getInventory } from "./api.js";
import { getSession, requireSession, saveSession } from "./session.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: true });
initTopbar();

const inventoryList = document.getElementById("inventoryList");

function renderItems(items) {
    if (!inventoryList) {
        return;
    }
    inventoryList.innerHTML = "";
    if (!items.length) {
        inventoryList.textContent = "Tui do dang trong. Hay nhan thuong trong Thu.";
        return;
    }

    items.forEach((item) => {
        const payload = item.item_payload || {};
        const row = document.createElement("div");
        row.className = "inventory-item";
        row.innerHTML = `
            <div>
                <strong>${item.item_name}</strong>
                <p class="small-status">Loai: ${item.item_type} ${item.equipped ? "| Dang deo" : ""}</p>
                <p class="small-status">${payload.display || ""}</p>
            </div>
            <div class="inline-actions">
                ${payload.image ? `<img src="${payload.image}" class="rank-badge" alt="badge">` : ""}
                <button type="button" ${item.equipped ? "disabled" : ""}>${item.equipped ? "Dang deo" : "Deo"}</button>
            </div>
        `;
        row.querySelector("button")?.addEventListener("click", async () => {
            const result = await equipInventoryItem(session.token, item.item_code);
            const current = getSession();
            if (current) {
                saveSession({ ...current, user: result.user });
            }
            await load();
        });
        inventoryList.appendChild(row);
    });
}

async function load() {
    if (!session) {
        return;
    }

    if (session.guest) {
        if (inventoryList) {
            inventoryList.textContent = "Tai khoan khach chua co tui do. Dang nhap de nhan va trang bi vat pham.";
        }
        return;
    }

    try {
        const data = await getInventory(session.token);
        renderItems(data.items || []);
    } catch (error) {
        if (inventoryList) {
            inventoryList.textContent = error.message || "Khong tai duoc tui do";
        }
    }
}

document.getElementById("backHomeBtn")?.addEventListener("click", () => {
    window.location.href = "/home.html";
});

load();


