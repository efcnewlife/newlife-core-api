"""
CLI package.

Important:
Avoid importing submodules (e.g. `.main`) at package import time, because
`python -m portal.cli.main` will import `portal.cli` first and then execute
`portal.cli.main` via `runpy`, which can trigger an import-order warning.
"""

__all__: list[str] = []

