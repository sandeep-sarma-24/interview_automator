"""Gmail discovery source (OAuth, read-only).

One-time authorization creates a refresh token on disk (run `app.cli gmail-auth`).
Thereafter the 24x7 service reads the dedicated job-alerts mailbox unattended.
If Gmail isn't configured/authorized, fetch() raises DiscoveryUnavailable and the
discovery service simply skips it (manual discovery + scoring keep working).
"""
from __future__ import annotations

import base64
import sqlite3
from typing import List, Optional

from app import util
from app.config import get_settings
from app.discovery.base import DiscoverySource, DiscoveryUnavailable, NormalizedJob
from app.discovery import parsers

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _load_credentials():
    settings = get_settings()
    token_path = settings.gmail_token
    if not token_path or not token_path.exists():
        raise DiscoveryUnavailable(
            "Gmail not authorized. Run: python -m app.cli gmail-auth")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError as e:  # pragma: no cover
        raise DiscoveryUnavailable(f"Google libraries missing: {e}")

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    if not creds or not creds.valid:
        raise DiscoveryUnavailable("Gmail credentials invalid; re-run gmail-auth")
    return creds


def authorize_interactive() -> str:
    """Run the one-time OAuth consent flow; persist the token. Returns token path."""
    settings = get_settings()
    if not settings.gmail_credentials or not settings.gmail_credentials.exists():
        raise RuntimeError(
            f"Missing OAuth client file at {settings.gmail_credentials}. "
            "Download a Desktop OAuth client from Google Cloud console.")
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(
        str(settings.gmail_credentials), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path = settings.gmail_token
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return str(token_path)


def _decode_part(data: Optional[str]) -> str:
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")


def _extract_html(payload: dict) -> str:
    """Walk the MIME tree, preferring text/html, falling back to text/plain."""
    html_parts: List[str] = []
    text_parts: List[str] = []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        if mime == "text/html":
            html_parts.append(_decode_part(body.get("data")))
        elif mime == "text/plain":
            text_parts.append(_decode_part(body.get("data")))
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    if html_parts:
        return "\n".join(html_parts)
    return "\n".join(f"<div>{t}</div>" for t in text_parts)


def _header(headers: List[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


class GmailSource(DiscoverySource):
    name = "gmail"

    def __init__(self, max_messages: int = 50) -> None:
        self.max_messages = max_messages

    def fetch(self, conn: sqlite3.Connection) -> List[NormalizedJob]:
        creds = _load_credentials()
        try:
            from googleapiclient.discovery import build
        except ImportError as e:  # pragma: no cover
            raise DiscoveryUnavailable(f"googleapiclient missing: {e}")

        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        settings = get_settings()
        listing = service.users().messages().list(
            userId="me", q=settings.gmail_query, maxResults=self.max_messages).execute()
        message_ids = [m["id"] for m in listing.get("messages", [])]

        jobs: List[NormalizedJob] = []
        for mid in message_ids:
            if conn.execute("SELECT 1 FROM processed_email WHERE message_id=?",
                            (mid,)).fetchone():
                continue
            msg = service.users().messages().get(
                userId="me", id=mid, format="full").execute()
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            sender = _header(headers, "From")
            subject = _header(headers, "Subject")
            source_ref = parsers.detect_source(sender, subject)
            html = _extract_html(payload)
            found = parsers.parse_email(html, source_ref)
            for nj in found:
                nj.source_ref = source_ref
            jobs.extend(found)
            conn.execute(
                "INSERT OR REPLACE INTO processed_email (message_id, source_ref, "
                "processed_at, job_count) VALUES (?,?,?,?)",
                (mid, source_ref, util.now_iso(), len(found)))
        return jobs
