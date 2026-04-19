from game.logic import apply_move, check_win, create_board


def test_apply_move_valid_and_invalid():
    board = create_board(5)
    assert apply_move(board, 1, 1, 1)
    assert not apply_move(board, 1, 1, 2)


def test_check_win_horizontal():
    board = create_board(10)
    row = 4
    for col in range(5):
        board[row][col] = 1

    assert check_win(board, row, 4, 1, 5)
