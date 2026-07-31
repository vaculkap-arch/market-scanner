"""Send alerts via Gmail, Telegram, and/or Discord."""

from __future__ import annotations

import json
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import requests

from .config import PROJECT_ROOT, Settings
from .signals import BullishSetup

GMAIL_SENT_PATH = PROJECT_ROOT / "config" / "gmail_sent.json"


def send_gmail(subject: str, message: str, settings: Settings) -> bool:
    if not settings.gmail_address or not settings.gmail_app_password or not settings.gmail_to:
        return False

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = settings.gmail_address
    email["To"] = settings.gmail_to
    email.set_content(message)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as smtp:
        smtp.login(settings.gmail_address, settings.gmail_app_password)
        smtp.send_message(email)

    return True


def send_telegram(message: str, settings: Settings) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": settings.telegram_chat_id, "text": message},
        timeout=15,
    )
    response.raise_for_status()
    return True


def telegram_configured(settings: Settings) -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


def should_send_gmail_for_score(score: int | None, settings: Settings) -> bool:
    """Legacy score-only check."""
    if score is None:
        return False
    return score >= settings.gmail_min_score


def _load_gmail_sent() -> dict[str, dict]:
    if not GMAIL_SENT_PATH.exists():
        return {}
    try:
        return json.loads(GMAIL_SENT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_gmail_sent(data: dict[str, dict]) -> None:
    GMAIL_SENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    GMAIL_SENT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _gmail_on_cooldown(setup: BullishSetup, settings: Settings) -> bool:
    """Skip repeat alerts for the same ticker within the cooldown window."""
    if settings.gmail_cooldown_hours <= 0:
        return False

    sent = _load_gmail_sent()
    prev = sent.get(setup.ticker)
    if not prev:
        return False

    try:
        sent_at = datetime.fromisoformat(prev["at"])
    except (KeyError, ValueError):
        return False

    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    cooldown = timedelta(hours=settings.gmail_cooldown_hours)
    if datetime.now(timezone.utc) - sent_at >= cooldown:
        return False

    prev_score = int(prev.get("score", 0))
    prev_tier = str(prev.get("tier", "C"))
    if setup.score >= prev_score + 5:
        return False
    if setup.tier != prev_tier and setup.tier in ("S", "A"):
        from .tier import tier_meets_minimum

        if tier_meets_minimum(setup.tier, prev_tier):
            return False

    return True


def record_gmail_sent(setup: BullishSetup) -> None:
    sent = _load_gmail_sent()
    sent[setup.ticker] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "score": setup.score,
        "tier": setup.tier,
    }
    _save_gmail_sent(sent)


def should_send_gmail_for_setup(setup: BullishSetup, settings: Settings) -> bool:
    from .tier import tier_meets_minimum

    if not tier_meets_minimum(setup.tier, settings.gmail_min_tier):
        return False
    if setup.score < settings.gmail_min_score:
        return False
    if setup.earnings_warning:
        return False
    if _gmail_on_cooldown(setup, settings):
        return False
    return True


def send_discord(message: str, settings: Settings) -> bool:
    if not settings.discord_webhook_url:
        return False

    response = requests.post(
        settings.discord_webhook_url,
        json={"content": message},
        timeout=15,
    )
    response.raise_for_status()
    return True


def notify(
    message: str,
    settings: Settings,
    subject: str = "Market Scanner Alert",
    *,
    gmail: bool = True,
    telegram: bool = True,
    discord: bool = True,
) -> None:
    sent = False
    errors: list[str] = []

    if gmail:
        try:
            if send_gmail(subject, message, settings):
                sent = True
        except Exception as exc:
            errors.append(f"Gmail: {exc}")

    if telegram and settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            if send_telegram(message, settings):
                sent = True
        except Exception as exc:
            errors.append(f"Telegram: {exc}")

    if discord and settings.discord_webhook_url:
        try:
            if send_discord(message, settings):
                sent = True
        except Exception as exc:
            errors.append(f"Discord: {exc}")

    if errors:
        for err in errors:
            print(f"[notify] Chyba - {err}")

    if not sent:
        print("[notify] Ziadny notifikacny kanal nie je nakonfigurovany - vypis do konzoly:")
        print(message)