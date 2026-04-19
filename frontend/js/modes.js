import { requireSession } from "./session.js";
import { getActiveRoomSession } from "./api.js";
import { initTopbar } from "./topbar.js?v=20260419n";

const session = requireSession({ allowGuest: true });
initTopbar();
const resumeRoomBtn = document.getElementById("resumeRoomBtn");

const rankHint = document.getElementById("rankHint");
if (session?.guest && rankHint) {
    rankHint.textContent = "Tai khoan khach khong choi duoc rank.";
}

document.getElementById("playAiBtn")?.addEventListener("click", () => {
    window.location.href = "/play.html?mode=ai";
});

document.getElementById("playMultiBtn")?.addEventListener("click", () => {
    window.location.href = "/play.html?mode=multi";
});

document.getElementById("roomBtn")?.addEventListener("click", () => {
    if (session?.guest) {
        alert("Che do khach khong vao duoc phong online.");
        return;
    }
    window.location.href = "/room.html";
});

document.getElementById("quickJoinRoomBtn")?.addEventListener("click", () => {
    if (session?.guest) {
        alert("Che do khach khong vao duoc phong online.");
        return;
    }
    const roomCodeInput = document.getElementById("quickRoomCode");
    const code = String(roomCodeInput?.value || "").trim().toUpperCase();
    if (!code) {
        alert("Nhap ID phong truoc khi vao.");
        return;
    }
    window.location.href = `/room.html?code=${encodeURIComponent(code)}`;
});

document.getElementById("rankBtn")?.addEventListener("click", () => {
    if (session?.guest) {
        alert("Che do khach khong choi rank.");
        return;
    }
    window.location.href = "/rank.html";
});

if (!session?.guest && resumeRoomBtn) {
    getActiveRoomSession(session.token)
        .then((data) => {
            const active = data?.session;
            if (!active?.room?.code) {
                return;
            }
            const roomType = String(active.room.roomType || "casual").toLowerCase();
            resumeRoomBtn.classList.remove("hidden");
            resumeRoomBtn.addEventListener("click", () => {
                if (roomType === "ranked") {
                    window.location.href = "/rank.html";
                    return;
                }
                window.location.href = `/room.html?code=${encodeURIComponent(String(active.room.code || ""))}`;
            });
        })
        .catch(() => {
            // No active room, keep button hidden.
        });
}

document.getElementById("backHomeBtn")?.addEventListener("click", () => {
    window.location.href = "/home.html";
});


