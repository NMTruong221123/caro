import json
from typing import Any, Dict, List, Optional

from game.ai import choose_ai_move
from game.logic import apply_move, check_win, create_board, is_draw
from game.multiplayer import build_multiplayer_players
from game.shapes import AI_TOKENS

_EXPAND_CHUNK = 15
_EXPAND_EDGE_THRESHOLD = 1


def _is_near_board_edge(board: List[List[int]], row: int, col: int) -> bool:
    size = len(board)
    if size <= 0:
        return False
    if row < 0 or col < 0 or row >= size or col >= size:
        return False
    edge_distance = min(row, col, size - 1 - row, size - 1 - col)
    return edge_distance <= _EXPAND_EDGE_THRESHOLD


def _expand_board_all_sides(board: List[List[int]], chunk: int = _EXPAND_CHUNK) -> None:
    if not board or chunk <= 0:
        return

    for line in board:
        line[:0] = [0 for _ in range(chunk)]
        line.extend([0 for _ in range(chunk)])

    width = len(board[0])
    top_rows = [[0 for _ in range(width)] for _ in range(chunk)]
    bottom_rows = [[0 for _ in range(width)] for _ in range(chunk)]
    board[:0] = top_rows
    board.extend(bottom_rows)


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
    board = json.loads(match["board_json"])
    board_size = len(board)

    return {
        "id": match["id"],
        "mode": match["mode"],
        "ai_level": match.get("ai_level", "medium"),
        "match_type": match.get("match_type", "casual"),
        "created_by_user_id": match.get("created_by_user_id"),
        "board_size": board_size,
        "win_length": match["win_length"],
        "players_count": match["players_count"],
        "players": json.loads(match["players_json"]),
        "board": board,
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

    if _is_near_board_edge(board, row, col):
        _expand_board_all_sides(board, _EXPAND_CHUNK)
        row += _EXPAND_CHUNK
        col += _EXPAND_CHUNK

    state["board_size"] = len(board)

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
