"""
Conflict resolution for ICS-TickTick sync
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from .models import SyncConflict, get_db_session

logger = logging.getLogger(__name__)

class ConflictResolver:
    """Handle conflicts between ICS events and TickTick tasks"""
    
    def __init__(self, ticktick_client):
        self.ticktick_client = ticktick_client
        self.db_session = get_db_session()
    
    def detect_conflict(
        self, 
        ics_event: Dict[str, Any], 
        ticktick_task: Dict[str, Any],
        mapping: Any
    ) -> Optional[str]:
        """Detect if there's a conflict between ICS event and TickTick task"""
        
        # Parse modification times
        try:
            ics_modified = datetime.fromisoformat(ics_event['last_modified'])
            # Handle missing modifiedTime field safely
            ticktick_modified_time = (ticktick_task.get('modifiedTime') or 
                                    ticktick_task.get('modified') or 
                                    ticktick_task.get('updatedTime'))
            if ticktick_modified_time:
                ticktick_modified = datetime.fromisoformat(ticktick_modified_time)
            else:
                # If no modification time available, assume it's very old
                ticktick_modified = datetime.min.replace(tzinfo=timezone.utc)
            
            # If both were modified since last sync
            if (mapping.ics_last_modified and mapping.ticktick_last_modified and
                ics_modified > mapping.ics_last_modified and 
                ticktick_modified > mapping.ticktick_last_modified):
                return 'both_modified'
            
            # Check for significant differences
            if self._has_significant_differences(ics_event, ticktick_task):
                return 'content_conflict'
            
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to parse modification times: {e}")
            return 'timestamp_error'
        
        return None
    
    def _has_significant_differences(
        self, 
        ics_event: Dict[str, Any], 
        ticktick_task: Dict[str, Any]
    ) -> bool:
        """Check if there are significant differences between event and task"""
        
        # Compare titles (removing time prefix from TickTick title)
        ticktick_title = ticktick_task.get('title', '')
        # Remove time prefix like [09:30]
        import re
        ticktick_title_clean = re.sub(r'^\[\d{2}:\d{2}\]\s*', '', ticktick_title)
        
        if ics_event.get('summary', '') != ticktick_title_clean:
            return True
        
        # Compare dates
        try:
            ics_start = datetime.fromisoformat(ics_event['start'])
            ticktick_start = datetime.fromisoformat(ticktick_task.get('startDate', ''))
            
            # Allow 1 minute difference for rounding
            if abs((ics_start - ticktick_start).total_seconds()) > 60:
                return True
        except (ValueError, TypeError):
            pass
        
        # Compare content (basic check)
        ics_desc = ics_event.get('description', '')
        ticktick_content = ticktick_task.get('content', '')
        
        # If content differs significantly (more than just formatting)
        if len(ics_desc) > 0 and len(ticktick_content) > 0:
            if ics_desc not in ticktick_content and ticktick_content not in ics_desc:
                return True
        
        return False
    
    def create_conflict_record(
        self,
        source_id: int,
        ics_uid: str,
        ticktick_task_id: str,
        conflict_type: str,
        ics_data: Dict[str, Any],
        ticktick_data: Dict[str, Any]
    ) -> SyncConflict:
        """Create a conflict record in the database"""
        
        conflict = SyncConflict(
            source_id=source_id,
            ics_uid=ics_uid,
            ticktick_task_id=ticktick_task_id,
            conflict_type=conflict_type,
            ics_data=json.dumps(ics_data, default=str),
            ticktick_data=json.dumps(ticktick_data, default=str),
            detected_at=datetime.utcnow()
        )
        
        self.db_session.add(conflict)
        self.db_session.commit()
        
        logger.info(f"Created conflict record {conflict.id} for {ics_uid}")
        
        return conflict
    
    def resolve_conflict(
        self, 
        conflict_id: int, 
        resolution: str,
        user_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Resolve a conflict with specified resolution strategy"""
        
        conflict = self.db_session.query(SyncConflict).filter_by(id=conflict_id).first()
        if not conflict:
            logger.error(f"Conflict {conflict_id} not found")
            return False
        
        try:
            ics_data = json.loads(conflict.ics_data)
            ticktick_data = json.loads(conflict.ticktick_data)
            
            success = False
            
            if resolution == 'keep_ics':
                success = self._apply_ics_version(conflict, ics_data, ticktick_data)
            
            elif resolution == 'keep_ticktick':
                success = self._apply_ticktick_version(conflict, ics_data, ticktick_data)
            
            elif resolution == 'keep_both':
                success = self._create_duplicate_task(conflict, ics_data, ticktick_data)
            
            elif resolution == 'merge_custom':
                if user_data:
                    success = self._apply_custom_merge(conflict, user_data)
            
            elif resolution == 'delete_both':
                success = self._delete_both_versions(conflict, ticktick_data)
            
            if success:
                conflict.resolved = True
                conflict.resolved_at = datetime.utcnow()
                conflict.resolution = resolution
                self.db_session.commit()
                
                logger.info(f"Resolved conflict {conflict_id} with strategy: {resolution}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to resolve conflict {conflict_id}: {e}")
            self.db_session.rollback()
        
        return False
    
    def _apply_ics_version(
        self, 
        conflict: SyncConflict, 
        ics_data: Dict[str, Any], 
        ticktick_data: Dict[str, Any]
    ) -> bool:
        """Apply ICS version, overwriting TickTick task"""
        try:
            # Get the project ID from the existing task
            project_id = ticktick_data.get('projectId')
            if not project_id:
                logger.error("No project ID found in TickTick task")
                return False
            
            # Convert ICS event to TickTick format
            from .ics_parser import ICSParser
            parser = ICSParser()
            updated_task = parser.event_to_ticktick_task(ics_data, project_id)
            
            # Update the task
            result = self.ticktick_client.update_task(
                task_id=conflict.ticktick_task_id,
                project_id=project_id,
                title=updated_task['title'],
                content=updated_task.get('content'),
                start_date=updated_task.get('startDate'),
                due_date=updated_task.get('dueDate'),
                priority=updated_task.get('priority', 0)
            )
            
            return 'error' not in result
            
        except Exception as e:
            logger.error(f"Failed to apply ICS version: {e}")
            return False
    
    def _apply_ticktick_version(
        self, 
        conflict: SyncConflict, 
        ics_data: Dict[str, Any], 
        ticktick_data: Dict[str, Any]
    ) -> bool:
        """Keep TickTick version, ignore ICS changes"""
        # Nothing to do - just mark as resolved
        return True
    
    def _create_duplicate_task(
        self, 
        conflict: SyncConflict, 
        ics_data: Dict[str, Any], 
        ticktick_data: Dict[str, Any]
    ) -> bool:
        """Create a duplicate task with ICS version"""
        try:
            project_id = ticktick_data.get('projectId')
            if not project_id:
                return False
            
            # Convert ICS event to TickTick format
            from .ics_parser import ICSParser
            parser = ICSParser()
            new_task = parser.event_to_ticktick_task(ics_data, project_id)
            
            # Add conflict indicator to title
            new_task['title'] = f"🔄 CONFLICT: {new_task['title']}"
            new_task['content'] = (
                f"⚠️ This is a duplicate created due to sync conflict.\n"
                f"Original task may have different details.\n\n"
                f"{new_task.get('content', '')}"
            )
            
            # Create new task
            result = self.ticktick_client.create_task(
                title=new_task['title'],
                project_id=project_id,
                content=new_task.get('content'),
                start_date=new_task.get('startDate'),
                due_date=new_task.get('dueDate'),
                priority=new_task.get('priority', 0)
            )
            
            return 'error' not in result
            
        except Exception as e:
            logger.error(f"Failed to create duplicate task: {e}")
            return False
    
    def _apply_custom_merge(
        self, 
        conflict: SyncConflict, 
        user_data: Dict[str, Any]
    ) -> bool:
        """Apply user-defined custom merge"""
        try:
            project_id = user_data.get('projectId')
            if not project_id:
                return False
            
            # Update task with user-provided data
            result = self.ticktick_client.update_task(
                task_id=conflict.ticktick_task_id,
                project_id=project_id,
                title=user_data.get('title'),
                content=user_data.get('content'),
                start_date=user_data.get('startDate'),
                due_date=user_data.get('dueDate'),
                priority=user_data.get('priority', 0)
            )
            
            return 'error' not in result
            
        except Exception as e:
            logger.error(f"Failed to apply custom merge: {e}")
            return False
    
    def _delete_both_versions(
        self, 
        conflict: SyncConflict, 
        ticktick_data: Dict[str, Any]
    ) -> bool:
        """Delete TickTick task (ICS event will be ignored in future syncs)"""
        try:
            project_id = ticktick_data.get('projectId')
            if not project_id:
                return False
            
            result = self.ticktick_client.delete_task(
                project_id=project_id,
                task_id=conflict.ticktick_task_id
            )
            
            return 'error' not in result
            
        except Exception as e:
            logger.error(f"Failed to delete task: {e}")
            return False
    
    def get_pending_conflicts(self, source_id: Optional[int] = None) -> List[SyncConflict]:
        """Get all pending conflicts"""
        query = self.db_session.query(SyncConflict).filter_by(resolved=False)
        
        if source_id:
            query = query.filter_by(source_id=source_id)
        
        return query.order_by(SyncConflict.detected_at.desc()).all()
    
    def get_conflict_summary(self) -> Dict[str, int]:
        """Get summary of conflicts by type"""
        conflicts = self.db_session.query(SyncConflict).filter_by(resolved=False).all()
        
        summary = {}
        for conflict in conflicts:
            conflict_type = conflict.conflict_type
            summary[conflict_type] = summary.get(conflict_type, 0) + 1
        
        return summary