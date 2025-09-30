"""
ICS file parser for calendar event extraction
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import requests
from icalendar import Calendar, Event
import pytz

logger = logging.getLogger(__name__)

class ICSParser:
    """Parse ICS calendar files and extract events"""
    
    def __init__(self):
        self.default_timezone = pytz.timezone('Asia/Taipei')
    
    def fetch_ics(self, url: str) -> Optional[str]:
        """Fetch ICS content from URL"""
        try:
            headers = {
                'User-Agent': 'TickTick-ICS-Sync/1.0',
                'Accept': 'text/calendar, application/calendar+xml, */*'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Failed to fetch ICS from {url}: {e}")
            return None
    
    def parse_ics(self, ics_content: str) -> List[Dict[str, Any]]:
        """Parse ICS content and return list of events"""
        events = []
        
        try:
            cal = Calendar.from_ical(ics_content)
            
            for component in cal.walk():
                if component.name == "VEVENT":
                    event = self._parse_event(component)
                    if event:
                        events.append(event)
        
        except Exception as e:
            logger.error(f"Failed to parse ICS content: {e}")
        
        return events
    
    def _parse_event(self, event: Event) -> Optional[Dict[str, Any]]:
        """Parse a single calendar event"""
        try:
            # Extract basic properties
            uid = str(event.get('UID', ''))
            summary = str(event.get('SUMMARY', ''))
            description = str(event.get('DESCRIPTION', ''))
            location = str(event.get('LOCATION', ''))
            
            # Parse dates
            dtstart = event.get('DTSTART')
            dtend = event.get('DTEND')
            
            if not dtstart:
                return None
            
            # Convert to datetime with timezone
            start_dt = self._to_datetime(dtstart.dt)
            end_dt = self._to_datetime(dtend.dt) if dtend else start_dt
            
            # Check if all-day event
            is_all_day = not hasattr(dtstart.dt, 'hour')
            
            # Parse last modified
            last_modified = event.get('LAST-MODIFIED')
            if last_modified:
                last_modified_dt = self._to_datetime(last_modified.dt)
            else:
                last_modified_dt = datetime.now(timezone.utc)
            
            # Parse attendees
            attendees = []
            attendee_list = event.get('ATTENDEE', [])
            if not isinstance(attendee_list, list):
                attendee_list = [attendee_list]
            
            for attendee in attendee_list:
                email = str(attendee).replace('mailto:', '')
                attendees.append({
                    'email': email,
                    'cn': attendee.params.get('CN', email),
                    'role': attendee.params.get('ROLE', 'REQ-PARTICIPANT'),
                    'partstat': attendee.params.get('PARTSTAT', 'NEEDS-ACTION')
                })
            
            # Parse organizer
            organizer = event.get('ORGANIZER')
            if organizer:
                organizer_email = str(organizer).replace('mailto:', '')
                organizer_info = {
                    'email': organizer_email,
                    'cn': organizer.params.get('CN', organizer_email)
                }
            else:
                organizer_info = None
            
            # Parse recurrence rules
            rrule = event.get('RRULE')
            recurrence = None
            if rrule:
                recurrence = {
                    'freq': rrule.get('FREQ', ['DAILY'])[0],
                    'interval': rrule.get('INTERVAL', [1])[0],
                    'until': self._to_datetime(rrule.get('UNTIL', [None])[0]) if rrule.get('UNTIL') else None,
                    'count': rrule.get('COUNT', [None])[0]
                }
            
            # Build event dictionary
            parsed_event = {
                'uid': uid,
                'summary': summary,
                'description': description,
                'location': location,
                'start': start_dt.isoformat(),
                'end': end_dt.isoformat(),
                'is_all_day': is_all_day,
                'last_modified': last_modified_dt.isoformat(),
                'attendees': attendees,
                'organizer': organizer_info,
                'recurrence': recurrence,
                # Additional fields for TickTick conversion
                'categories': [str(cat) for cat in event.get('CATEGORIES', [])],
                'priority': event.get('PRIORITY', 0),
                'status': str(event.get('STATUS', 'CONFIRMED'))
            }
            
            return parsed_event
            
        except Exception as e:
            logger.error(f"Failed to parse event: {e}")
            return None
    
    def _to_datetime(self, dt: Any) -> datetime:
        """Convert various datetime formats to timezone-aware datetime"""
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                # Assume local timezone if not specified
                return self.default_timezone.localize(dt)
            return dt
        elif hasattr(dt, 'date'):
            # Handle date-only objects
            return self.default_timezone.localize(
                datetime.combine(dt, datetime.min.time())
            )
        else:
            # Fallback
            return datetime.now(timezone.utc)
    
    def event_to_ticktick_task(self, event: Dict[str, Any], project_id: str) -> Dict[str, Any]:
        """Convert ICS event to TickTick task format"""
        # Parse dates
        start_dt = datetime.fromisoformat(event['start'])
        end_dt = datetime.fromisoformat(event['end'])
        
        # Build task title with time if not all-day
        if event['is_all_day']:
            title = event['summary']
        else:
            start_time = start_dt.strftime('%H:%M')
            title = f"[{start_time}] {event['summary']}"
        
        # Build content
        content_parts = []
        if event['description']:
            content_parts.append(event['description'])
        if event['location']:
            content_parts.append(f"📍 Location: {event['location']}")
        if event['attendees']:
            attendee_list = ', '.join([a['cn'] for a in event['attendees'][:5]])
            if len(event['attendees']) > 5:
                attendee_list += f" (+{len(event['attendees']) - 5} more)"
            content_parts.append(f"👥 Attendees: {attendee_list}")
        
        content = '\n\n'.join(content_parts)
        
        # Set priority based on importance
        priority = 0  # Default
        if 'important' in event['summary'].lower() or event.get('priority', 0) >= 5:
            priority = 5  # High
        
        # Create task data
        task_data = {
            'title': title,
            'projectId': project_id,
            'content': content,
            'startDate': start_dt.isoformat(),
            'dueDate': end_dt.isoformat(),
            'isAllDay': event['is_all_day'],
            'priority': priority,
            'tags': event.get('categories', []),
            # Store ICS UID in custom field for tracking
            'customFields': {
                'ics_uid': event['uid'],
                'ics_last_modified': event['last_modified']
            }
        }
        
        # Add reminder if not all-day event
        if not event['is_all_day']:
            task_data['reminders'] = ['TRIGGER:PT15M']  # 15 minutes before
        
        return task_data