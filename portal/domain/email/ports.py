"""
Email rendering domain ports.
"""

from typing import Protocol


class EmailTemplateRenderPort(Protocol):
    """Render version-controlled HTML email templates."""

    async def render_email_template(self, template_name: str, **context: object) -> str: ...
