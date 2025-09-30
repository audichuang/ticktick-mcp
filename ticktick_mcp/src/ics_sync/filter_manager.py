"""
Filter manager for ICS event filtering
"""

import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class FilterManager:
    """Manage and apply filters to ICS events"""
    
    def __init__(self):
        self.filters = []
    
    def add_filter(self, rule_type: str, rule_value: Any, enabled: bool = True):
        """Add a filter rule"""
        self.filters.append({
            'type': rule_type,
            'value': rule_value,
            'enabled': enabled
        })
    
    def load_filters(self, filter_rules: List[Any]):
        """Load filters from database models"""
        self.filters = []
        for rule in filter_rules:
            if rule.enabled:
                try:
                    value = json.loads(rule.rule_value) if rule.rule_type != 'exclude_keyword' else rule.rule_value
                    self.add_filter(rule.rule_type, value, rule.enabled)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in filter rule {rule.id}")
    
    def should_include_event(self, event: Dict[str, Any]) -> bool:
        """Check if an event should be included based on all filters"""
        if not self.filters:
            return True  # No filters = include all
        
        # Apply all filters
        for filter_rule in self.filters:
            if not filter_rule['enabled']:
                continue
            
            filter_type = filter_rule['type']
            filter_value = filter_rule['value']
            
            # Check each filter type
            if filter_type == 'exclude_keyword':
                if self._matches_keyword(event, filter_value):
                    return False  # Exclude if keyword matches
            
            elif filter_type == 'include_attendee':
                if not self._has_attendee(event, filter_value):
                    return False  # Exclude if attendee not found
            
            elif filter_type == 'exclude_organizer':
                if self._has_organizer(event, filter_value):
                    return False  # Exclude if organizer matches
            
            elif filter_type == 'time_range':
                if not self._in_time_range(event, filter_value):
                    return False  # Exclude if outside time range
            
            elif filter_type == 'exclude_all_day':
                if event.get('is_all_day', False):
                    return False  # Exclude all-day events
            
            elif filter_type == 'required_attendee_count':
                if not self._meets_attendee_count(event, filter_value):
                    return False  # Exclude if attendee count doesn't meet criteria
        
        return True  # Include if all filters pass
    
    def _matches_keyword(self, event: Dict[str, Any], keyword: str) -> bool:
        """Check if event contains keyword (case-insensitive)"""
        keyword_lower = keyword.lower()
        
        # Check in summary
        if keyword_lower in event.get('summary', '').lower():
            return True
        
        # Check in description
        if keyword_lower in event.get('description', '').lower():
            return True
        
        # Check in location
        if keyword_lower in event.get('location', '').lower():
            return True
        
        return False
    
    def _has_attendee(self, event: Dict[str, Any], attendee_email: str) -> bool:
        """Check if specific attendee is in the event"""
        attendees = event.get('attendees', [])
        attendee_email_lower = attendee_email.lower()
        
        for attendee in attendees:
            if attendee_email_lower in attendee.get('email', '').lower():
                return True
        
        return False
    
    def _has_organizer(self, event: Dict[str, Any], organizer_email: str) -> bool:
        """Check if event organizer matches"""
        organizer = event.get('organizer', {})
        if not organizer:
            return False
        
        organizer_email_lower = organizer_email.lower()
        return organizer_email_lower in organizer.get('email', '').lower()
    
    def _in_time_range(self, event: Dict[str, Any], time_range: Dict[str, Any]) -> bool:
        """Check if event is within specified time range"""
        try:
            event_start = datetime.fromisoformat(event['start'])
            
            # Check future days limit
            if 'future_days' in time_range:
                future_limit = datetime.now() + timedelta(days=time_range['future_days'])
                if event_start > future_limit:
                    return False
            
            # Check past days limit
            if 'past_days' in time_range:
                past_limit = datetime.now() - timedelta(days=time_range['past_days'])
                if event_start < past_limit:
                    return False
            
            # Check specific date range
            if 'start_date' in time_range:
                start_limit = datetime.fromisoformat(time_range['start_date'])
                if event_start < start_limit:
                    return False
            
            if 'end_date' in time_range:
                end_limit = datetime.fromisoformat(time_range['end_date'])
                if event_start > end_limit:
                    return False
            
            return True
            
        except (ValueError, KeyError):
            return True  # Include if date parsing fails
    
    def _meets_attendee_count(self, event: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
        """Check if event meets attendee count criteria"""
        attendee_count = len(event.get('attendees', []))
        
        if 'min' in criteria and attendee_count < criteria['min']:
            return False
        
        if 'max' in criteria and attendee_count > criteria['max']:
            return False
        
        return True
    
    def get_default_filters(self) -> List[Dict[str, Any]]:
        """Get default filter rules for common scenarios"""
        return [
            {
                'type': 'exclude_keyword',
                'value': '全員會議',
                'description': 'Exclude company-wide meetings'
            },
            {
                'type': 'exclude_keyword',
                'value': '全体会議',
                'description': 'Exclude all-hands meetings'
            },
            {
                'type': 'time_range',
                'value': {'future_days': 30},
                'description': 'Only sync events within next 30 days'
            },
            {
                'type': 'required_attendee_count',
                'value': {'max': 50},
                'description': 'Exclude meetings with more than 50 attendees'
            }
        ]