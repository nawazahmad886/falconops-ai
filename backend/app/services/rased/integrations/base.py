"""
Integration adapter interface: one live/mock pair per external system. Mock
is the default and must be demo-perfect — assume live access is not granted
until late, or at all.
"""
from abc import ABC, abstractmethod


class IntegrationAdapter(ABC):
    @abstractmethod
    async def is_live(self) -> bool:
        raise NotImplementedError


__all__ = ["IntegrationAdapter"]
