"""
Resolve ministry application mail delivery targets for dev/test overrides.
"""


def resolve_mail_delivery_targets(*, intended_recipient: str, override_recipients: list[str]) -> tuple[list[str], str]:
    """
    Return recipient list and optional subject prefix.

    When override_recipients is set, all mail is redirected there and the subject
    is prefixed so the inbox shows the original intended recipient.
    """
    normalized_intended = (intended_recipient or "").strip()
    if not normalized_intended:
        return [], ""

    overrides = [email.strip() for email in override_recipients if email and email.strip()]
    if overrides:
        return overrides, f"[DEV -> {normalized_intended}] "
    return [normalized_intended], ""
