"""Transport-only serializers for Phase 10 reporting."""

from __future__ import annotations

from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, Iterable, Iterator, Mapping, Protocol, runtime_checkable


ReportRowLike = Mapping[str, object]


@runtime_checkable
class ReportColumnLike(Protocol):
    key: str
    title: str
    column_type: object
    nullable: bool


@runtime_checkable
class ReportSchemaLike(Protocol):
    columns: tuple[ReportColumnLike, ...]
    sheet_name: str


@runtime_checkable
class ReportSerializer(Protocol):
    def serialize(
        self,
        rows: Iterable[ReportRowLike],
        schema: ReportSchemaLike,
    ) -> "SerializedReport": ...


@dataclass(slots=True)
class SerializedReport:
    """Owned request-scoped stream; callers must close it."""

    stream: BinaryIO
    mime_type: str
    file_extension: str
    byte_length: int

    @property
    def rolled_to_disk(self) -> bool:
        return bool(getattr(self.stream, "_rolled", False))

    def iter_bytes(self, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self.stream.seek(0)
        while chunk := self.stream.read(chunk_size):
            yield chunk

    def close(self) -> None:
        self.stream.close()

    def __enter__(self) -> "SerializedReport":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def create_spooled_stream(threshold_bytes: int) -> BinaryIO:
    if threshold_bytes <= 0:
        raise ValueError("threshold_bytes must be positive")
    return SpooledTemporaryFile(max_size=threshold_bytes, mode="w+b")


__all__ = (
    "ReportColumnLike",
    "ReportRowLike",
    "ReportSchemaLike",
    "ReportSerializer",
    "SerializedReport",
    "create_spooled_stream",
)
