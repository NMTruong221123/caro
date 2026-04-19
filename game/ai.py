import random
from math import inf
from typing import Dict, List, Optional, Tuple

from game.logic import available_moves, check_win

Board = List[List[int]]


def _difficulty_depth(level: str) -> int:
    if level == "hard":
        return 3
    if level == "medium":
        return 2
    return 1


def _try_find_finishing_move(board: Board, player: int, win_length: int) -> Optional[Tuple[int, int]]:
    for row, col in available_moves(board):
        board[row][col] = player
        can_win = check_win(board, row, col, player, win_length)
        board[row][col] = 0
        if can_win:
            return row, col
    return None


def _has_neighbor(board: Board, row: int, col: int) -> bool:
    size = len(board)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            if 0 <= nr < size and 0 <= nc < size and board[nr][nc] != 0:
                return True
    return False


def _candidate_moves(board: Board, max_candidates: int = 12) -> List[Tuple[int, int]]:
    size = len(board)
    center = size // 2

    stones = sum(1 for row in board for cell in row if cell != 0)
    if stones == 0:
        return [(center, center)]

    candidates: List[Tuple[int, int, int]] = []
    for row, col in available_moves(board):
        if not _has_neighbor(board, row, col):
            continue
        score = -abs(center - row) - abs(center - col)
        candidates.append((score, row, col))

    candidates.sort(reverse=True)
    return [(row, col) for _, row, col in candidates[:max_candidates]]


def _score_window(window: List[int], ai_player: int, human_player: int, win_length: int) -> int:
    ai_count = window.count(ai_player)
    human_count = window.count(human_player)
    empty_count = window.count(0)

    if ai_count == win_length:
        return 1_000_000
    if human_count == win_length:
        return -1_000_000

    if ai_count > 0 and human_count > 0:
        return 0

    if ai_count == win_length - 1 and empty_count == 1:
        return 15_000
    if human_count == win_length - 1 and empty_count == 1:
        return -18_000

    if ai_count == win_length - 2 and empty_count == 2:
        return 1_800
    if human_count == win_length - 2 and empty_count == 2:
        return -2_200

    if ai_count == win_length - 3 and empty_count == 3:
        return 260
    if human_count == win_length - 3 and empty_count == 3:
        return -320

    return 0


def _evaluate_board(board: Board, ai_player: int, human_player: int, win_length: int) -> int:
    size = len(board)
    score = 0

    for row in range(size):
        for col in range(size):
            if col + win_length <= size:
                window = [board[row][col + k] for k in range(win_length)]
                score += _score_window(window, ai_player, human_player, win_length)
            if row + win_length <= size:
                window = [board[row + k][col] for k in range(win_length)]
                score += _score_window(window, ai_player, human_player, win_length)
            if row + win_length <= size and col + win_length <= size:
                window = [board[row + k][col + k] for k in range(win_length)]
                score += _score_window(window, ai_player, human_player, win_length)
            if row + win_length <= size and col - win_length + 1 >= 0:
                window = [board[row + k][col - k] for k in range(win_length)]
                score += _score_window(window, ai_player, human_player, win_length)

    return score


def _minimax(
    board: Board,
    depth: int,
    is_maximizing: bool,
    ai_player: int,
    human_player: int,
    win_length: int,
    alpha: float,
    beta: float,
) -> float:
    candidate_moves = _candidate_moves(board)
    if depth == 0 or not candidate_moves:
        return float(_evaluate_board(board, ai_player, human_player, win_length))

    if is_maximizing:
        best_score = -inf
        for row, col in candidate_moves:
            board[row][col] = ai_player
            if check_win(board, row, col, ai_player, win_length):
                board[row][col] = 0
                return 1_000_000.0
            score = _minimax(
                board,
                depth - 1,
                False,
                ai_player,
                human_player,
                win_length,
                alpha,
                beta,
            )
            board[row][col] = 0
            best_score = max(best_score, score)
            alpha = max(alpha, best_score)
            if beta <= alpha:
                break
        return best_score

    best_score = inf
    for row, col in candidate_moves:
        board[row][col] = human_player
        if check_win(board, row, col, human_player, win_length):
            board[row][col] = 0
            return -1_000_000.0
        score = _minimax(
            board,
            depth - 1,
            True,
            ai_player,
            human_player,
            win_length,
            alpha,
            beta,
        )
        board[row][col] = 0
        best_score = min(best_score, score)
        beta = min(beta, best_score)
        if beta <= alpha:
            break
    return best_score


def choose_ai_move(
    board: Board,
    ai_player: int,
    human_player: int,
    win_length: int,
    difficulty: str = "medium",
    learned_heatmap: Optional[Dict[Tuple[int, int], int]] = None,
) -> Optional[Tuple[int, int]]:
    winning_move = _try_find_finishing_move(board, ai_player, win_length)
    if winning_move:
        return winning_move

    blocking_move = _try_find_finishing_move(board, human_player, win_length)
    if blocking_move and difficulty != "easy":
        return blocking_move

    candidate_moves = _candidate_moves(board)
    if not candidate_moves:
        all_moves = available_moves(board)
        return random.choice(all_moves) if all_moves else None

    if difficulty == "easy":
        return random.choice(candidate_moves[: min(6, len(candidate_moves))])

    search_depth = _difficulty_depth(difficulty)
    best_score = -inf
    best_moves: List[Tuple[int, int]] = []

    for row, col in candidate_moves:
        board[row][col] = ai_player
        score = _minimax(
            board,
            search_depth - 1,
            False,
            ai_player,
            human_player,
            win_length,
            -inf,
            inf,
        )
        board[row][col] = 0

        if learned_heatmap:
            score += min(1200.0, float(learned_heatmap.get((row, col), 0) * 10))

        if score > best_score:
            best_score = score
            best_moves = [(row, col)]
        elif score == best_score:
            best_moves.append((row, col))

    if not best_moves:
        return random.choice(candidate_moves)
    return random.choice(best_moves)
