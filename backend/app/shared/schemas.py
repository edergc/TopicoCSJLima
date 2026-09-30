"""Tipos y utilidades comunes de los schemas de la API."""

from collections.abc import Sequence
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, ConfigDict, StringConstraints


class ApiModel(BaseModel):
    """Base de los schemas: estricto con campos desconocidos en la entrada."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApiOut(BaseModel):
    """Base de los schemas de salida (se construyen desde objetos ORM)."""

    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: Sequence[T]
    total: int
    page: int
    size: int


class PageParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, le=100_000)] = 1,
        size: Annotated[int, Query(ge=1, le=200)] = 25,
    ) -> None:
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
