"""Shared Texas Hold'em / Omaha / Seven-Card Stud hand logic.

Cards are (rank, suit) tuples, e.g. ('A', '♠'). One evaluator powers all variants.
"""

from __future__ import annotations

import random
from collections import Counter
from itertools import combinations

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RVAL = {r: i + 2 for i, r in enumerate(RANKS)}

HAND_NAMES = [
    'High Card', 'One Pair', 'Two Pair', 'Three of a Kind',
    'Straight', 'Flush', 'Full House', 'Four of a Kind', 'Straight Flush'
]


def fmt_hand(cards):
    return ' '.join(f"{r}{s}" for r, s in cards) if cards else '—'


def evaluate(five):
    """Score exactly five cards. Returns (category, tiebreakers) — bigger wins."""
    vals = sorted([RVAL[c[0]] for c in five], reverse=True)
    suits = [c[1] for c in five]
    flush = len(set(suits)) == 1
    straight = vals == list(range(vals[0], vals[0] - 5, -1)) or vals == [14, 5, 4, 3, 2]
    if vals == [14, 5, 4, 3, 2]:
        vals = [5, 4, 3, 2, 1]
    cnt = Counter(vals)
    groups = sorted(cnt.items(), key=lambda x: (x[1], x[0]), reverse=True)
    gv = [g[0] for g in groups]
    gc = [g[1] for g in groups]
    if straight and flush: return (8, vals)
    if gc[0] == 4:         return (7, gv)
    if gc[:2] == [3, 2]:   return (6, gv)
    if flush:              return (5, vals)
    if straight:           return (4, vals)
    if gc[0] == 3:         return (3, gv)
    if gc[:2] == [2, 2]:   return (2, gv)
    if gc[0] == 2:         return (1, gv)
    return (0, vals)


def best_hand(cards):
    """Best five-card hand from any number of cards (Hold'em and Stud)."""
    best = max(combinations(tuple(cards), 5), key=evaluate)
    return list(best), evaluate(list(best))


def best_omaha_hand(hole_cards, community):
    """Omaha rule: exactly two hole cards plus exactly three community cards."""
    candidates = (
        tuple(hole) + tuple(board)
        for hole in combinations(tuple(hole_cards), 2)
        for board in combinations(tuple(community), 3)
    )
    best = max(candidates, key=evaluate)
    return list(best), evaluate(list(best))


def new_deck():
    deck = [(rank, suit) for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    return deck


def variant_key(value: str) -> str | None:
    """Normalize a user-supplied variant name to holdem/omaha/stud."""
    value = (value or '').strip().lower().replace(' ', '').replace('-', '').replace("'", '')
    aliases = {
        'holdem': 'holdem', 'texas': 'holdem', 'texasholdem': 'holdem',
        'omaha': 'omaha',
        'stud': 'stud', 'sevenstud': 'stud', '7stud': 'stud',
        'sevencardstud': 'stud', '7cardstud': 'stud',
    }
    return aliases.get(value)
