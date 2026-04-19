from typing import List, Tuple

Board = List[List[int]]


def create_board(size: int) -> Board:
    return [[0 for _ in range(size)] for _ in range(size)]


def apply_move(board: Board, row: int, col: int, player: int) -> bool:
    size = len(board)
    if row < 0 or col < 0 or row >= size or col >= size:
        return False
    if board[row][col] != 0:
        return False
    board[row][col] = player
    return True


def available_moves(board: Board) -> List[Tuple[int, int]]:
    moves: List[Tuple[int, int]] = []
    for row_index, row in enumerate(board):
        for col_index, value in enumerate(row):
            if value == 0:
                moves.append((row_index, col_index))
    return moves


def is_draw(board: Board) -> bool:
    return all(cell != 0 for row in board for cell in row)


def check_win(board: Board, row: int, col: int, player: int, win_length: int = 5) -> bool:
    directions = [
        (1, 0),
        (0, 1),
        (1, 1),
        (1, -1),
    ]

    size = len(board)

    for dr, dc in directions:
        count = 1

        r, c = row + dr, col + dc
        while 0 <= r < size and 0 <= c < size and board[r][c] == player:
            count += 1
            r += dr
            c += dc

        r, c = row - dr, col - dc
        while 0 <= r < size and 0 <= c < size and board[r][c] == player:
            count += 1
            r -= dr
            c -= dc

        if count >= win_length:
            return True

    return False
