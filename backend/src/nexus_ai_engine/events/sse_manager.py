"""
SSE Manager - Server-Sent Events connection manager for real-time job progress updates.

This module manages SSE connections per job_id and broadcasts events to all subscribers.
Events include: step_status, log, task_progress, job_complete

Thread-safety: This module is designed to be called from both async (FastAPI handlers)
and sync (job executor threads) contexts. It uses thread-safe data structures.

Memory-safety: Uses bounded queues with size limits and automatic stale connection cleanup.
"""

import asyncio
import json
import logging
import os
import threading
import time
import queue as thread_queue
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://redis-svc:6379/0")
SSE_HISTORY_MAX = int(os.getenv("SSE_HISTORY_MAX", "100"))
SSE_REDIS_ENABLED = os.getenv("SSE_REDIS_ENABLED", "true").lower() in ("1", "true", "yes")

try:
    import redis as redis_sync

    REDIS_AVAILABLE = True
except ImportError:
    redis_sync = None  # type: ignore
    REDIS_AVAILABLE = False

# Configuration constants for memory safety
MAX_QUEUE_SIZE = 100  # Maximum events per subscriber queue
STALE_CONNECTION_TIMEOUT_SECONDS = 300  # 5 minutes - cleanup connections with no activity
MAX_CONNECTIONS_PER_JOB = 50  # Maximum concurrent subscribers per job


class EventType(str, Enum):
    """SSE event types for job progress updates"""
    STEP_STATUS = "step_status"
    LOG = "log"
    TASK_PROGRESS = "task_progress"
    JOB_COMPLETE = "job_complete"
    ERROR = "error"


@dataclass
class JobEvent:
    """Represents an SSE event to be broadcast"""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + 'Z')
    
    def to_sse_format(self) -> str:
        """Format event for SSE transmission"""
        event_data = {**self.data, "timestamp": self.timestamp}
        return f"event: {self.event_type.value}\ndata: {json.dumps(event_data)}\n\n"


@dataclass
class ConnectionInfo:
    """Tracks connection metadata for cleanup purposes."""
    queue: thread_queue.Queue
    created_at: float
    last_activity: float


