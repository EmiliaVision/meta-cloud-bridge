from __future__ import annotations

import re
import unicodedata
from typing import Any

from .types import MetaChannel

META_IDENTITY_CONTENT_KEY = "com.emiliavision.meta_cloud_bridge.identity"

_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?[0-9][0-9 ()_.-]{6,}[0-9]")


def _clean_label(label: str) -> str:
    normalized = unicodedata.normalize("NFKD", label)
    ascii_label = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_label = ascii_label.lower().strip()
    ascii_label = re.sub(r"[\s_\-:]+", " ", ascii_label)
    ascii_label = re.sub(r"[^a-z0-9 ?]+", "", ascii_label)
    return ascii_label.strip(" ?")


def _looks_like_label(value: str) -> bool:
    label = _clean_label(value)
    if not label or len(label) > 120:
        return False
    if label in _FIELD_ALIASES:
        return True
    return any(
        token in label
        for token in ("email", "phone", "telefone", "restaurant", "restaurante", "nome")
    )


_FIELD_ALIASES = {
    "email": "email",
    "e mail": "email",
    "full name": "full_name",
    "nome completo": "full_name",
    "name": "full_name",
    "nome": "full_name",
    "phone number": "phone",
    "phone": "phone",
    "telefone": "phone",
    "celular": "phone",
    "whatsapp": "phone",
    "qual e o nome dos seus restaurantes": "restaurant_name",
    "qual e o nome do seu restaurante": "restaurant_name",
    "nome do restaurante": "restaurant_name",
    "restaurant name": "restaurant_name",
    "quantos restaurantes voces operam": "restaurant_count",
    "quantos restaurantes voce opera": "restaurant_count",
    "restaurant count": "restaurant_count",
    "quem decide a contratacao de novas tecnologias para os restaurantes": "decision_maker",
    "quem decide a contratacao de novas tecnologias": "decision_maker",
    "decision maker": "decision_maker",
}


def parse_lead_fields(text: str | None) -> dict[str, str]:
    """Parse lead form fields from the plain text body emitted by Meta."""
    if not text:
        return {}

    fields: dict[str, str] = {}
    lines = [line.strip(" \t•-–") for line in text.splitlines()]
    lines = [line for line in lines if line]

    index = 0
    while index < len(lines):
        line = lines[index]
        if ":" in line:
            label, value = line.split(":", 1)
            label = label.strip()
            value = value.strip()
            if label and value:
                fields[label] = value
            index += 1
            continue

        if _looks_like_label(line) and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if next_line and not _looks_like_label(next_line):
                fields[line] = next_line
                index += 2
                continue

        index += 1

    if "Email" not in fields:
        email = _EMAIL_RE.search(text)
        if email:
            fields["Email"] = email.group(0)

    if "Phone number" not in fields:
        phone = _PHONE_RE.search(text)
        if phone:
            fields["Phone number"] = phone.group(0).strip()

    return fields


def _canonical_field_map(fields: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for label, value in fields.items():
        canonical = _FIELD_ALIASES.get(_clean_label(label))
        if canonical and value:
            result[canonical] = value.strip()
    return result


def extract_contact_identity(
    fields: dict[str, str], *, fallback_name: str | None = None
) -> dict[str, str]:
    """Extract contact fields from parsed lead/message text."""
    canonical = _canonical_field_map(fields)
    contact: dict[str, str] = {}

    full_name = canonical.get("full_name") or fallback_name
    if full_name:
        contact["full_name"] = full_name

    email = canonical.get("email")
    if email:
        match = _EMAIL_RE.search(email)
        if match:
            contact["email"] = match.group(0)
            contact["email_source"] = "lead_form_message"

    phone = canonical.get("phone")
    if phone:
        contact["phone"] = phone
        contact["phone_source"] = "lead_form_message"

    return contact


def extract_lead_identity(fields: dict[str, str]) -> dict[str, Any]:
    """Extract sales lead fields from parsed lead/message text."""
    canonical = _canonical_field_map(fields)
    lead: dict[str, Any] = {}
    for source, target in (
        ("restaurant_name", "restaurant_name"),
        ("restaurant_count", "restaurant_count"),
        ("decision_maker", "decision_maker"),
    ):
        value = canonical.get(source)
        if value:
            lead[target] = value
    if fields:
        lead["raw_fields"] = fields
    return lead


def normalize_graph_profile(
    channel: MetaChannel, profile: dict[str, Any] | None
) -> dict[str, str]:
    """Normalize channel-specific Graph profile fields for Pyldon metadata."""
    if not profile:
        return {}
    normalized: dict[str, str] = {}
    for key in ("id", "username", "name", "first_name", "last_name", "profile_pic"):
        value = profile.get(key)
        if value:
            normalized[key] = str(value)
    if channel is MetaChannel.MESSENGER and "name" not in normalized:
        name = " ".join(
            part for part in (normalized.get("first_name"), normalized.get("last_name")) if part
        ).strip()
        if name:
            normalized["name"] = name
    return normalized


def choose_display_name(
    profile: dict[str, Any] | None,
    contact: dict[str, Any] | None,
    fallback: str,
) -> str:
    """Choose the most human-readable display name available."""
    contact = contact or {}
    profile = profile or {}
    for value in (
        contact.get("full_name"),
        profile.get("name"),
        profile.get("username"),
        fallback,
    ):
        if value:
            return str(value)
    return fallback


def is_non_actionable_meta_attachment(attachment: dict[str, Any]) -> bool:
    """Return true for Meta artifacts that should not become Matrix messages."""
    attachment_type = str(attachment.get("type") or "").lower()
    payload = attachment.get("payload") or {}
    url = payload.get("url") or attachment.get("url")
    return attachment_type == "template" and not url


def build_matrix_identity_payload(
    *,
    channel: MetaChannel,
    account_id: str,
    remote_user_id: str,
    remote_message_id: str | None = None,
    message_type: str | None = None,
    is_echo: bool = False,
    matrix_sender_hint: str | None = None,
    profile: dict[str, Any] | None = None,
    contact: dict[str, Any] | None = None,
    lead: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a namespaced Matrix content payload with Meta lead identity."""
    payload: dict[str, Any] = {
        "source": "meta-cloud-bridge",
        "channel": channel.value,
        "account_id": account_id,
        "remote_user_id": str(remote_user_id),
        "message": {
            "remote_message_id": remote_message_id,
            "message_type": message_type,
            "is_echo": is_echo,
        },
    }
    if matrix_sender_hint:
        payload["matrix_sender_hint"] = matrix_sender_hint
    if profile:
        payload["profile"] = {key: value for key, value in profile.items() if value is not None}
    if contact:
        payload["contact"] = {key: value for key, value in contact.items() if value is not None}
    if lead:
        payload["lead"] = {key: value for key, value in lead.items() if value is not None}
    return payload
