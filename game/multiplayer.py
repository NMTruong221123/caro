from typing import Dict, List

from config.settings import MAX_MULTI_PLAYERS, MIN_MULTI_PLAYERS
from game.shapes import get_multi_tokens, get_random_icon_tokens


def build_multiplayer_players(player_count: int) -> List[Dict[str, str]]:
    if player_count < MIN_MULTI_PLAYERS or player_count > MAX_MULTI_PLAYERS:
        raise ValueError("So nguoi choi khong hop le")
    return get_multi_tokens(player_count)


def build_random_icon_players(player_count: int) -> List[Dict[str, str]]:
    if player_count < MIN_MULTI_PLAYERS or player_count > MAX_MULTI_PLAYERS:
        raise ValueError("So nguoi choi khong hop le")
    return get_random_icon_tokens(player_count)
