"""Stage Emitter for tracking verification progress in real-time.

This module provides a clean interface to emit verification stage events
to the UI without relying on log parsing.
"""

import uuid
from contextlib import contextmanager
from typing import Optional, Dict, Any
from queue import Queue


class StageEmitter:
    """Singleton emitter for verification stage events.
    
    Usage:
        # Set queue once in backend
        StageEmitter.set_queue(queue)
        
        # Emit stage events from procedure
        event_id = StageEmitter.emit(stage, status='inprogress', title='...', detail='...')
        
        # Update existing event
        StageEmitter.update(event_id, status='complete', detail='Results...')
        
        # Or use context manager for auto start/complete
        with StageEmitter.track(stage, title='...') as tracker:
            # Do work
            tracker.update_detail('Progress...')
    """
    
    _queue: Optional[Queue] = None
    _enabled: bool = True
    
    @classmethod
    def set_queue(cls, queue: Optional[Queue]):
        """Set the queue for emitting events."""
        cls._queue = queue
    
    @classmethod
    def enable(cls):
        """Enable event emission."""
        cls._enabled = True
    
    @classmethod
    def disable(cls):
        """Disable event emission (for testing)."""
        cls._enabled = False
    
    @classmethod
    def emit(cls, 
             stage,  # VerificationStage enum
             status: str = 'inprogress',
             title: Optional[str] = None,
             detail: Optional[str] = None,
             metadata: Optional[Dict[str, Any]] = None) -> str:
        """Emit a new stage event.
        
        Args:
            stage: VerificationStage enum value
            status: 'inprogress' or 'complete'
            title: Custom title (if None, uses stage.title with metadata)
            detail: Detail text (result or progress info)
            metadata: Dict for formatting title template (e.g., {'question': '...'})
        
        Returns:
            Event ID (UUID) for future updates
        """
        if not cls._enabled or cls._queue is None:
            return str(uuid.uuid4())  # Return dummy ID even if disabled
        
        event_id = str(uuid.uuid4())[:12]  # Short UUID
        
        # Format title with metadata if provided
        if title is None:
            title = stage.title
            if metadata:
                try:
                    title = title.format(**metadata)
                except (KeyError, ValueError):
                    pass  # Use template as-is if formatting fails
        
        event = {
            "type": "stage",
            "id": event_id,
            "status": status,
            "stage": stage.name,  # Enum name as string
            "stage_id": stage.value,  # Numeric ID for ordering
            "title": title,
            "detail": detail or stage.description,
        }
        
        cls._queue.put(event)
        return event_id
    
    @classmethod
    def update(cls,
               event_id: str,
               status: Optional[str] = None,
               detail: Optional[str] = None):
        """Update an existing event.
        
        Args:
            event_id: ID returned from emit()
            status: New status ('complete', etc.)
            detail: Updated detail text
        """
        if not cls._enabled or cls._queue is None:
            return
        
        update_event = {
            "type": "stage_update",
            "id": event_id,
        }
        
        if status is not None:
            update_event["status"] = status
        if detail is not None:
            update_event["detail"] = detail
        
        cls._queue.put(update_event)
    
    @classmethod
    @contextmanager
    def track(cls, 
              stage,
              title: Optional[str] = None,
              metadata: Optional[Dict[str, Any]] = None):
        """Context manager for auto start/complete tracking.
        
        Usage:
            with StageEmitter.track(VerificationStage.FORMULATE_QUESTION) as tracker:
                questions = pose_questions()
                tracker.update_detail(f"Generated {len(questions)} questions")
        
        Yields:
            EventTracker object with update_detail() method
        """
        event_id = cls.emit(stage, status='inprogress', title=title, metadata=metadata)
        
        class EventTracker:
            def __init__(self, eid):
                self.event_id = eid
                self.result_detail = None
            
            def update_detail(self, detail: str):
                """Update detail while still in progress."""
                self.result_detail = detail
                cls.update(self.event_id, detail=detail)
            
            def set_result(self, detail: str):
                """Set final result detail."""
                self.result_detail = detail
        
        tracker = EventTracker(event_id)
        
        try:
            yield tracker
            # Auto complete on success
            final_detail = tracker.result_detail if tracker.result_detail else "Hoàn thành"
            cls.update(event_id, status='complete', detail=final_detail)
        except Exception as e:
            # Mark as error
            cls.update(event_id, status='error', detail=f"Lỗi: {str(e)}")
            raise
