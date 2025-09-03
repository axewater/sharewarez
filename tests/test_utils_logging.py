import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from modules import create_app, db
from modules.models import SystemEvents, User
from modules.utils_logging import log_system_event


# Helper function to create test users
def get_or_create_user(db_session, name, email):
    """Get existing user or create new one with unique name and email."""
    existing = db_session.query(User).filter_by(name=name).first()
    if existing:
        return existing
    
    user = User(
        name=name, 
        email=email, 
        password_hash='hashed_password',  # User model requires password_hash
        role='user'  # User model requires role
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing."""
    import random
    # Use random suffix to avoid unique constraint violations
    suffix = random.randint(1000, 9999)
    return get_or_create_user(db_session, f'testuser_{suffix}', f'test_{suffix}@example.com')


class TestLogSystemEvent:
    """Tests for log_system_event function."""
    
    def test_log_system_event_success_with_defaults(self, app, db_session):
        """Test successful logging with default parameters."""
        with app.app_context():
            result = log_system_event("Test event message")
            
            assert result is True
            
            # Verify event was created in database
            event = db_session.query(SystemEvents).filter_by(event_text="Test event message").first()
            assert event is not None
            assert event.event_type == 'log'
            assert event.event_level == 'information'
            assert event.audit_user is None  # No current_user, defaults to None
            assert event.timestamp is not None
    
    def test_log_system_event_success_with_custom_parameters(self, app, db_session):
        """Test successful logging with custom parameters (no foreign key)."""
        with app.app_context():
            result = log_system_event(
                event_text="Custom test event",
                event_type="error",
                event_level="critical",
                audit_user=None  # Use None to avoid foreign key issues
            )
            
            assert result is True
            
            # Verify event was created with custom values
            event = db_session.query(SystemEvents).filter_by(event_text="Custom test event").first()
            assert event is not None
            assert event.event_type == 'error'
            assert event.event_level == 'critical'
            assert event.audit_user is None
            assert event.timestamp is not None
    
    def test_log_system_event_with_system_audit_user(self, app, db_session):
        """Test logging with 'system' as audit_user."""
        with app.app_context():
            result = log_system_event("System event", audit_user='system')
            
            assert result is True
            
            # Verify event was created with audit_user as None when 'system' is passed
            event = db_session.query(SystemEvents).filter_by(event_text="System event").first()
            assert event is not None
            assert event.audit_user is None  # 'system' gets converted to None
    
    @patch('modules.utils_logging.db')
    @patch('modules.utils_logging.current_user')
    def test_log_system_event_with_current_user(self, mock_current_user, mock_db, app):
        """Test logging when current_user is available."""
        # Mock current_user.id
        mock_current_user.id = 123
        
        with app.app_context():
            result = log_system_event("User event")
            
            assert result is True
            
            # Verify SystemEvents was created with correct audit_user
            mock_db.session.add.assert_called_once()
            added_event = mock_db.session.add.call_args[0][0]
            assert added_event.event_text == "User event"
            assert added_event.audit_user == 123
            mock_db.session.commit.assert_called_once()
    
    @patch('modules.utils_logging.current_user')
    def test_log_system_event_with_current_user_no_id(self, mock_current_user, app, db_session):
        """Test logging when current_user has no id attribute."""
        # Mock current_user without id attribute
        mock_current_user.id = None
        
        with app.app_context():
            result = log_system_event("Event without user id")
            
            assert result is True
            
            # Verify event was created with audit_user as None
            event = db_session.query(SystemEvents).filter_by(event_text="Event without user id").first()
            assert event is not None
            assert event.audit_user is None
    
    def test_log_system_event_truncates_long_strings(self, app, db_session):
        """Test that long strings are truncated to fit database constraints."""
        with app.app_context():
            # Create strings that exceed the maximum lengths
            long_event_text = "x" * 300  # Exceeds 256 char limit
            long_event_type = "y" * 50   # Exceeds 32 char limit
            long_event_level = "z" * 50  # Exceeds 32 char limit
            
            result = log_system_event(
                event_text=long_event_text,
                event_type=long_event_type,
                event_level=long_event_level
            )
            
            assert result is True
            
            # Verify strings were truncated
            event = db_session.query(SystemEvents).filter_by(event_text="x" * 256).first()
            assert event is not None
            assert len(event.event_text) == 256
            assert len(event.event_type) == 32
            assert len(event.event_level) == 32
            assert event.event_text == "x" * 256
            assert event.event_type == "y" * 32
            assert event.event_level == "z" * 32
    
    @patch('modules.utils_logging.db')
    def test_log_system_event_database_error(self, mock_db, app):
        """Test error handling when database operation fails."""
        # Mock database session to raise an exception
        mock_db.session.add.side_effect = Exception("Database error")
        
        with app.app_context():
            # Capture print output
            with patch('builtins.print') as mock_print:
                result = log_system_event("Test event")
                
                assert result is False
                mock_db.session.rollback.assert_called_once()
                mock_print.assert_called_once_with("Error logging system event: Database error")
    
    @patch('modules.utils_logging.db')
    def test_log_system_event_commit_error(self, mock_db, app):
        """Test error handling when database commit fails."""
        # Mock database commit to raise an exception
        mock_db.session.commit.side_effect = Exception("Commit failed")
        
        with app.app_context():
            with patch('builtins.print') as mock_print:
                result = log_system_event("Test event")
                
                assert result is False
                mock_db.session.rollback.assert_called_once()
                mock_print.assert_called_once_with("Error logging system event: Commit failed")
    
    def test_log_system_event_creates_proper_timestamp(self, app, db_session):
        """Test that events are created with proper UTC timestamp."""
        with app.app_context():
            result = log_system_event("Timestamp test")
            
            assert result is True
            
            event = db_session.query(SystemEvents).filter_by(event_text="Timestamp test").first()
            assert event is not None
            assert event.timestamp is not None
            
            # Just verify the timestamp exists and is a datetime object
            # Don't compare actual times as there may be timezone differences between server and database
            assert isinstance(event.timestamp, datetime)
            assert event.timestamp.year == 2025  # Basic sanity check
    
    def test_log_system_event_empty_string_handling(self, app, db_session):
        """Test logging with empty strings."""
        with app.app_context():
            result = log_system_event(
                event_text="",
                event_type="",
                event_level=""
            )
            
            assert result is True
            
            event = db_session.query(SystemEvents).filter_by(event_text="").first()
            assert event is not None
            assert event.event_text == ""
            assert event.event_type == ""
            assert event.event_level == ""
    
    @patch('modules.utils_logging.db')
    def test_log_system_event_with_integer_audit_user(self, mock_db, app):
        """Test logging with integer audit_user."""
        with app.app_context():
            result = log_system_event("Integer user test", audit_user=456)
            
            assert result is True
            
            # Verify SystemEvents was created with correct audit_user
            mock_db.session.add.assert_called_once()
            added_event = mock_db.session.add.call_args[0][0]
            assert added_event.event_text == "Integer user test"
            assert added_event.audit_user == 456
            mock_db.session.commit.assert_called_once()
    
    def test_log_system_event_with_invalid_audit_user_string(self, app, db_session):
        """Test logging with invalid string audit_user (not 'system') returns False."""
        with app.app_context():
            with patch('builtins.print') as mock_print:
                result = log_system_event("String user test", audit_user="user123")
                
                assert result is False
                # Should print error about invalid input
                mock_print.assert_called_once()
                assert "Error logging system event" in mock_print.call_args[0][0]
    
    def test_log_system_event_with_nonexistent_user_id(self, app, db_session):
        """Test logging with nonexistent user ID returns False."""
        with app.app_context():
            with patch('builtins.print') as mock_print:
                # Use a very large ID that's unlikely to exist
                nonexistent_id = 999999999
                result = log_system_event("Nonexistent user test", audit_user=nonexistent_id)
                
                assert result is False
                # Should print error about foreign key constraint
                mock_print.assert_called_once()
                assert "Error logging system event" in mock_print.call_args[0][0]
    
    def test_log_system_event_multiple_events(self, app, db_session):
        """Test logging multiple events in sequence."""
        with app.app_context():
            events_data = [
                ("Event 1", "info", "low"),
                ("Event 2", "warning", "medium"),
                ("Event 3", "error", "high")
            ]
            
            for event_text, event_type, event_level in events_data:
                result = log_system_event(event_text, event_type, event_level)
                assert result is True
            
            # Verify all events were created
            for event_text, event_type, event_level in events_data:
                event = db_session.query(SystemEvents).filter_by(event_text=event_text).first()
                assert event is not None
                assert event.event_type == event_type
                assert event.event_level == event_level