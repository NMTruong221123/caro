import json
from typing import Any, Dict, List, Optional

from game.ai import choose_ai_move
from game.logic import apply_move, check_win, create_board, is_draw
from game.multiplayer import build_multiplayer_players
from game.shapes import AI_TOKENS


def start_game_state(mode: str, board_size: int, players_count: int) -> Dict[str, Any]:
    if mode == "ai":
        players = AI_TOKENS
        players_count = 2
    else:
        players = build_multiplayer_players(players_count)

    return {
        "players": players,
        "players_count": players_count,
        "board": create_board(board_size),
        "current_player": 1,
    }


def parse_match(match: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": match["id"],
        "mode": match["mode"],
        "ai_level": match.get("ai_level", "medium"),
        "match_type": match.get("match_type", "casual"),
        "created_by_user_id": match.get("created_by_user_id"),
        "board_size": match["board_size"],
        "win_length": match["win_length"],
        "players_count": match["players_count"],
        "players": json.loads(match["players_json"]),
        "board": json.loads(match["board_json"]),
        "current_player": match["current_player"],
        "status": match["status"],
        "winner": match["winner"],
    }


def apply_player_move(
    state: Dict[str, Any],
    row: int,
    col: int,
) -> Optional[Dict[str, Any]]:
    player = state["current_player"]
    board = state["board"]

    if not apply_move(board, row, col, player):
        return None

    token = state["players"][player - 1]
    move_result = {
        "player": player,
        "row": row,
        "col": col,
        "shape": token["shape"],
        "color": token["color"],
    }

    if check_win(board, row, col, player, state["win_length"]):
        state["status"] = "finished"
        state["winner"] = player
    elif is_draw(board):
        state["status"] = "draw"
        state["winner"] = None
    else:
        state["current_player"] = (player % state["players_count"]) + 1

    return move_result
def maybe_make_ai_move(
    state: Dict[str, Any],
    learned_heatmap: Optional[dict[tuple[int, int], int]] = None,
) -> Optional[Dict[str, Any]]:
    if state["mode"] != "ai" or state["status"] != "playing":
        return None

    if state["current_player"] != 2:
        return None

    ai_move = choose_ai_move(
        board=state["board"],
        ai_player=2,
        human_player=1,
        win_length=state["win_length"],
        difficulty=state.get("ai_level", "medium"),
        learned_heatmap=learned_heatmap,
    )
    if ai_move is None:
        state["status"] = "draw"
        state["winner"] = None
        return None

    row, col = ai_move
    return apply_player_move(state, row, col)