class SSEManager:
    """
    Manages Server-Sent Events connections for real-time job updates.
    
    Thread-safe implementation that works from both async and sync contexts.
    Memory-safe with bounded queues, connection limits, and stale connection cleanup.
    
    Usage:
        # In API endpoint (async)
        async def stream_job(job_id: str):
            async for event in sse_manager.subscribe(job_id):
                yield event
        
        # In job executor (sync - from any thread)
        sse_manager.broadcast_sync(job_id, JobEvent(
            event_type=EventType.STEP_STATUS,
            data={"step_id": "fetch_tasks", "status": "running"}
        ))
    """
    
    def __init__(self):
        # Use thread-safe queue.Queue for cross-thread communication
        # Now stores ConnectionInfo instead of raw queues for tracking
        self._connections: Dict[str, Dict[int, ConnectionInfo]] = {}
        self._lock = threading.Lock()  # Thread-safe lock (not asyncio.Lock)
        self._cleanup_task = None
        self._next_conn_id = 0
        self._redis_client = None
        self._redis_publish_only = False
        self._redis_listener_threads: Dict[str, threading.Thread] = {}
        logger.info("SSEManager initialized (thread-safe mode with memory limits)")

    def _redis_channel(self, job_id: str) -> str:
        return f"sse:job:{job_id}"

    def _redis_history_key(self, job_id: str) -> str:
        return f"sse:job:{job_id}:history"

    def _get_redis(self):
        if not REDIS_AVAILABLE or not SSE_REDIS_ENABLED:
            return None
        if self._redis_client is None:
            self._redis_client = redis_sync.from_url(REDIS_URL, decode_responses=True)
        return self._redis_client

    def enable_redis_bridge(self, publish_only: bool = False) -> None:
        """Workers publish-only; API pods subscribe and relay to SSE clients."""
        self._redis_publish_only = publish_only
        self._get_redis()

    def _publish_to_redis(self, job_id: str, event: JobEvent) -> None:
        client = self._get_redis()
        if client is None:
            return
        payload = json.dumps(
            {
                "event_type": event.event_type.value,
                "data": event.data,
                "timestamp": event.timestamp,
            }
        )
        try:
            pipe = client.pipeline()
            pipe.publish(self._redis_channel(job_id), payload)
            pipe.lpush(self._redis_history_key(job_id), payload)
            pipe.ltrim(self._redis_history_key(job_id), 0, SSE_HISTORY_MAX - 1)
            pipe.execute()
        except Exception as exc:
            logger.warning("Redis SSE publish failed for job %s: %s", job_id, exc)

    def _replay_history(self, job_id: str, event_queue: thread_queue.Queue) -> None:
        client = self._get_redis()
        if client is None:
            return
        try:
            items = client.lrange(self._redis_history_key(job_id), 0, SSE_HISTORY_MAX - 1)
            for raw in reversed(items or []):
                parsed = json.loads(raw)
                event = JobEvent(
                    event_type=EventType(parsed["event_type"]),
                    data=parsed.get("data") or {},
                    timestamp=parsed.get("timestamp") or datetime.utcnow().isoformat() + "Z",
                )
                try:
                    event_queue.put_nowait(event)
                except thread_queue.Full:
                    break
        except Exception as exc:
            logger.debug("SSE history replay failed for %s: %s", job_id, exc)

    def _ensure_redis_listener(self, job_id: str, event_queue: thread_queue.Queue) -> None:
        if self._redis_publish_only:
            return
        with self._lock:
            if job_id in self._redis_listener_threads:
                return

            def _listen():
                client = self._get_redis()
                if client is None:
                    return
                pubsub = client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(self._redis_channel(job_id))
                for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        parsed = json.loads(message["data"])
                        event = JobEvent(
                            event_type=EventType(parsed["event_type"]),
                            data=parsed.get("data") or {},
                            timestamp=parsed.get("timestamp")
                            or datetime.utcnow().isoformat() + "Z",
                        )
                        event_queue.put_nowait(event)
                    except Exception:
                        continue

            thread = threading.Thread(
                target=_listen,
                name=f"sse-redis-{job_id[:12]}",
                daemon=True,
            )
            self._redis_listener_threads[job_id] = thread
            thread.start()
    
    def _get_next_conn_id(self) -> int:
        """Get next unique connection ID."""
        self._next_conn_id += 1
        return self._next_conn_id
    
    def _cleanup_stale_connections(self) -> int:
        """
        Remove stale connections that haven't had activity.
        
        Returns:
            Number of connections cleaned up
        """
        now = time.time()
        cleaned = 0
        
        with self._lock:
            jobs_to_remove = []
            
            for job_id, connections in self._connections.items():
                stale_conn_ids = []
                for conn_id, conn_info in connections.items():
                    if now - conn_info.last_activity > STALE_CONNECTION_TIMEOUT_SECONDS:
                        stale_conn_ids.append(conn_id)
                
                for conn_id in stale_conn_ids:
                    del connections[conn_id]
                    cleaned += 1
                    logger.debug(f"Cleaned up stale SSE connection {conn_id} for job {job_id}")
                
                if not connections:
                    jobs_to_remove.append(job_id)
            
            for job_id in jobs_to_remove:
                del self._connections[job_id]
                logger.info(f"📡 Cleaned up all stale connections for job {job_id}")
        
        if cleaned > 0:
            logger.info(f"🧹 Cleaned up {cleaned} stale SSE connections")
        
        return cleaned
    
    async def subscribe(self, job_id: str) -> AsyncGenerator[str, None]:
        """
        Subscribe to job updates via SSE stream.
        
        Args:
            job_id: The job ID to subscribe to
            
        Yields:
            SSE-formatted event strings
        """
        # Use bounded queue to prevent memory leaks
        event_queue: thread_queue.Queue = thread_queue.Queue(maxsize=MAX_QUEUE_SIZE)
        conn_id = None
        
        with self._lock:
            if job_id not in self._connections:
                self._connections[job_id] = {}
            
            # Check connection limit
            if len(self._connections[job_id]) >= MAX_CONNECTIONS_PER_JOB:
                logger.warning(f"Connection limit reached for job {job_id}, rejecting subscriber")
                yield JobEvent(
                    event_type=EventType.ERROR,
                    data={"message": "Connection limit reached", "job_id": job_id}
                ).to_sse_format()
                return
            
            conn_id = self._get_next_conn_id()
            now = time.time()
            self._connections[job_id][conn_id] = ConnectionInfo(
                queue=event_queue,
                created_at=now,
                last_activity=now
            )
            subscriber_count = len(self._connections[job_id])
        
        logger.info(f"📡 SSE subscriber connected for job {job_id} (total: {subscriber_count})")

        yield ": connected\n\n"

        self._replay_history(job_id, event_queue)
        self._ensure_redis_listener(job_id, event_queue)
        
        # Send initial connection event
        yield JobEvent(
            event_type=EventType.STEP_STATUS,
            data={"message": "Connected to job stream", "job_id": job_id}
        ).to_sse_format()
        
        try:
            while True:
                try:
                    # Use non-blocking get with short sleep intervals for responsiveness
                    # Poll every 100ms for up to 30 seconds before sending keepalive
                    event = None
                    for _ in range(300):  # 300 iterations * 0.1 second = 30 second timeout
                        try:
                            event = event_queue.get_nowait()
                            break
                        except thread_queue.Empty:
                            await asyncio.sleep(0.1)  # Short sleep for responsiveness
                    
                    if event is not None:
                        # Update last activity timestamp
                        with self._lock:
                            if job_id in self._connections and conn_id in self._connections[job_id]:
                                self._connections[job_id][conn_id].last_activity = time.time()
                        
                        logger.debug(f"📤 SSE sending event: {event.event_type.value}")
                        yield event.to_sse_format()
                    else:
                        # Send keepalive comment to prevent connection timeout
                        # Also update activity to show connection is alive
                        with self._lock:
                            if job_id in self._connections and conn_id in self._connections[job_id]:
                                self._connections[job_id][conn_id].last_activity = time.time()
                        yield ": keepalive\n\n"
                        
                except Exception as e:
                    logger.warning(f"Error getting event from queue: {e}")
                    yield ": keepalive\n\n"
                    
        except asyncio.CancelledError:
            logger.debug(f"SSE subscription cancelled for job {job_id}")
        finally:
            with self._lock:
                if job_id in self._connections and conn_id is not None:
                    self._connections[job_id].pop(conn_id, None)
                    if not self._connections[job_id]:
                        del self._connections[job_id]
                        logger.info(f"📡 All SSE subscribers disconnected for job {job_id}")
                    else:
                        logger.info(f"📡 SSE subscriber disconnected for job {job_id} (remaining: {len(self._connections[job_id])})")
            if job_id not in self._connections:
                self._redis_listener_threads.pop(job_id, None)
    
    async def broadcast(self, job_id: str, event: JobEvent) -> int:
        """
        Broadcast an event to all subscribers of a job (async version).
        
        Args:
            job_id: The job ID to broadcast to
            event: The event to broadcast
            
        Returns:
            Number of subscribers the event was sent to
        """
        # Use sync broadcast internally since we now use thread-safe queues
        return self._broadcast_internal(job_id, event)
    
    def _broadcast_internal(self, job_id: str, event: JobEvent) -> int:
        """Internal thread-safe broadcast implementation with overflow handling"""
        with self._lock:
            if job_id not in self._connections:
                return 0
            
            # Get list of (conn_id, conn_info) tuples
            connections = list(self._connections[job_id].items())
        
        sent_count = 0
        dropped_count = 0
        
        for conn_id, conn_info in connections:
            try:
                conn_info.queue.put_nowait(event)
                sent_count += 1
            except thread_queue.Full:
                # Queue is full - drop oldest event and add new one
                dropped_count += 1
                try:
                    # Try to remove oldest event
                    conn_info.queue.get_nowait()
                    conn_info.queue.put_nowait(event)
                    sent_count += 1
                except (thread_queue.Empty, thread_queue.Full):
                    # If still can't add, just skip this subscriber
                    logger.warning(f"Event queue overflow for connection {conn_id} on job {job_id}")
            except Exception as e:
                logger.warning(f"Failed to send event to subscriber {conn_id}: {e}")
        
        if dropped_count > 0:
            logger.warning(f"Dropped {dropped_count} old events due to queue overflow for job {job_id}")
        
        if sent_count > 0:
            logger.debug(f"📤 Broadcast {event.event_type.value} to {sent_count} subscribers for job {job_id}")
        
        return sent_count
    
    def broadcast_sync(self, job_id: str, event: JobEvent) -> None:
        """
        Synchronous broadcast - thread-safe, can be called from any thread.
        Use this from synchronous code (e.g., in stage execution).
        
        Args:
            job_id: The job ID to broadcast to
            event: The event to broadcast
        """
        self._publish_to_redis(job_id, event)

        with self._lock:
            if job_id not in self._connections or not self._connections[job_id]:
                return
        
        sent = self._broadcast_internal(job_id, event)
        if sent > 0:
            logger.info(f"📡 SSE sync broadcast: {event.event_type.value} to {sent} subscribers for job {job_id}")
    
    def get_subscriber_count(self, job_id: str) -> int:
        """Get the number of active subscribers for a job"""
        with self._lock:
            return len(self._connections.get(job_id, {}))
    
    def get_active_jobs(self) -> List[str]:
        """Get list of job IDs with active subscribers"""
        with self._lock:
            return list(self._connections.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get SSE manager statistics for monitoring."""
        with self._lock:
            total_connections = sum(len(conns) for conns in self._connections.values())
            return {
                "active_jobs": len(self._connections),
                "total_connections": total_connections,
                "max_queue_size": MAX_QUEUE_SIZE,
                "max_connections_per_job": MAX_CONNECTIONS_PER_JOB,
                "stale_timeout_seconds": STALE_CONNECTION_TIMEOUT_SECONDS,
            }
    
    async def cleanup_job(self, job_id: str) -> None:
        """
        Clean up all connections for a job (call after job completes).
        
        Args:
            job_id: The job ID to clean up
        """
        self.cleanup_job_sync(job_id)
    
    def cleanup_job_sync(self, job_id: str) -> None:
        """
        Synchronous cleanup - thread-safe.
        
        Args:
            job_id: The job ID to clean up
        """
        with self._lock:
            if job_id in self._connections:
                # Notify all subscribers that job is done
                close_event = JobEvent(
                    event_type=EventType.JOB_COMPLETE,
                    data={"job_id": job_id, "message": "Job stream closed"}
                )
                for conn_id, conn_info in self._connections[job_id].items():
                    try:
                        conn_info.queue.put_nowait(close_event)
                    except (thread_queue.Full, Exception):
                        pass
                del self._connections[job_id]
                logger.info(f"🧹 Cleaned up SSE connections for job {job_id}")
    
    async def start_cleanup_task(self) -> None:
        """Start background task for periodic stale connection cleanup."""
        if self._cleanup_task is not None:
            return
        
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(60)  # Run every minute
                    self._cleanup_stale_connections()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in SSE cleanup task: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info("Started SSE stale connection cleanup task")
    
    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped SSE stale connection cleanup task")


# Global singleton instance
sse_manager = SSEManager()


# Convenience functions for common events
def emit_step_status(job_id: str, step_id: str, status: str, step_index: int, progress: int = 0, message: str = None, stage_id: str = None):
    """Emit a step status change event"""
    data = {
        "step_id": step_id,
        "status": status,
        "step_index": step_index,
        "progress": progress,
        "message": message,
    }
    if stage_id:
        data["stage_id"] = stage_id
    sse_manager.broadcast_sync(job_id, JobEvent(
        event_type=EventType.STEP_STATUS,
        data=data,
    ))


def emit_log(job_id: str, step_id: str, level: str, message: str, stage_id: str = None):
    """Emit a log entry event"""
    data = {
        "step_id": step_id,
        "level": level.lower(),
        "message": message,
    }
    if stage_id:
        data["stage_id"] = stage_id
    sse_manager.broadcast_sync(job_id, JobEvent(
        event_type=EventType.LOG,
        data=data,
    ))


def emit_task_progress(job_id: str, step_id: str, task_id: str, current: int, total: int, status: str = "processing"):
    """Emit a task progress event"""
    percentage = round((current / total) * 100) if total > 0 else 0
    logger.info(f"📊 emit_task_progress: job={job_id}, step={step_id}, {current}/{total} = {percentage}%")
    sse_manager.broadcast_sync(job_id, JobEvent(
        event_type=EventType.TASK_PROGRESS,
        data={
            "step_id": step_id,
            "task_id": task_id,
            "current": current,
            "total": total,
            "percentage": percentage,
            "status": status
        }
    ))


def emit_job_complete(job_id: str, status: str, duration_seconds: float, items_processed: int, items_total: int):
    """Emit a job completion event"""
    sse_manager.broadcast_sync(job_id, JobEvent(
        event_type=EventType.JOB_COMPLETE,
        data={
            "status": status,
            "duration": duration_seconds,
            "metrics": {
                "itemsProcessed": items_processed,
                "itemsTotal": items_total
            }
        }
    ))
