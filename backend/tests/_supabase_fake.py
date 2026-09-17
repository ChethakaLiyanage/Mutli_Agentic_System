"""Small PostgREST-style fake used by Supabase repository unit tests."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass
class FakeResponse:
    data: list[dict[str, Any]]


class FakePostgrestError(Exception):
    def __init__(self, message: str, code: str = "XX000") -> None:
        super().__init__(message)
        self.code = code


class FakeQuery:
    def __init__(self, client: "FakeSupabaseClient", table_name: str) -> None:
        self.client = client
        self.table_name = table_name
        self.operation = ""
        self.payload: dict[str, Any] | None = None
        self.filters: list[tuple[str, Any]] = []

    def insert(self, payload: dict[str, Any]) -> "FakeQuery":
        self.operation = "insert"
        self.payload = deepcopy(payload)
        return self

    def upsert(
        self,
        payload: dict[str, Any],
        *,
        on_conflict: str,
    ) -> "FakeQuery":
        self.operation = "upsert"
        self.payload = deepcopy(payload)
        self.client.last_on_conflict = on_conflict
        return self

    def select(self, _columns: str) -> "FakeQuery":
        self.operation = "select"
        return self

    def delete(self) -> "FakeQuery":
        self.operation = "delete"
        return self

    def eq(self, column: str, value: Any) -> "FakeQuery":
        self.filters.append((column, value))
        return self

    def limit(self, _count: int) -> "FakeQuery":
        return self

    def execute(self) -> FakeResponse:
        return self.client.execute(self)


class FakeSupabaseClient:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, dict[str, Any]]] = {
            "users": {},
            "workflows": {},
        }
        self.calls: list[tuple[str, str]] = []
        self.fail_next: Exception | None = None
        self.last_on_conflict: str | None = None

    def table(self, table_name: str) -> FakeQuery:
        return FakeQuery(self, table_name)

    def execute(self, query: FakeQuery) -> FakeResponse:
        self.calls.append((query.table_name, query.operation))
        if self.fail_next is not None:
            error = self.fail_next
            self.fail_next = None
            raise error

        table = self.rows[query.table_name]
        if query.operation == "insert":
            assert query.payload is not None
            if query.table_name == "users" and any(
                row["email"] == query.payload["email"] for row in table.values()
            ):
                raise FakePostgrestError("duplicate key", code="23505")
            key_name = "user_id" if query.table_name == "users" else "workflow_id"
            table[query.payload[key_name]] = deepcopy(query.payload)
            return FakeResponse([deepcopy(query.payload)])

        if query.operation == "upsert":
            assert query.payload is not None
            table[query.payload["workflow_id"]] = deepcopy(query.payload)
            return FakeResponse([deepcopy(query.payload)])

        matching = [
            row
            for row in table.values()
            if all(row.get(column) == value for column, value in query.filters)
        ]
        if query.operation == "select":
            return FakeResponse(deepcopy(matching))
        if query.operation == "delete":
            for row in matching:
                key_name = (
                    "user_id" if query.table_name == "users" else "workflow_id"
                )
                table.pop(row[key_name], None)
            return FakeResponse(deepcopy(matching))
        raise AssertionError(f"Unsupported operation: {query.operation}")
