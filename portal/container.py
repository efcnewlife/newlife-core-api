"""
Composition root: single entry point for dependency injection.
"""

from portal.containers import RootContainer

Container = RootContainer
container = RootContainer()
