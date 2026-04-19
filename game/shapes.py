import random
from typing import Dict, List

MULTI_PLAYER_TOKENS: List[Dict[str, str]] = [
    {"shape": "square", "color": "#ef4444", "name": "Nguoi choi 1"},
    {"shape": "triangle", "color": "#3b82f6", "name": "Nguoi choi 2"},
    {"shape": "rectangle", "color": "#f59e0b", "name": "Nguoi choi 3"},
    {"shape": "circle", "color": "#10b981", "name": "Nguoi choi 4"},
]

AI_TOKENS: List[Dict[str, str]] = [
    {"shape": "x", "color": "#0284c7", "name": "Nguoi choi"},
    {"shape": "o", "color": "#ea580c", "name": "May"},
]

ICON_TOKENS: List[str] = [
    "🐶", "🐱", "🐭", "🐹", "🐰", "🐻", "🐼", "🐨", "🐯", "🦁", "🐮", "🐷", "🐽",
    "🍏", "🍎", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍈", "🍒", "🍑", "🍍", "🍅", "🍆",
]


def get_random_icon_tokens(player_count: int) -> List[Dict[str, str]]:
    if player_count > len(ICON_TOKENS):
        raise ValueError("Khong du icon de phan phoi cho tat ca nguoi choi")

    picked = random.sample(ICON_TOKENS, k=player_count)
    return [
        {
            "shape": "icon",
            "icon": icon,
            "color": "#e2e8f0",
            "name": f"Nguoi choi {index + 1}",
        }
        for index, icon in enumerate(picked)
    ]


def get_multi_tokens(player_count: int) -> List[Dict[str, str]]:
    return MULTI_PLAYER_TOKENS[:player_count]
