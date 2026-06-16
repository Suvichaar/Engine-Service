"""Broadcast service — fans out a story link to recipients across channels.

Providers are pluggable. If env credentials are not configured the adapter
records the intent and returns a ``queued`` outcome; once credentials are
wired in (Meta WhatsApp Cloud API, SMTP/SES), the same adapter performs
real delivery without touching call sites.
"""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterable, List, Optional

import httpx


logger = logging.getLogger(__name__)


@dataclass
class DeliveryOutcome:
    channel: str
    recipient: str
    status: str  # "sent" | "failed" | "queued"
    error: Optional[str] = None


@dataclass(frozen=True)
class RecipientRef:
    """A normalized recipient with whatever contact methods are known."""

    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


# ── WhatsApp adapter (Meta Cloud API) ───────────────────────────────────────


class WhatsAppAdapter:
    """Send a story-link message via Meta Cloud API when credentials are set.

    Env vars used (all optional — missing creds => `queued` outcomes):
        WHATSAPP_PHONE_ID         the WABA phone number id
        WHATSAPP_ACCESS_TOKEN     long-lived access token
        WHATSAPP_TEMPLATE_NAME    approved template name (defaults to
                                  "story_broadcast")
        WHATSAPP_TEMPLATE_LANG    template language (defaults to "en")
    """

    def __init__(self) -> None:
        self.phone_id = (os.getenv("WHATSAPP_PHONE_ID") or "").strip()
        self.access_token = (os.getenv("WHATSAPP_ACCESS_TOKEN") or "").strip()
        self.template = (os.getenv("WHATSAPP_TEMPLATE_NAME") or "story_broadcast").strip()
        self.language = (os.getenv("WHATSAPP_TEMPLATE_LANG") or "en").strip()

    @property
    def configured(self) -> bool:
        return bool(self.phone_id and self.access_token)

    def send_many(
        self,
        recipients: Iterable[RecipientRef],
        *,
        story_url: str,
        message: Optional[str],
    ) -> List[DeliveryOutcome]:
        outcomes: List[DeliveryOutcome] = []
        if not self.configured:
            for r in recipients:
                if not r.phone:
                    continue
                outcomes.append(
                    DeliveryOutcome(
                        channel="whatsapp",
                        recipient=r.phone,
                        status="queued",
                        error="WhatsApp credentials not configured; queued.",
                    )
                )
            return outcomes

        url = f"https://graph.facebook.com/v20.0/{self.phone_id}/messages"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        for r in recipients:
            if not r.phone:
                continue
            payload = {
                "messaging_product": "whatsapp",
                "to": r.phone,
                "type": "template",
                "template": {
                    "name": self.template,
                    "language": {"code": self.language},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": (message or "Suvichaar story")},
                                {"type": "text", "text": story_url},
                            ],
                        }
                    ],
                },
            }
            try:
                response = httpx.post(url, json=payload, headers=headers, timeout=15.0)
                if response.status_code // 100 == 2:
                    outcomes.append(DeliveryOutcome("whatsapp", r.phone, "sent"))
                else:
                    outcomes.append(
                        DeliveryOutcome(
                            "whatsapp",
                            r.phone,
                            "failed",
                            f"{response.status_code}: {response.text[:200]}",
                        )
                    )
            except Exception as exc:  # noqa: BLE001
                outcomes.append(DeliveryOutcome("whatsapp", r.phone, "failed", str(exc)))
        return outcomes


# ── Email adapter (SMTP) ────────────────────────────────────────────────────


