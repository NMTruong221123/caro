function buildMarker(playerToken) {
    const marker = document.createElement("div");
    marker.className = "marker";
    marker.style.setProperty("--token-color", playerToken.color);

    if (playerToken.shape === "x" || playerToken.shape === "o") {
        marker.classList.add(`marker-${playerToken.shape}`);
        marker.textContent = playerToken.shape.toUpperCase();
        marker.style.color = playerToken.color;
        return marker;
    }

    if (playerToken.shape === "icon") {
        marker.classList.add("marker-icon");
        marker.textContent = String(playerToken.icon || "*");
        return marker;
    }

    marker.classList.add(`marker-${playerToken.shape}`);
    return marker;
}

const MIN_BOARD_ZOOM = 0.6;
const MAX_BOARD_ZOOM = 2.4;
const BOARD_ZOOM_STEP = 0.2;

function normalizeZoom(value) {
    const raw = Number(value);
    if (!Number.isFinite(raw)) {
        return 1;
    }
    return Math.max(MIN_BOARD_ZOOM, Math.min(MAX_BOARD_ZOOM, Math.round(raw * 10) / 10));
}

export function setBoardZoom(boardElement, zoom) {
    if (!boardElement) {
        return 1;
    }
    const normalized = normalizeZoom(zoom);
    boardElement.style.setProperty("--board-zoom", String(normalized));
    boardElement.dataset.zoom = String(normalized);
    return normalized;
}

export function adjustBoardZoom(boardElement, direction = 0) {
    const current = Number(boardElement?.dataset?.zoom || boardElement?.style?.getPropertyValue("--board-zoom") || 1);
    return setBoardZoom(boardElement, current + BOARD_ZOOM_STEP * Number(direction || 0));
}

export function renderLegend(legendElement, players) {
    legendElement.innerHTML = "";
    players.forEach((token, index) => {
        const item = document.createElement("div");
        item.className = "legend-item";

        const marker = buildMarker(token);
        const text = document.createElement("span");
        if (token.shape === "icon") {
            text.textContent = `P${index + 1}: ${token.icon}`;
        } else {
            text.textContent = `P${index + 1}: ${token.shape} (${token.color})`;
        }

        item.appendChild(marker);
        item.appendChild(text);
        legendElement.appendChild(item);
    });
}

export function renderBoard(boardElement, state, onCellClick) {
    boardElement.innerHTML = "";
    const rows = Array.isArray(state.board) ? state.board.length : 0;
    const cols = rows > 0 && Array.isArray(state.board[0]) ? state.board[0].length : 0;
    boardElement.style.setProperty("--cols", String(cols));
    boardElement.style.setProperty("--rows", String(rows));

    if (!boardElement.dataset.zoom) {
        setBoardZoom(boardElement, 1);
    }

    for (let row = 0; row < rows; row += 1) {
        for (let col = 0; col < cols; col += 1) {
            const cell = document.createElement("button");
            cell.type = "button";
            cell.className = "cell";
            const value = Number(state.board?.[row]?.[col] || 0);

            if (value !== 0) {
                cell.classList.add("taken");
                const token = state.players[value - 1];
                cell.appendChild(buildMarker(token));
                cell.disabled = true;
            } else {
                cell.addEventListener("click", () => onCellClick(row, col));
            }

            boardElement.appendChild(cell);
        }
    }
}

export function buildStatus(state) {
    if (state.status === "finished") {
        const roomPlayers = state.roomPlayers || [];
        const winnerInfo = roomPlayers.find((player) => Number(player.player_index) === Number(state.winner));
        if (winnerInfo?.username) {
            return `${winnerInfo.username} (P${state.winner}) thang!`;
        }
        return `Nguoi choi P${state.winner} thang!`;
    }

    if (state.status === "draw") {
        return "Hoa! Khong con nuoc di hop le.";
    }

    return `Luot cua P${state.currentPlayer}`;
}

export function renderLeaderboard(target, items, kind = "room", onSelect = null) {
    target.innerHTML = "";
    if (!items.length) {
        target.textContent = "Chua co du lieu ranking.";
        return;
    }

    items.forEach((item, index) => {
        const row = document.createElement("button");
        row.type = "button";
        row.className = "leaderboard-card";
        const avatar = String(item.avatar || "🙂");
        const tier = String(item.rank_tier || "Bronze");
        const stars = Number(item.rank_stars || 0);
        const streak = Number(item.rank_streak || 0);
        let scoreText = "";
        if (kind === "ai") {
            scoreText = `${item.wins_vs_ai} thang voi may`;
        } else if (kind === "rank") {
            scoreText = `${item.displayTier || tier} ${item.division || "V"}-${(item.starsInDivision ?? 0) + 1}* (streak ${streak})`;
        } else {
            scoreText = `${item.wins_vs_room} thang dau phong`;
        }

        row.innerHTML = `
            <div class="leaderboard-left">
                <span class="leaderboard-rank">#${index + 1}</span>
                <span class="leaderboard-avatar">${avatar}</span>
                ${item.badgeImage ? `<img src="${item.badgeImage}" class="rank-badge" alt="rank">` : ""}
                <div class="leaderboard-user">
                    <strong>${item.username}</strong>
                    <span>ID: ${item.id}</span>
                </div>
            </div>
            <div class="leaderboard-right">
                <span>${scoreText}</span>
            </div>
        `;

        if (typeof onSelect === "function") {
            row.addEventListener("click", () => onSelect(item));
        }

        target.appendChild(row);
    });
}
