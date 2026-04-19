from game.ai import choose_ai_move
from game.logic import create_board


def test_ai_blocks_winning_line():
    board = create_board(10)
    board[2][0] = 1
    board[2][1] = 1
    board[2][2] = 1
    board[2][3] = 1

    move = choose_ai_move(board, ai_player=2, human_player=1, win_length=5)
    assert move == (2, 4)
