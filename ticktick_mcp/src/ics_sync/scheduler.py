"""
Scheduler for automatic ICS synchronization
"""

import logging
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from .models import ICSSource, get_db_session
from .sync_engine import ICSSyncEngine

logger = logging.getLogger(__name__)

class SyncScheduler:
    """Background scheduler for ICS synchronization"""
    
    def __init__(self, ticktick_client):
        self.ticktick_client = ticktick_client
        self.scheduler = BackgroundScheduler()
        self.sync_engine = ICSSyncEngine(ticktick_client)
        self.db_session = get_db_session()
        self._is_running = False
        self._sync_callbacks: Dict[str, Callable] = {}
    
    def start(self):
        """Start the scheduler"""
        if self._is_running:
            logger.warning("Scheduler is already running")
            return
        
        try:
            self.scheduler.start()
            self._is_running = True
            
            # Schedule periodic sync for all sources
            self._schedule_all_sources()
            
            logger.info("ICS Sync Scheduler started")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    def stop(self):
        """Stop the scheduler"""
        if not self._is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("ICS Sync Scheduler stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop scheduler: {e}")
    
    def _schedule_all_sources(self):
        """Schedule sync jobs for all enabled sources"""
        sources = self.db_session.query(ICSSource).filter_by(enabled=True).all()
        
        for source in sources:
            self._schedule_source(source)
    
    def _schedule_source(self, source: ICSSource):
        """Schedule sync job for a specific source"""
        job_id = f"sync_source_{source.id}"
        
        # Remove existing job if it exists
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
        
        # Calculate interval
        interval_seconds = source.sync_interval or 3600  # Default 1 hour
        
        # Schedule the job
        self.scheduler.add_job(
            func=self._sync_source_job,
            trigger=IntervalTrigger(seconds=interval_seconds),
            args=[source.id],
            id=job_id,
            name=f"Sync {source.name}",
            max_instances=1,  # Prevent overlapping syncs
            coalesce=True,    # Combine multiple pending executions
            misfire_grace_time=300  # 5 minutes grace time
        )
        
        logger.info(f"Scheduled sync for '{source.name}' every {interval_seconds} seconds")
    
    def _sync_source_job(self, source_id: int):
        """Execute sync job for a source"""
        try:
            logger.info(f"Starting scheduled sync for source {source_id}")
            
            result = self.sync_engine.sync_source(source_id)
            
            # Trigger callbacks
            self._trigger_callbacks('sync_completed', {
                'source_id': source_id,
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            if 'error' in result:
                logger.error(f"Scheduled sync failed for source {source_id}: {result['error']}")
                self._trigger_callbacks('sync_failed', {
                    'source_id': source_id,
                    'error': result['error'],
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                logger.info(f"Scheduled sync completed for source {source_id}: {result}")
                
                # Check for conflicts
                if result.get('stats', {}).get('conflicts', 0) > 0:
                    self._trigger_callbacks('conflicts_detected', {
                        'source_id': source_id,
                        'conflict_count': result['stats']['conflicts'],
                        'timestamp': datetime.utcnow().isoformat()
                    })
        
        except Exception as e:
            logger.error(f"Exception in scheduled sync for source {source_id}: {e}")
            self._trigger_callbacks('sync_error', {
                'source_id': source_id,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
    
    def add_source(self, source_id: int):
        """Add a new source to the scheduler"""
        if not self._is_running:
            logger.warning("Scheduler not running, source will be scheduled when started")
            return
        
        source = self.db_session.query(ICSSource).filter_by(id=source_id).first()
        if source and source.enabled:
            self._schedule_source(source)
    
    def remove_source(self, source_id: int):
        """Remove a source from the scheduler"""
        job_id = f"sync_source_{source_id}"
        
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed sync job for source {source_id}")
    
    def update_source_schedule(self, source_id: int):
        """Update schedule for a source (when interval changes)"""
        source = self.db_session.query(ICSSource).filter_by(id=source_id).first()
        if not source:
            return
        
        if source.enabled:
            self._schedule_source(source)
        else:
            self.remove_source(source_id)
    
    def sync_now(self, source_id: Optional[int] = None) -> Dict[str, Any]:
        """Trigger immediate sync for a source or all sources"""
        if source_id:
            return self.sync_engine.sync_source(source_id)
        else:
            return self.sync_engine.sync_all_sources()
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        jobs = []
        
        if self._is_running:
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                jobs.append({
                    'id': job.id,
                    'name': job.name,
                    'next_run': next_run.isoformat() if next_run else None,
                    'trigger': str(job.trigger)
                })
        
        return {
            'running': self._is_running,
            'jobs': jobs,
            'job_count': len(jobs)
        }
    
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for scheduler events"""
        if event_type not in self._sync_callbacks:
            self._sync_callbacks[event_type] = []
        
        self._sync_callbacks[event_type].append(callback)
    
    def _trigger_callbacks(self, event_type: str, data: Dict[str, Any]):
        """Trigger callbacks for an event"""
        callbacks = self._sync_callbacks.get(event_type, [])
        
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Callback error for {event_type}: {e}")
    
    def schedule_daily_cleanup(self):
        """Schedule daily cleanup of old sync history"""
        self.scheduler.add_job(
            func=self._cleanup_old_records,
            trigger=CronTrigger(hour=2, minute=0),  # 2 AM daily
            id="daily_cleanup",
            name="Daily Cleanup",
            max_instances=1
        )
        
        logger.info("Scheduled daily cleanup at 2:00 AM")
    
    def _cleanup_old_records(self):
        """Clean up old sync history records"""
        try:
            # Keep last 30 days of sync history
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            from .models import SyncHistory
            old_records = self.db_session.query(SyncHistory).filter(
                SyncHistory.sync_start < cutoff_date
            ).all()
            
            count = len(old_records)
            for record in old_records:
                self.db_session.delete(record)
            
            self.db_session.commit()
            
            logger.info(f"Cleaned up {count} old sync history records")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")
            self.db_session.rollback()

# Global scheduler instance
_scheduler_instance: Optional[SyncScheduler] = None

def get_scheduler(ticktick_client=None) -> Optional[SyncScheduler]:
    """Get the global scheduler instance"""
    global _scheduler_instance
    
    if _scheduler_instance is None and ticktick_client:
        _scheduler_instance = SyncScheduler(ticktick_client)
    
    return _scheduler_instance

def start_scheduler(ticktick_client) -> SyncScheduler:
    """Start the global scheduler"""
    scheduler = get_scheduler(ticktick_client)
    if scheduler and not scheduler._is_running:
        scheduler.start()
        scheduler.schedule_daily_cleanup()
    
    return scheduler

def stop_scheduler():
    """Stop the global scheduler"""
    global _scheduler_instance
    
    if _scheduler_instance:
        _scheduler_instance.stop()
        _scheduler_instance = None