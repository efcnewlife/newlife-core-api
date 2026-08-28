"""
Jinja2 email template renderer.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template


class TemplateRenderProvider:
    """Render HTML email templates from portal/templates/."""

    def __init__(self, templates_root: Path | None = None):
        self._templates_root = templates_root or Path(__file__).resolve().parents[1] / "templates"

    def _template_dirs(self, scan_path: Path) -> list[str]:
        paths = [str(scan_path)]
        if not scan_path.is_dir():
            return paths
        for child in scan_path.iterdir():
            if child.is_dir():
                paths.extend(self._template_dirs(child))
        return paths

    @property
    def _environment(self) -> Environment:
        return Environment(loader=FileSystemLoader(searchpath=self._template_dirs(self._templates_root)), enable_async=True, autoescape=True)

    @staticmethod
    async def _render(template: Template, **context: object) -> str:
        return await template.render_async(**context)

    async def render_email_template(self, template_name: str, **context: object) -> str:
        template = self._environment.get_template(name=template_name)
        return await self._render(template, **context)
