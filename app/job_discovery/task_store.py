from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from app.api.schemas import DiscoveryTask

_tasks: dict[str, DiscoveryTask] = {}
_lock = threading.Lock()


def create_task() -> DiscoveryTask:
    """Create a new discovery task and return it."""
    task = DiscoveryTask(
        task_id=uuid4().hex[:12],
        status="pending",
        progress=0.0,
        message="Task created",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    with _lock:
        _tasks[task.task_id] = task
    return task


def get_task(task_id: str) -> DiscoveryTask | None:
    """Retrieve a task by ID."""
    with _lock:
        return _tasks.get(task_id)


def update_task(task_id: str, **fields) -> DiscoveryTask | None:
    """Update fields on an existing task."""
    with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return None
        for key, value in fields.items():
            if hasattr(task, key):
                setattr(task, key, value)
        return task


def delete_task(task_id: str) -> bool:
    """Remove a completed task."""
    with _lock:
        return _tasks.pop(task_id, None) is not None
