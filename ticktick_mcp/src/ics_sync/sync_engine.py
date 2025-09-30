"""
Main synchronization engine for ICS-TickTick sync
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from .models import ICSSource, SyncMapping, SyncHistory, get_db_session
from .ics_parser import ICSParser
from .filter_manager import FilterManager
from .conflict_resolver import ConflictResolver

logger = logging.getLogger(__name__)

class ICSSyncEngine:
    """Core synchronization engine"""
    
    def __init__(self, ticktick_client):
        self.ticktick_client = ticktick_client
        self.db_session = get_db_session()
        self.parser = ICSParser()
        self.filter_manager = FilterManager()
        self.conflict_resolver = ConflictResolver(ticktick_client)
    
    def sync_source(self, source_id: int) -> Dict[str, Any]:
        """Synchronize a single ICS source"""
        source = self.db_session.query(ICSSource).filter_by(id=source_id).first()
        if not source:
            return {'error': f'Source {source_id} not found'}
        
        if not source.enabled:
            return {'error': f'Source {source.name} is disabled'}
        
        # Start sync history record
        sync_history = SyncHistory(
            source_id=source_id,
            sync_start=datetime.utcnow(),
            status='running'
        )
        self.db_session.add(sync_history)
        self.db_session.commit()
        
        try:
            logger.info(f"Starting sync for source: {source.name}")
            
            # Fetch and parse ICS
            ics_content = self.parser.fetch_ics(source.url)
            if not ics_content:
                raise Exception(f"Failed to fetch ICS from {source.url}")
            
            events = self.parser.parse_ics(ics_content)
            logger.info(f"Parsed {len(events)} events from ICS")
            
            # Load and apply filters
            self.filter_manager.load_filters(source.filter_rules)
            filtered_events = [
                event for event in events 
                if self.filter_manager.should_include_event(event)
            ]
            logger.info(f"After filtering: {len(filtered_events)} events")
            
            # Sync events
            sync_stats = self._sync_events(source, filtered_events)
            
            # Update sync history
            sync_history.sync_end = datetime.utcnow()
            sync_history.status = 'success'
            sync_history.events_processed = len(filtered_events)
            sync_history.events_created = sync_stats['created']
            sync_history.events_updated = sync_stats['updated']
            sync_history.events_deleted = sync_stats['deleted']
            sync_history.conflicts_detected = sync_stats['conflicts']
            
            # Update source last sync time
            source.last_sync = datetime.utcnow()
            
            self.db_session.commit()
            
            result = {
                'success': True,
                'source_name': source.name,
                'events_processed': len(filtered_events),
                'stats': sync_stats
            }
            
            logger.info(f"Sync completed for {source.name}: {result}")
            return result
            
        except Exception as e:
            # Update sync history with failure
            sync_history.sync_end = datetime.utcnow()
            sync_history.status = 'failed'
            sync_history.error_message = str(e)
            self.db_session.commit()
            
            logger.error(f"Sync failed for {source.name}: {e}")
            return {'error': str(e)}
    
    def _sync_events(self, source: ICSSource, events: List[Dict[str, Any]]) -> Dict[str, int]:
        """Synchronize events with TickTick"""
        stats = {'created': 0, 'updated': 0, 'deleted': 0, 'conflicts': 0}
        
        # Get existing mappings
        existing_mappings = {
            mapping.ics_uid: mapping 
            for mapping in source.mappings
        }
        
        # Track which events we've seen
        processed_uids = set()
        
        for event in events:
            ics_uid = event['uid']
            processed_uids.add(ics_uid)
            
            existing_mapping = existing_mappings.get(ics_uid)
            
            if existing_mapping:
                # Update existing task
                result = self._update_existing_task(source, event, existing_mapping)
                if result == 'updated':
                    stats['updated'] += 1
                elif result == 'conflict':
                    stats['conflicts'] += 1
            else:
                # Create new task
                if self._create_new_task(source, event):
                    stats['created'] += 1
        
        # Handle deleted events (in ICS source but not in current fetch)
        for ics_uid, mapping in existing_mappings.items():
            if ics_uid not in processed_uids:
                if self._handle_deleted_event(source, mapping):
                    stats['deleted'] += 1
        
        return stats
    
    def _create_new_task(self, source: ICSSource, event: Dict[str, Any]) -> bool:
        """Create a new TickTick task from ICS event"""
        try:
            # Convert to TickTick format
            task_data = self.parser.event_to_ticktick_task(event, source.project_id)
            
            # Create task
            result = self.ticktick_client.create_task(
                title=task_data['title'],
                project_id=task_data['projectId'],
                content=task_data.get('content', ''),
                start_date=task_data.get('startDate'),
                due_date=task_data.get('dueDate'),
                priority=task_data.get('priority', 0)
            )
            
            if 'error' in result:
                logger.error(f"Failed to create task: {result['error']}")
                return False
            
            # Create mapping record
            # Handle missing modifiedTime field safely
            ticktick_modified_time = result.get('modifiedTime') or result.get('modified') or result.get('updatedTime')
            if not ticktick_modified_time:
                # Fallback to current time if no modification time is available
                ticktick_modified_time = datetime.utcnow().isoformat()
                logger.warning(f"No modifiedTime field in task creation response for event {event['uid']}, using current time")
            
            mapping = SyncMapping(
                source_id=source.id,
                ics_uid=event['uid'],
                ticktick_task_id=result['id'],
                ticktick_project_id=source.project_id,
                ics_last_modified=datetime.fromisoformat(event['last_modified']),
                ticktick_last_modified=datetime.fromisoformat(ticktick_modified_time)
            )
            
            self.db_session.add(mapping)
            self.db_session.commit()
            
            logger.info(f"Created task {result['id']} for event {event['uid']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create task for event {event['uid']}: {e}")
            return False
    
    def _update_existing_task(
        self, 
        source: ICSSource, 
        event: Dict[str, Any], 
        mapping: SyncMapping
    ) -> str:
        """Update existing TickTick task"""
        try:
            # Get current task from TickTick
            task_result = self.ticktick_client.get_task(
                mapping.ticktick_project_id, 
                mapping.ticktick_task_id
            )
            
            if 'error' in task_result:
                logger.error(f"Failed to get task {mapping.ticktick_task_id}: {task_result['error']}")
                return 'error'
            
            # Check for conflicts
            conflict_type = self.conflict_resolver.detect_conflict(event, task_result, mapping)
            
            if conflict_type:
                # Handle conflict
                self.conflict_resolver.create_conflict_record(
                    source_id=source.id,
                    ics_uid=event['uid'],
                    ticktick_task_id=mapping.ticktick_task_id,
                    conflict_type=conflict_type,
                    ics_data=event,
                    ticktick_data=task_result
                )
                logger.warning(f"Conflict detected for {event['uid']}: {conflict_type}")
                return 'conflict'
            
            # Check if update is needed
            ics_modified = datetime.fromisoformat(event['last_modified'])
            if mapping.ics_last_modified and ics_modified <= mapping.ics_last_modified:
                # No changes in ICS, skip update
                return 'skipped'
            
            # Update task
            task_data = self.parser.event_to_ticktick_task(event, source.project_id)
            
            result = self.ticktick_client.update_task(
                task_id=mapping.ticktick_task_id,
                project_id=mapping.ticktick_project_id,
                title=task_data['title'],
                content=task_data.get('content'),
                start_date=task_data.get('startDate'),
                due_date=task_data.get('dueDate'),
                priority=task_data.get('priority', 0)
            )
            
            if 'error' in result:
                logger.error(f"Failed to update task {mapping.ticktick_task_id}: {result['error']}")
                return 'error'
            
            # Update mapping
            # Handle missing modifiedTime field safely
            ticktick_modified_time = result.get('modifiedTime') or result.get('modified') or result.get('updatedTime')
            if not ticktick_modified_time:
                # Fallback to current time if no modification time is available
                ticktick_modified_time = datetime.utcnow().isoformat()
                logger.warning(f"No modifiedTime field in task update response for event {event['uid']}, using current time")
                
            mapping.ics_last_modified = ics_modified
            mapping.ticktick_last_modified = datetime.fromisoformat(ticktick_modified_time)
            mapping.updated_at = datetime.utcnow()
            
            self.db_session.commit()
            
            logger.info(f"Updated task {mapping.ticktick_task_id} for event {event['uid']}")
            return 'updated'
            
        except Exception as e:
            logger.error(f"Failed to update task for event {event['uid']}: {e}")
            return 'error'
    
    def _handle_deleted_event(self, source: ICSSource, mapping: SyncMapping) -> bool:
        """Handle event that was deleted from ICS source"""
        try:
            # For now, we don't delete tasks when events are removed from ICS
            # Instead, we could mark them with a special tag or move to archive
            
            # Option 1: Add a tag to indicate it's no longer in source calendar
            result = self.ticktick_client.get_task(
                mapping.ticktick_project_id, 
                mapping.ticktick_task_id
            )
            
            if 'error' not in result:
                # Update task content to indicate it's been removed from source
                current_content = result.get('content', '')
                if '📅 No longer in source calendar' not in current_content:
                    updated_content = f"📅 No longer in source calendar\n\n{current_content}"
                    
                    self.ticktick_client.update_task(
                        task_id=mapping.ticktick_task_id,
                        project_id=mapping.ticktick_project_id,
                        content=updated_content
                    )
            
            # Keep the mapping but mark it as deleted
            # (In future, we might add a 'deleted' field to SyncMapping)
            
            logger.info(f"Marked task {mapping.ticktick_task_id} as removed from source")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle deleted event {mapping.ics_uid}: {e}")
            return False
    
    def sync_all_sources(self) -> Dict[str, Any]:
        """Synchronize all enabled sources"""
        sources = self.db_session.query(ICSSource).filter_by(enabled=True).all()
        
        results = []
        total_stats = {'created': 0, 'updated': 0, 'deleted': 0, 'conflicts': 0}
        
        for source in sources:
            result = self.sync_source(source.id)
            results.append(result)
            
            if 'stats' in result:
                for key in total_stats:
                    total_stats[key] += result['stats'].get(key, 0)
        
        return {
            'total_sources': len(sources),
            'results': results,
            'total_stats': total_stats
        }
    
    def get_sync_status(self, source_id: Optional[int] = None) -> Dict[str, Any]:
        """Get synchronization status"""
        if source_id:
            sources = [self.db_session.query(ICSSource).filter_by(id=source_id).first()]
            if not sources[0]:
                return {'error': f'Source {source_id} not found'}
        else:
            sources = self.db_session.query(ICSSource).all()
        
        status_data = []
        
        for source in sources:
            # Get latest sync history
            latest_sync = (
                self.db_session.query(SyncHistory)
                .filter_by(source_id=source.id)
                .order_by(SyncHistory.sync_start.desc())
                .first()
            )
            
            # Get conflict count
            from .models import SyncConflict
            conflict_count = (
                self.db_session.query(SyncConflict)
                .filter_by(source_id=source.id, resolved=False)
                .count()
            )
            
            # Get mapping count
            mapping_count = len(source.mappings)
            
            source_status = {
                'id': source.id,
                'name': source.name,
                'url': source.url,
                'enabled': source.enabled,
                'last_sync': source.last_sync.isoformat() if source.last_sync else None,
                'sync_interval': source.sync_interval,
                'mapping_count': mapping_count,
                'pending_conflicts': conflict_count
            }
            
            if latest_sync:
                source_status['latest_sync'] = {
                    'status': latest_sync.status,
                    'start': latest_sync.sync_start.isoformat(),
                    'end': latest_sync.sync_end.isoformat() if latest_sync.sync_end else None,
                    'events_processed': latest_sync.events_processed,
                    'events_created': latest_sync.events_created,
                    'events_updated': latest_sync.events_updated,
                    'conflicts_detected': latest_sync.conflicts_detected,
                    'error_message': latest_sync.error_message
                }
            
            status_data.append(source_status)
        
        return {
            'sources': status_data,
            'total_sources': len(sources)
        }