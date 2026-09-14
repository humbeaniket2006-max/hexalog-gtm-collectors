"""Small typed wrapper around Notion database operations."""
from __future__ import annotations

from typing import Any
from notion_client import Client

class NotionHelper:
    def __init__(self, token: str, client: Any | None = None) -> None:
        self.client = client or Client(auth=token)

    def find_database_id(self, name: str) -> str:
        results = self.client.search(
            query=name,
            filter={"property": "object", "value": "data_source"},
            in_trash=False,
        ).get("results", [])
        for database in results:
            title = "".join(x.get("plain_text", "") for x in database.get("title", []))
            if title == name:
                return database["id"]
        raise LookupError(f'Notion database not found by exact title: "{name}"')

    def page_exists(self, database_id: str, external_id: str) -> bool:
        return self.find_page(database_id, "External ID", external_id) is not None

    def find_page(self, database_id: str, filter_property: str, equals: str) -> dict[str, Any] | None:
        result = self.query(database_id, {"property": filter_property, "rich_text": {"equals": equals}})
        return result.get("results", [None])[0] if result.get("results") else None

    def query(self, database_id: str, filter: dict[str, Any]) -> dict[str, Any]:
        """Query a data source (the post-2025-09-03 replacement for database queries)."""
        return self.client.data_sources.query(data_source_id=database_id, filter=filter)

    @staticmethod
    def _properties(properties: dict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for key, value in properties.items():
            if value is None:
                continue
            if isinstance(value, dict) and "type" in value:
                kind, raw = value["type"], value.get("value")
            else:
                kind, raw = ("title" if key == "Title" else "select" if key in {"Platform", "Type", "Status", "Sentiment"} else "url" if key.endswith("URL") or key == "URL" else "number" if key in {"Score/Views", "Comments Count"} else "date" if key.endswith("At") or key == "Scheduled Publish Time" else "rich_text"), value
            if kind in {"title", "rich_text"}:
                output[key] = {kind: [{"type": "text", "text": {"content": str(raw)}}]}
            elif kind == "select": output[key] = {"select": {"name": str(raw)}}
            elif kind == "url": output[key] = {"url": str(raw)}
            elif kind == "number": output[key] = {"number": int(raw) if raw is not None else None}
            elif kind == "date": output[key] = {"date": {"start": str(raw)}}
            else: raise ValueError(f"Unsupported Notion property type: {kind}")
        return output

    def create_page(self, database_id: str, properties: dict[str, Any]) -> None:
        self.client.pages.create(parent={"data_source_id": database_id}, properties=self._properties(properties))

    def update_page(self, page_id: str, properties: dict[str, Any]) -> None:
        self.client.pages.update(page_id=page_id, properties=self._properties(properties))
