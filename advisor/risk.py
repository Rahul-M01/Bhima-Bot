from __future__ import annotations

from dataclasses import dataclass

from advisor.market import min_dollar_volume


@dataclass(frozen=True)
class RiskProfile:
    score: int
    label: str
    emoji: str
    ann_vol: float
    max_dd_1y: float
    atr_pct: float
    max_position_pct: float


LABELS = {
    1: ("Very Low", "\U0001F7E2"),
    2: ("Low", "\U0001F7E9"),
    3: ("Moderate", "\U0001F7E8"),
    4: ("High", "\U0001F7E0"),
    5: ("Extreme", "\U0001F534"),
}

MAX_POSITION_PCT = {1: 10.0, 2: 8.0, 3: 5.0, 4: 3.0, 5: 1.0}


def assess(
    ann_vol: float,
    max_dd_1y: float,
    atr_value: float,
    last_close: float,
    dollar_volume: float = float("nan"),
    ticker: str = "",
) -> RiskProfile:
    points = 0
    if ann_vol == ann_vol:
        if ann_vol > 0.80:
            points += 2
        elif ann_vol > 0.50:
            points += 1
    if max_dd_1y == max_dd_1y:
        if max_dd_1y < -0.50:
            points += 2
        elif max_dd_1y < -0.30:
            points += 1
    atr_pct = atr_value / last_close if last_close else float("nan")
    if atr_pct == atr_pct:
        if atr_pct > 0.06:
            points += 1
        elif atr_pct > 0.035:
            points += 0.5
    floor = min_dollar_volume(ticker) * 2
    if dollar_volume == dollar_volume and dollar_volume < floor:
        points += 1
    score = min(max(int(round(points)) + 1, 1), 5)
    label, emoji = LABELS[score]
    return RiskProfile(
        score=score,
        label=label,
        emoji=emoji,
        ann_vol=ann_vol,
        max_dd_1y=max_dd_1y,
        atr_pct=atr_pct,
        max_position_pct=MAX_POSITION_PCT[score],
    )
