"""
Minimal Mongo-backed LangGraph checkpointer, against db.rased_checkpoints.

The plan's instruction was: try langgraph-checkpoint-mongodb first; if it
doesn't resolve cleanly, write this ~60-line fallback. Verifying that package
requires an actual pip/uv resolution in a working Python environment, which
was not available while authoring this file (see Phase 0's dependency
resolution report — no local interpreter, uv's managed-Python download is
blocked by TLS interception in this sandbox). Taking the documented fallback
path directly rather than guessing at whether the third-party package
resolves.

HIGHEST-RISK FILE IN THIS BUILD. BaseCheckpointSaver's async method
signatures (aput/aput_writes/aget_tuple/alist) are implemented here against
the documented shape of langgraph's checkpoint.base API, not against an
actually-imported langgraph — there was no interpreter available to import it
and confirm. This is the first file to exercise against a real
`pip install langgraph==1.2.10` before trusting the approval-gate resume path
in Phase 4.
"""
import logging
from typing import Any, AsyncIterator, Dict, Optional, Sequence, Tuple

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

logger = logging.getLogger(__name__)


class MongoCheckpointer(BaseCheckpointSaver):
    """One document per (thread_id, checkpoint_ns, checkpoint_id) in
    db.rased_checkpoints. thread_id is the RASED incident_id, so killing the
    process mid-investigation and restarting resumes from the last-written
    checkpoint for that incident."""

    def __init__(self):
        super().__init__(serde=JsonPlusSerializer())

    def _collection(self):
        from ....core.database import db
        return db.rased_checkpoints

    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> Dict[str, Any]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]

        await self._collection().update_one(
            {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id},
            {"$set": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
                "checkpoint": self.serde.dumps_typed(checkpoint),
                "metadata": self.serde.dumps_typed(metadata),
            }},
            upsert=True,
        )
        return {"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id}}

    async def aput_writes(
        self,
        config: Dict[str, Any],
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        serialized = [
            {"channel": channel, "type_value": self.serde.dumps_typed(value), "task_id": task_id, "task_path": task_path}
            for channel, value in writes
        ]
        await self._collection().update_one(
            {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": checkpoint_id},
            {"$push": {"pending_writes": {"$each": serialized}}},
            upsert=True,
        )

    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        query = {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}
        if checkpoint_id:
            query["checkpoint_id"] = checkpoint_id
            doc = await self._collection().find_one(query, {"_id": 0})
        else:
            doc = await self._collection().find_one(query, {"_id": 0}, sort=[("checkpoint_id", -1)])

        if doc is None:
            return None

        parent_config = None
        if doc.get("parent_checkpoint_id"):
            parent_config = {"configurable": {
                "thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": doc["parent_checkpoint_id"],
            }}

        pending_writes = [
            (w["task_id"], w["channel"], self.serde.loads_typed(w["type_value"]))
            for w in doc.get("pending_writes", [])
        ]

        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": doc["checkpoint_id"]}},
            checkpoint=self.serde.loads_typed(doc["checkpoint"]),
            metadata=self.serde.loads_typed(doc["metadata"]),
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    async def alist(
        self,
        config: Optional[Dict[str, Any]],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        query: Dict[str, Any] = {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}
        if before and before.get("configurable", {}).get("checkpoint_id"):
            query["checkpoint_id"] = {"$lt": before["configurable"]["checkpoint_id"]}

        cursor = self._collection().find(query, {"_id": 0}).sort("checkpoint_id", -1)
        if limit:
            cursor = cursor.limit(limit)

        async for doc in cursor:
            yield CheckpointTuple(
                config={"configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns, "checkpoint_id": doc["checkpoint_id"]}},
                checkpoint=self.serde.loads_typed(doc["checkpoint"]),
                metadata=self.serde.loads_typed(doc["metadata"]),
                parent_config=None,
                pending_writes=[],
            )


__all__ = ["MongoCheckpointer"]
