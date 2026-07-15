"""
MS Graph DI container.
"""
from dependency_injector import containers, providers

from portal.providers.ms_graph.users import MSGraphUsers


class MSGraphContainer(containers.DeclarativeContainer):
    """Microsoft Graph providers."""

    users = providers.Factory(MSGraphUsers)
