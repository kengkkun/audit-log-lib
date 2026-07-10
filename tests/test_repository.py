from datetime import datetime

import pytest

from audit_log_lib import AuditLogCreate, AuditLogRepository


class FakeCursor:
    def __init__(self, documents):
        self.documents = list(documents)
        self._skip = 0
        self._limit = None

    def sort(self, field, direction):
        self.documents.sort(key=lambda item: item[field], reverse=direction == -1)
        return self

    def skip(self, value):
        self._skip = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def __aiter__(self):
        end = None if self._limit is None else self._skip + self._limit
        self._iter = iter(self.documents[self._skip:end])
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class FakeCollection:
    def __init__(self):
        self.documents = []
        self.last_count_query = None

    async def insert_one(self, payload):
        self.documents.append(dict(payload))

    async def find_one(self, query):
        for document in self.documents:
            if document.get("uid") == query.get("uid"):
                return dict(document)
        return None

    def find(self, query):
        filtered = [doc for doc in self.documents if self._matches(doc, query)]
        return FakeCursor(filtered)

    async def count_documents(self, query):
        self.last_count_query = query
        return len([doc for doc in self.documents if self._matches(doc, query)])

    def _matches(self, document, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self._matches(document, item) for item in value):
                    return False
                continue

            if key == "created_at" and isinstance(value, dict):
                created_at = document["created_at"]
                if "$gte" in value and created_at < value["$gte"]:
                    return False
                if "$lte" in value and created_at > value["$lte"]:
                    return False
                continue

            if isinstance(value, dict) and "$regex" in value:
                field_value = _resolve_field(document, key) or ""
                if value.get("$options") == "i":
                    if value["$regex"].lower() not in str(field_value).lower():
                        return False
                elif value["$regex"] not in str(field_value):
                    return False
                continue

            if document.get(key) != value:
                if _resolve_field(document, key) != value:
                    return False

        return True


def _resolve_field(document, dotted_key):
    value = document
    for part in dotted_key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


@pytest.fixture
def repository():
    repo = AuditLogRepository(connection_string="mongodb://localhost:27017/audit_db")
    repo._collection = FakeCollection()
    return repo


@pytest.mark.asyncio
async def test_create_log(repository):
    created = await repository.create(
        obj_in=AuditLogCreate(
            owner_uid="company-001",
            actor={"username": "alice"},
            entity={"name": "Order #1"},
            entity_type="order",
            action_type="create",
        )
    )

    assert created.uid
    assert created.created_at is not None
    assert created.owner_uid == "company-001"


@pytest.mark.asyncio
async def test_get_by_uid(repository):
    created = await repository.create(
        obj_in=AuditLogCreate(
            owner_uid="company-001",
            actor={"username": "alice"},
            entity={"name": "Order #1"},
            entity_type="order",
            action_type="create",
        )
    )

    fetched = await repository.get_by_uid(uid=created.uid)

    assert fetched is not None
    assert fetched.uid == created.uid


@pytest.mark.asyncio
async def test_get_by_owner_returns_list(repository):
    repository.collection.documents = [
        {
            "uid": "1",
            "owner_uid": "company-001",
            "actor": {"username": "alice", "name": "Alice"},
            "entity": {"name": "Order A"},
            "entity_type": "order",
            "action_type": "create",
            "created_at": datetime(2024, 1, 1, 10, 0, 0),
        },
        {
            "uid": "2",
            "owner_uid": "company-001",
            "actor": {"username": "bob", "name": "Bob"},
            "entity": {"name": "Order B"},
            "entity_type": "order",
            "action_type": "update",
            "created_at": datetime(2024, 1, 2, 10, 0, 0),
        },
    ]

    items = await repository.get_by_owner(owner_uid="company-001", skip=0, limit=10)

    assert len(items) == 2
    assert items[0].uid == "2"


@pytest.mark.asyncio
async def test_list_paginated_by_owner_returns_total_and_items(repository):
    repository.collection.documents = [
        {
            "uid": "1",
            "owner_uid": "company-001",
            "actor": {"username": "alice"},
            "entity": {"name": "Order A"},
            "entity_type": "order",
            "action_type": "create",
            "created_at": datetime(2024, 1, 1, 10, 0, 0),
        },
        {
            "uid": "2",
            "owner_uid": "company-001",
            "actor": {"username": "bob"},
            "entity": {"name": "Order B"},
            "entity_type": "order",
            "action_type": "update",
            "created_at": datetime(2024, 1, 2, 10, 0, 0),
        },
        {
            "uid": "3",
            "owner_uid": "company-002",
            "actor": {"username": "carol"},
            "entity": {"name": "Order C"},
            "entity_type": "order",
            "action_type": "delete",
            "created_at": datetime(2024, 1, 3, 10, 0, 0),
        },
    ]

    result = await repository.list_paginated_by_owner(
        owner_uid="company-001",
        skip=0,
        limit=1,
    )

    assert result.total == 2
    assert len(result.items) == 1
    assert result.items[0].uid == "2"


@pytest.mark.asyncio
async def test_custom_query_converts_iso_datetime_strings(repository):
    repository.collection.documents = [
        {
            "uid": "1",
            "owner_uid": "company-001",
            "actor": {"username": "alice"},
            "entity": {"name": "Order A"},
            "entity_type": "order",
            "action_type": "create",
            "created_at": datetime(2024, 1, 2, 10, 0, 0),
        }
    ]

    result = await repository.list_custom_paginated(
        owner_uid="company-001",
        custom_query={
            "created_at": {
                "$gte": "2024-01-02T00:00:00.000Z",
                "$lte": "2024-01-02T23:59:59.000Z",
            }
        },
        skip=0,
        limit=10,
    )

    assert result.total == 1
    assert len(result.items) == 1
    assert isinstance(repository.collection.last_count_query["created_at"]["$gte"], datetime)
