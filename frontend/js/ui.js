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
    boardElement.style.setProperty("--size", String(state.boardSize));

    for (let row = 0; row < state.boardSize; row += 1) {
        for (let col = 0; col < state.boardSize; col += 1) {
            const cell = document.createElement("button");
            cell.type = "button";
            cell.className = "cell";
            const value = state.board[row][col];

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
