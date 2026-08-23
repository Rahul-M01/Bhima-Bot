"""Shared chip economy store used by the economy, poker and blackjack cogs."""

from __future__ import annotations

import json
import time
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ECONOMY_FILE = LOGS_DIR / 'economy.json'

STARTING_BALANCE = 500
DAILY_BONUS = 200
DAILY_COOLDOWN_SECONDS = 86400


def load_economy(path: Path = ECONOMY_FILE) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_economy(data: dict, path: Path = ECONOMY_FILE):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _load_with_account(guild_id, user_id, path: Path) -> tuple[dict, dict]:
    """Return (full data, account), creating the account if needed."""
    data = load_economy(path)
    account = data.setdefault(str(guild_id), {}).setdefault(str(user_id), {
        'balance': STARTING_BALANCE,
        'last_daily': 0,
    })
    return data, account


def get_account(guild_id, user_id, path: Path = ECONOMY_FILE) -> dict:
    data, account = _load_with_account(str(guild_id), str(user_id), path)
    if data:
        save_economy(data, path)
    return dict(account)


def get_balance(guild_id, user_id, path: Path = ECONOMY_FILE) -> int:
    account = load_economy(path).get(str(guild_id), {}).get(str(user_id))
    if not account:
        return STARTING_BALANCE
    return int(account.get('balance', STARTING_BALANCE))


def add_chips(guild_id, user_id, amount: int, path: Path = ECONOMY_FILE) -> int:
    """Credit (or debit with a negative amount) chips and return the new balance."""
    data, account = _load_with_account(str(guild_id), str(user_id), path)
    account['balance'] += amount
    save_economy(data, path)
    return account['balance']


def spend_chips(guild_id, user_id, amount: int, path: Path = ECONOMY_FILE) -> bool:
    """Remove chips if affordable. Returns False (and changes nothing) otherwise."""
    if amount < 0:
        return False
    data, account = _load_with_account(str(guild_id), str(user_id), path)
    if account['balance'] < amount:
        return False
    account['balance'] -= amount
    save_economy(data, path)
    return True


def seconds_until_daily(last_daily: float, now: float | None = None,
                        cooldown: int = DAILY_COOLDOWN_SECONDS) -> int:
    now = time.time() if now is None else now
    remaining = int(last_daily + cooldown - now)
    return max(0, remaining)


def claim_daily(guild_id, user_id, now: float | None = None,
                path: Path = ECONOMY_FILE) -> tuple[int, int]:
    """Award the daily bonus if off cooldown. Returns (amount_claimed, retry_in_seconds)."""
    now = time.time() if now is None else now
    data, account = _load_with_account(str(guild_id), str(user_id), path)
    remaining = seconds_until_daily(account.get('last_daily', 0), now)
    if remaining > 0:
        return 0, remaining
    account['balance'] += DAILY_BONUS
    account['last_daily'] = now
    save_economy(data, path)
    return DAILY_BONUS, 0


def top_holders(guild_id, limit: int = 10, path: Path = ECONOMY_FILE) -> list[tuple[str, int]]:
    data = load_economy(path)
    accounts = data.get(str(guild_id), {})
    ranked = sorted(
        ((user_id, int(info.get('balance', 0))) for user_id, info in accounts.items()),
        key=lambda pair: pair[1], reverse=True,
    )
    return ranked[:limit]
