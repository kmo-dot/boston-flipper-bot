"""Common interface every source adapter implements."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Listing


class Source(ABC):
    name: str

    @abstractmethod
    def fetch(self) -> list[Listing]:
        """Return every listing found this run. Should raise on total
        failure (e.g. site unreachable) so the pipeline can record a
        per-source error without one bad source killing the whole run.
        Partial-result failures (e.g. one page of several fails) should be
        swallowed internally and logged, returning whatever succeeded.
        """
        raise NotImplementedError
