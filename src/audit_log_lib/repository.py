from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from audit_log_lib.models import AuditLogCreate, AuditLogRecord, PaginatedAuditLogResult

_ISO_DATETIME_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$"
)


class AuditLogRepository:
    def __init__(
        self,
        *,
        connection_string: str,
        database_name: Optional[str] = None,
        collection_name: str = "audit_trails",
        client: Optional[AsyncIOMotorClient] = None,
    ) -> None:
        self._client = client or AsyncIOMotorClient(connection_string)
        database = self._client.get_default_database(default=database_name or "main")
        self._collection: AsyncIOMotorCollection = database[collection_name]

    @property
    def collection(self) -> AsyncIOMotorCollection:
        return self._collection

    async def create(self, *, obj_in: AuditLogCreate) -> AuditLogRecord:
        payload = _model_to_dict(obj_in)
        payload["uid"] = str(uuid4())
        payload["created_at"] = datetime.now(UTC)
        await self.collection.insert_one(payload)
        return AuditLogRecord(**payload)

    async def get_by_uid(self, *, uid: str) -> Optional[AuditLogRecord]:
        document = await self.collection.find_one({"uid": uid})
        return self._to_record(document)

    async def get_by_owner(
        self,
        *,
        owner_uid: str,
        username: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AuditLogRecord]:
        query = self._build_owner_query(
            owner_uid=owner_uid,
            username=username,
            start_date=start_date,
            end_date=end_date,
            search_keyword=search_keyword,
        )
        return await self._find(query=query, skip=skip, limit=limit)

    async def get_by_owner_with_count(
        self,
        *,
        owner_uid: str,
        username: Optional[str] = None,
        entity_type: Optional[str] = None,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[AuditLogRecord], int]:
        query = self._build_owner_query(
            owner_uid=owner_uid,
            username=username,
            start_date=start_date,
            end_date=end_date,
            search_keyword=search_keyword,
        )

        if entity_type:
            query["entity_type"] = entity_type

        if action_type:
            query["action_type"] = action_type

        total = await self.collection.count_documents(query)
        items = await self._find(query=query, skip=skip, limit=limit)
        return items, total

    async def list_paginated_by_owner(
        self,
        *,
        owner_uid: str,
        username: Optional[str] = None,
        entity_type: Optional[str] = None,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search_keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> PaginatedAuditLogResult:
        items, total = await self.get_by_owner_with_count(
            owner_uid=owner_uid,
            username=username,
            entity_type=entity_type,
            action_type=action_type,
            start_date=start_date,
            end_date=end_date,
            search_keyword=search_keyword,
            skip=skip,
            limit=limit,
        )
        return PaginatedAuditLogResult(total=total, items=items)

    async def get_custom_with_count(
        self,
        *,
        owner_uid: str,
        custom_query: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[AuditLogRecord], int]:
        query: Dict[str, Any] = {"owner_uid": owner_uid}
        if custom_query:
            query.update(custom_query)

        normalized_query = self._normalize_query(query)
        total = await self.collection.count_documents(normalized_query)
        items = await self._find(query=normalized_query, skip=skip, limit=limit)
        return items, total

    async def list_custom_paginated(
        self,
        *,
        owner_uid: str,
        custom_query: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> PaginatedAuditLogResult:
        items, total = await self.get_custom_with_count(
            owner_uid=owner_uid,
            custom_query=custom_query,
            skip=skip,
            limit=limit,
        )
        return PaginatedAuditLogResult(total=total, items=items)

    async def _find(
        self, *, query: Dict[str, Any], skip: int, limit: int
    ) -> List[AuditLogRecord]:
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        documents = [document async for document in cursor]
        return [self._to_record(document) for document in documents if document]

    def _build_owner_query(
        self,
        *,
        owner_uid: str,
        username: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        search_keyword: Optional[str],
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {"owner_uid": owner_uid}

        if start_date or end_date:
            date_query: Dict[str, datetime] = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            if date_query:
                query["created_at"] = date_query

        if username:
            query["actor.username"] = {"$regex": f"^{username}$", "$options": "i"}

        if search_keyword:
            query["$or"] = [
                {"action_type": {"$regex": search_keyword, "$options": "i"}},
                {"entity_type": {"$regex": search_keyword, "$options": "i"}},
                {"actor.name": {"$regex": search_keyword, "$options": "i"}},
                {"actor.role": {"$regex": search_keyword, "$options": "i"}},
                {"entity.name": {"$regex": search_keyword, "$options": "i"}},
            ]

        return query

    def _normalize_query(self, value: Any, parent_key: Optional[str] = None) -> Any:
        if isinstance(value, dict):
            return {
                key: self._normalize_query(item, parent_key=key)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [self._normalize_query(item, parent_key=parent_key) for item in value]

        if (
            parent_key in {"$gte", "$lte", "$gt", "$lt"}
            and isinstance(value, str)
            and _ISO_DATETIME_PATTERN.match(value)
        ):
            return self._parse_iso_datetime(value)

        return value

    def _to_record(self, document: Optional[Dict[str, Any]]) -> Optional[AuditLogRecord]:
        if not document:
            return None

        clean_document = {key: value for key, value in document.items() if key != "_id"}
        return AuditLogRecord(**clean_document)

    @staticmethod
    def _parse_iso_datetime(value: str) -> datetime:
        if "." in value:
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
