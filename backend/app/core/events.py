"""In-process async event bus for decoupled feature communication.

This module provides a simple pub/sub event system using asyncio.Queue.
It allows different parts of the application to communicate without
direct dependencies on each other.

Usage:
    from app.core.events import event_bus, Event

    # Subscribe to events
    async def handle_document_created(event: Event):
        print(f"Document created: {event.payload}")

    event_bus.subscribe("document.created", handle_document_created)

    # Publish events
    await event_bus.publish("document.created", {"doc_id": 123, "title": "Test"})
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Standard event types used across the system."""
    # Document events
    DOCUMENT_CREATED = "document.created"
    DOCUMENT_UPDATED = "document.updated"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_VIEWED = "document.viewed"

    # Collaboration events
    COMMENT_ADDED = "comment.added"
    COMMENT_UPDATED = "comment.updated"
    COMMENT_DELETED = "comment.deleted"
    COMMENT_RESOLVED = "comment.resolved"
    DOCUMENT_SHARED = "document.shared"
    DOCUMENT_LOCKED = "document.locked"
    DOCUMENT_UNLOCKED = "document.unlocked"

    # User events
    USER_ACTIVITY = "user.activity"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"

    # Workflow events
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"

    # Search events
    SEARCH_PERFORMED = "search.performed"
    SEARCH_RESULT_CLICKED = "search.result_clicked"

    # AI events
    AI_ANALYSIS_COMPLETED = "ai.analysis_completed"
    AI_EMBEDDING_COMPLETED = "ai.embedding_completed"

    # Recommendation events
    RECOMMENDATION_GENERATED = "recommendation.generated"
    RECOMMENDATION_DISMISSED = "recommendation.dismissed"


@dataclass
class Event:
    """Represents an event in the system."""
    type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str | None = None  # Optional source identifier
    event_id: str | None = None  # Optional unique event ID

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "type": self.type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "event_id": self.event_id,
        }


# Type alias for event handlers
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBus:
    """Simple async pub/sub event bus.

    Events are dispatched to subscribers asynchronously. Each subscriber
    receives events in the order they were published. If a subscriber
    raises an exception, it is logged but does not affect other subscribers.
    """

    def __init__(self):
        self._subscribers: dict[str, list[EventHandler]] = {}
        self._wildcard_subscribers: list[EventHandler] = []
        self._lock = asyncio.Lock()
        self._event_history: list[Event] = []
        self._max_history = 1000  # Keep last N events for debugging

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to a specific event type.

        Args:
            event_type: The event type to subscribe to (e.g., "document.created")
            handler: Async function to call when event is published
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug("Subscribed handler %s to event %s", handler.__name__, event_type)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe to all events (wildcard subscription).

        Args:
            handler: Async function to call for any event
        """
        self._wildcard_subscribers.append(handler)
        logger.debug("Subscribed handler %s to all events", handler.__name__)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type.

        Args:
            event_type: The event type to unsubscribe from
            handler: The handler to remove
        """
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]
            logger.debug("Unsubscribed handler %s from event %s", handler.__name__, event_type)

    async def publish(self, event_type: str, payload: dict[str, Any], source: str | None = None) -> None:
        """Publish an event to all subscribers.

        Args:
            event_type: The event type to publish
            payload: Event data dictionary
            source: Optional source identifier
        """
        event = Event(type=event_type, payload=payload, source=source)

        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Get subscribers for this event type
        handlers = self._subscribers.get(event_type, [])
        all_handlers = handlers + self._wildcard_subscribers

        if not all_handlers:
            logger.debug("No subscribers for event %s", event_type)
            return

        logger.debug("Publishing event %s to %d subscribers", event_type, len(all_handlers))

        # Dispatch to all subscribers
        for handler in all_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "Error in event handler %s for event %s: %s",
                    handler.__name__, event_type, e,
                    exc_info=True,
                )

    def get_subscribers(self, event_type: str) -> list[EventHandler]:
        """Get list of subscribers for an event type.

        Args:
            event_type: The event type to query

        Returns:
            List of subscribed handlers
        """
        return self._subscribers.get(event_type, [])

    def get_event_history(self, event_type: str | None = None, limit: int = 100) -> list[Event]:
        """Get recent event history.

        Args:
            event_type: Optional filter by event type
            limit: Maximum number of events to return

        Returns:
            List of recent events
        """
        events = self._event_history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()

    @property
    def subscriber_count(self) -> dict[str, int]:
        """Get count of subscribers per event type."""
        return {event_type: len(handlers) for event_type, handlers in self._subscribers.items()}


# Global event bus instance
event_bus = EventBus()


# Convenience functions for common operations
async def publish_document_created(doc_id: int, title: str, user_id: int) -> None:
    """Publish a document created event."""
    await event_bus.publish(
        EventType.DOCUMENT_CREATED,
        {"doc_id": doc_id, "title": title, "user_id": user_id},
        source="documents_api",
    )


async def publish_document_updated(doc_id: int, title: str, user_id: int) -> None:
    """Publish a document updated event."""
    await event_bus.publish(
        EventType.DOCUMENT_UPDATED,
        {"doc_id": doc_id, "title": title, "user_id": user_id},
        source="documents_api",
    )


async def publish_document_deleted(doc_id: int, user_id: int) -> None:
    """Publish a document deleted event."""
    await event_bus.publish(
        EventType.DOCUMENT_DELETED,
        {"doc_id": doc_id, "user_id": user_id},
        source="documents_api",
    )


async def publish_document_viewed(doc_id: int, user_id: int) -> None:
    """Publish a document viewed event."""
    await event_bus.publish(
        EventType.DOCUMENT_VIEWED,
        {"doc_id": doc_id, "user_id": user_id},
        source="documents_api",
    )


async def publish_comment_added(doc_id: int, comment_id: int, user_id: int) -> None:
    """Publish a comment added event."""
    await event_bus.publish(
        EventType.COMMENT_ADDED,
        {"doc_id": doc_id, "comment_id": comment_id, "user_id": user_id},
        source="comments_api",
    )


async def publish_user_activity(user_id: int, activity_type: str, doc_id: int | None = None) -> None:
    """Publish a user activity event."""
    payload = {"user_id": user_id, "activity_type": activity_type}
    if doc_id:
        payload["doc_id"] = doc_id
    await event_bus.publish(
        EventType.USER_ACTIVITY,
        payload,
        source="activity_tracker",
    )


async def publish_search_performed(user_id: int, query: str, mode: str, results_count: int) -> None:
    """Publish a search performed event."""
    await event_bus.publish(
        EventType.SEARCH_PERFORMED,
        {"user_id": user_id, "query": query, "mode": mode, "results_count": results_count},
        source="search_api",
    )


async def publish_workflow_completed(workflow_id: int, run_id: int, user_id: int) -> None:
    """Publish a workflow completed event."""
    await event_bus.publish(
        EventType.WORKFLOW_COMPLETED,
        {"workflow_id": workflow_id, "run_id": run_id, "user_id": user_id},
        source="workflow_engine",
    )
