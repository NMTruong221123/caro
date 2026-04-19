import { loginUser, registerUser } from "./api.js";
import { createGuestSession, getSession, saveSession } from "./session.js";

const usernameInput = document.getElementById("usernameInput");
const passwordInput = document.getElementById("passwordInput");
const registerBtn = document.getElementById("registerBtn");
const loginBtn = document.getElementById("loginBtn");
const guestBtn = document.getElementById("guestBtn");
const authStatus = document.getElementById("authStatus");

function setStatus(message, isError = false) {
    if (!authStatus) {
        return;
    }
    authStatus.textContent = message;
    authStatus.style.color = isError ? "#fecaca" : "#c7d2fe";
}

function goHome() {
    window.location.href = "/home.html";
}

const existing = getSession();
if (existing) {
    goHome();
}

registerBtn?.addEventListener("click", async () => {
    try {
        const payload = {
            username: String(usernameInput?.value || "").trim(),
            password: String(passwordInput?.value || "").trim(),
        };
        const result = await registerUser(payload);
        setStatus(`Dang ky thanh cong: ${result.user.username}`);
    } catch (error) {
        setStatus(error.message || "Dang ky that bai", true);
    }
});

loginBtn?.addEventListener("click", async () => {
    try {
        const payload = {
            username: String(usernameInput?.value || "").trim(),
            password: String(passwordInput?.value || "").trim(),
        };
        const result = await loginUser(payload);
        saveSession({
            guest: false,
            token: result.token,
            user: result.user,
        });
        goHome();
    } catch (error) {
        setStatus(error.message || "Dang nhap that bai", true);
    }
});

guestBtn?.addEventListener("click", () => {
    createGuestSession();
    goHome();
});
