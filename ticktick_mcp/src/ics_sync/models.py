"""
Database models for ICS sync functionality
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class ICSSource(Base):
    """ICS calendar source configuration"""
    __tablename__ = 'ics_sources'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    project_id = Column(String(100), nullable=False)  # TickTick project ID
    enabled = Column(Boolean, default=True)
    sync_interval = Column(Integer, default=3600)  # seconds
    last_sync = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    mappings = relationship("SyncMapping", back_populates="source", cascade="all, delete-orphan")
    filter_rules = relationship("FilterRule", back_populates="source", cascade="all, delete-orphan")
    sync_history = relationship("SyncHistory", back_populates="source", cascade="all, delete-orphan")

class SyncMapping(Base):
    """Mapping between ICS events and TickTick tasks"""
    __tablename__ = 'sync_mappings'
    
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('ics_sources.id'), nullable=False)
    ics_uid = Column(String(200), nullable=False)
    ticktick_task_id = Column(String(100), nullable=False)
    ticktick_project_id = Column(String(100), nullable=False)
    ics_last_modified = Column(DateTime)
    ticktick_last_modified = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    source = relationship("ICSSource", back_populates="mappings")
    
    # Unique constraint
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class FilterRule(Base):
    """Filter rules for ICS events"""
    __tablename__ = 'filter_rules'
    
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('ics_sources.id'), nullable=False)
    rule_type = Column(String(50), nullable=False)  # 'exclude_keyword', 'include_attendee', 'time_range'
    rule_value = Column(Text, nullable=False)  # JSON string for complex rules
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    source = relationship("ICSSource", back_populates="filter_rules")

class SyncHistory(Base):
    """Synchronization history and logs"""
    __tablename__ = 'sync_history'
    
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('ics_sources.id'), nullable=False)
    sync_start = Column(DateTime, nullable=False)
    sync_end = Column(DateTime)
    status = Column(String(20))  # 'success', 'failed', 'partial'
    events_processed = Column(Integer, default=0)
    events_created = Column(Integer, default=0)
    events_updated = Column(Integer, default=0)
    events_deleted = Column(Integer, default=0)
    conflicts_detected = Column(Integer, default=0)
    error_message = Column(Text)
    
    # Relationships
    source = relationship("ICSSource", back_populates="sync_history")

class SyncConflict(Base):
    """Conflict records for manual resolution"""
    __tablename__ = 'sync_conflicts'

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('ics_sources.id'), nullable=False)
    ics_uid = Column(String(200), nullable=False)
    ticktick_task_id = Column(String(100))
    conflict_type = Column(String(50))  # 'both_modified', 'delete_conflict'
    ics_data = Column(Text)  # JSON
    ticktick_data = Column(Text)  # JSON
    detected_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime)
    resolution = Column(String(50))  # 'keep_ics', 'keep_ticktick', 'keep_both', 'delete_both'

class OAuthToken(Base):
    """OAuth access and refresh tokens"""
    __tablename__ = 'oauth_tokens'

    id = Column(Integer, primary_key=True)
    token = Column(String(200), unique=True, nullable=False, index=True)
    token_type = Column(String(20), nullable=False)  # 'access' or 'refresh'
    client_id = Column(String(100), nullable=False)
    username = Column(String(100))  # For authorization_code grant
    scope = Column(String(200))
    grant_type = Column(String(50))  # 'client_credentials', 'authorization_code', etc.
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # For refresh tokens: link to the access token they can refresh
    parent_token = Column(String(200))  # The access token this refresh token belongs to

    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

# Database initialization
def init_db(db_path=None):
    """Initialize the database"""
    if db_path is None:
        # Place database in the ics_sync directory
        db_path = os.path.join(os.path.dirname(__file__), 'ics_sync.db')
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    return Session()

# Helper function to get database session
def get_db_session(db_path=None):
    """Get a database session"""
    if db_path is None:
        # Place database in the ics_sync directory for easy packaging
        db_path = os.path.join(os.path.dirname(__file__), 'ics_sync.db')
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    engine = create_engine(f'sqlite:///{db_path}')
    
    # Create tables if they don't exist
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    return Session()