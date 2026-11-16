"""
Temporary test recipient rotator for verifying SMTP notification behavior.
Routes all outgoing notification emails to a hardcoded pool of test recipients in rotation:
- fahmikeilmawan22@gmail.com
- fahmiilmawan8@gmail.com
- miilmawan.test@gmail.com

Protects real company employees from receiving test emails and prevents email blast accidents
while allowing testers to verify recipient logic and blast mitigation.
"""

from __future__ import annotations

import itertools
import logging
import threading
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

# Hardcoded test recipients requested by user
TEST_HARDCODED_EMAILS: list[str] = [
    "fahmikeilmawan22@gmail.com",
    "fahmiilmawan8@gmail.com",
    "miilmawan.test@gmail.com",
]

_email_cycle = itertools.cycle(TEST_HARDCODED_EMAILS)
_lock = threading.Lock()


def get_next_test_email() -> str:
    """Return the next test email recipient in thread-safe round-robin rotation."""
    with _lock:
        return next(_email_cycle)


def reroute_recipients(
    to: Iterable[str],
    cc: Iterable[str] | None = None,
    bcc: Iterable[str] | None = None,
) -> tuple[list[str], list[str], list[str], dict]:
    """
    Reroute recipient lists to the hardcoded test emails.

    Returns:
        tuple: (new_to, new_cc, new_bcc, audit_meta)
        - new_to: original recipients each substituted with a test recipient in rotation
        - new_cc: emptied to prevent sending test notifications to real employees
        - new_bcc: emptied to prevent sending test notifications to real employees
        - audit_meta: dictionary containing original_to, original_cc, original_bcc
    """
    orig_to = [e for e in to if e]
    orig_cc = [e for e in (cc or []) if e and e not in orig_to]
    orig_bcc = [
        e for e in (bcc or []) if e and e not in orig_to and e not in orig_cc
    ]

    if not orig_to:
        return [], [], [], {
            "original_to": orig_to,
            "original_cc": orig_cc,
            "original_bcc": orig_bcc,
        }

    # Assign each original recipient to a test email address in rotation
    new_to = [get_next_test_email() for _ in orig_to]
    new_cc: list[str] = []
    new_bcc: list[str] = []

    logger.info(
        "TEST MODE EMAIL REROUTE: original_to=%s -> rerouted_to=%s (suppressed cc=%s, bcc=%s)",
        orig_to,
        new_to,
        orig_cc,
        orig_bcc,
    )

    audit_meta = {
        "original_to": orig_to,
        "original_cc": orig_cc,
        "original_bcc": orig_bcc,
    }
    return new_to, new_cc, new_bcc, audit_meta


def format_test_email_content(
    subject: str,
    text_body: str,
    html_body: str | None,
    original_to: Sequence[str],
    original_cc: Sequence[str] | None = None,
    new_to: Sequence[str] | None = None,
) -> tuple[str, str, str | None]:
    """
    Annotate subject and body with clear test headers showing original destination
    and test recipient for transparency and verification.
    """
    orig_to_str = ", ".join(original_to)
    orig_cc_str = ", ".join(original_cc or [])
    new_to_str = ", ".join(new_to or [])

    test_subject = f"[TEST -> {orig_to_str}] {subject}"

    test_header_text = (
        f"[MODE PENGUJIAN EMAIL - ROTASI GILIRAN]\n"
        f"Dialihkan ke: {new_to_str}\n"
        f"Penerima Asli (TO): {orig_to_str}\n"
    )
    if orig_cc_str:
        test_header_text += f"Penerima Asli (CC): {orig_cc_str}\n"
    test_header_text += "--------------------------------------------------\n\n"

    new_text_body = test_header_text + text_body

    new_html_body = None
    if html_body:
        cc_html_line = (
            f"<br><strong>Penerima Asli (CC):</strong> <code>{orig_cc_str}</code>"
            if orig_cc_str
            else ""
        )
        test_banner_html = (
            f'<div style="background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; '
            f'padding: 12px 16px; margin-bottom: 20px; border-radius: 6px; font-family: sans-serif; font-size: 13px;">'
            f'<strong>[MODE PENGUJIAN EMAIL - ROTASI GILIRAN]</strong><br>'
            f'<strong>Dialihkan ke (Test Target):</strong> <code>{new_to_str}</code><br>'
            f'<strong>Penerima Asli (TO):</strong> <code>{orig_to_str}</code>'
            f'{cc_html_line}'
            f'</div>'
        )
        new_html_body = test_banner_html + html_body

    return test_subject, new_text_body, new_html_body
