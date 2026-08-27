from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Sequence


class DatabaseAdapter(ABC):
    @abstractmethod
    def connect(self, database: str): ...

    @abstractmethod
    def execute(self, database: str, sql: str, params: Sequence[Any] = ()): ...

    @abstractmethod
    def resolve_database(self, database: str, *, must_exist: bool = True) -> Path: ...