class EmailAdapter:
    """Send a story-link email via SMTP when credentials are set.

    Env vars used (all optional — missing creds => `queued` outcomes):
        SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASSWORD
        SMTP_FROM           default "no-reply@suvichaar.org"
        SMTP_USE_TLS        "true" (default) or "false"
    """

    def __init__(self) -> None:
        self.host = (os.getenv("SMTP_HOST") or "").strip()
        self.port = int(os.getenv("SMTP_PORT") or "587")
        self.user = (os.getenv("SMTP_USER") or "").strip()
        self.password = (os.getenv("SMTP_PASSWORD") or "").strip()
        self.sender = (os.getenv("SMTP_FROM") or "no-reply@suvichaar.org").strip()
        self.use_tls = (os.getenv("SMTP_USE_TLS") or "true").strip().lower() != "false"

    @property
    def configured(self) -> bool:
        return bool(self.host and self.user and self.password)

    def send_many(
        self,
        recipients: Iterable[RecipientRef],
        *,
        story_title: str,
        story_url: str,
        message: Optional[str],
    ) -> List[DeliveryOutcome]:
        outcomes: List[DeliveryOutcome] = []
        rcpts = [r for r in recipients if r.email]
        if not rcpts:
            return outcomes

        if not self.configured:
            for r in rcpts:
                outcomes.append(
                    DeliveryOutcome(
                        channel="email",
                        recipient=r.email or "",
                        status="queued",
                        error="SMTP credentials not configured; queued.",
                    )
                )
            return outcomes

        body_text = (message or "A new Suvichaar story is live.") + f"\n\n{story_url}\n"
        try:
            client_factory = smtplib.SMTP if self.use_tls else smtplib.SMTP_SSL
            with client_factory(self.host, self.port, timeout=15) as smtp:
                if self.use_tls:
                    smtp.starttls()
                smtp.login(self.user, self.password)
                for r in rcpts:
                    msg = EmailMessage()
                    msg["Subject"] = story_title
                    msg["From"] = self.sender
                    msg["To"] = r.email
                    msg.set_content(body_text)
                    try:
                        smtp.send_message(msg)
                        outcomes.append(DeliveryOutcome("email", r.email or "", "sent"))
                    except Exception as exc:  # noqa: BLE001
                        outcomes.append(
                            DeliveryOutcome("email", r.email or "", "failed", str(exc))
                        )
        except Exception as exc:  # noqa: BLE001
            for r in rcpts:
                outcomes.append(DeliveryOutcome("email", r.email or "", "failed", str(exc)))
        return outcomes


# ── Service ─────────────────────────────────────────────────────────────────


@dataclass
class BroadcastResult:
    outcomes: List[DeliveryOutcome]
    total: int
    sent: int
    failed: int
    queued: int

    @property
    def status(self) -> str:
        if self.failed == self.total and self.total > 0:
            return "failed"
        if self.sent == self.total:
            return "sent"
        if self.queued == self.total and self.total > 0:
            return "queued"
        return "partial"


class BroadcastService:
    def __init__(
        self,
        whatsapp: Optional[WhatsAppAdapter] = None,
        email: Optional[EmailAdapter] = None,
    ) -> None:
        self.whatsapp = whatsapp or WhatsAppAdapter()
        self.email = email or EmailAdapter()

    def broadcast(
        self,
        *,
        story_title: str,
        story_url: str,
        channels: List[str],
        recipients: List[RecipientRef],
        message: Optional[str] = None,
    ) -> BroadcastResult:
        outcomes: List[DeliveryOutcome] = []

        if "whatsapp" in channels:
            outcomes.extend(
                self.whatsapp.send_many(
                    [r for r in recipients if r.phone],
                    story_url=story_url,
                    message=message,
                )
            )
        if "email" in channels:
            outcomes.extend(
                self.email.send_many(
                    [r for r in recipients if r.email],
                    story_title=story_title,
                    story_url=story_url,
                    message=message,
                )
            )

        total = len(outcomes)
        sent = sum(1 for o in outcomes if o.status == "sent")
        failed = sum(1 for o in outcomes if o.status == "failed")
        queued = sum(1 for o in outcomes if o.status == "queued")
        return BroadcastResult(outcomes=outcomes, total=total, sent=sent, failed=failed, queued=queued)
