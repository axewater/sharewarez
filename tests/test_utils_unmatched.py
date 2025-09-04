import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.exc import SQLAlchemyError
from modules.models import UnmatchedFolder, Library, ScanJob
from modules.utils_unmatched import handle_delete_unmatched


@pytest.fixture
def sample_library(db_session):
    """Create a sample library for testing."""
    from modules.models import LibraryPlatform
    library = Library(
        uuid=str(uuid4()),
        name='Test Library',
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.flush()
    return library


@pytest.fixture
def sample_scan_job(db_session):
    """Create a sample scan job for testing."""
    scan_job = ScanJob(
        id=str(uuid4()),
        content_type='Games',
        status='Completed'
    )
    db_session.add(scan_job)
    db_session.flush()
    return scan_job


@pytest.fixture
def sample_unmatched_folders(db_session, sample_library, sample_scan_job):
    """Create sample unmatched folders for testing."""
    folders = []
    
    # Create folders with different statuses
    statuses = ['Unmatched', 'Pending', 'Ignore', 'Duplicate']
    
    for i, status in enumerate(statuses):
        folder = UnmatchedFolder(
            id=str(uuid4()),
            library_uuid=sample_library.uuid,
            scan_job_id=sample_scan_job.id,
            folder_path=f'/test/path/folder_{i}',
            failed_time=datetime.now(timezone.utc),
            content_type='Games',
            status=status
        )
        folders.append(folder)
        db_session.add(folder)
    
    db_session.flush()
    return folders


class TestHandleDeleteUnmatchedOnly:
    """Tests for handle_delete_unmatched function with all=False (replaces clear_only_unmatched_folders tests)."""

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_only_success(self, mock_logger, mock_flash, 
                                                 mock_url_for, mock_redirect, mock_log_system_event,
                                                 app, db_session, sample_unmatched_folders):
        """Test successful clearing of only unmatched folders using handle_delete_unmatched(all=False)."""
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=False)
                    
                    # Verify function calls
                    mock_flash.assert_called_once()
                    flash_message = mock_flash.call_args[0][0]
                    assert 'Unmatched folders with status "Unmatched" cleared successfully' in flash_message
                    assert 'success' in mock_flash.call_args[0]
                    
                    # Verify audit logging was called
                    mock_log_system_event.assert_called()
                    
                    mock_url_for.assert_called_once_with('main.scan_management')
                    mock_redirect.assert_called_once_with('/scan-management')
                    
                    assert result == mock_redirect_response

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_only_no_folders(self, mock_logger, mock_flash,
                                                    mock_url_for, mock_redirect, mock_log_system_event,
                                                    app, db_session, sample_library, sample_scan_job):
        """Test clearing when no unmatched folders exist."""
        # Create only non-unmatched folders
        folder = UnmatchedFolder(
            id=str(uuid4()),
            library_uuid=sample_library.uuid,
            scan_job_id=sample_scan_job.id,
            folder_path='/test/path/pending_folder',
            failed_time=datetime.now(timezone.utc),
            content_type='Games',
            status='Pending'
        )
        db_session.add(folder)
        db_session.flush()
        
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=False)
                    
                    # Verify success message even with 0 deletions
                    mock_flash.assert_called_once()
                    assert 'Unmatched folders with status "Unmatched" cleared successfully' in mock_flash.call_args[0][0]
                    
                    # Verify audit logging was called for 0 deletions
                    mock_log_system_event.assert_called()
                    
                    assert result == mock_redirect_response

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.db.session.execute')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_only_database_error(self, mock_logger, mock_flash,
                                                        mock_url_for, mock_redirect,
                                                        mock_execute, mock_log_system_event, app, db_session):
        """Test handling of database errors."""
        mock_execute.side_effect = SQLAlchemyError("Database connection failed")
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=False)
                    
                    # Verify error handling - generic message to user
                    mock_flash.assert_called_once()
                    assert 'Database error occurred while clearing folders' in mock_flash.call_args[0][0]
                    assert 'error' in mock_flash.call_args[0]
                    
                    # Verify error audit logging was called
                    mock_log_system_event.assert_called()
                    
                    assert result == mock_redirect_response

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.db.session.execute')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_only_unexpected_error(self, mock_logger, mock_flash,
                                                          mock_url_for, mock_redirect,
                                                          mock_execute, mock_log_system_event, app, db_session):
        """Test handling of unexpected errors."""
        mock_execute.side_effect = Exception("Unexpected error occurred")
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=False)
                    
                    # Verify error handling - generic message to user
                    mock_flash.assert_called_once()
                    assert 'An unexpected error occurred while clearing folders' in mock_flash.call_args[0][0]
                    assert 'error' in mock_flash.call_args[0]
                    
                    # Verify error audit logging was called
                    mock_log_system_event.assert_called()
                    
                    assert result == mock_redirect_response


class TestHandleDeleteUnmatched:
    """Tests for handle_delete_unmatched function."""

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_all_true(self, mock_logger, mock_flash, mock_url_for,
                                             mock_redirect, mock_log_system_event, app, db_session, sample_unmatched_folders):
        """Test deleting all unmatched folders when all=True."""
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        with app.app_context():
            with app.test_request_context():
                # Mock Flask-Login current_user and session within context
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=True)
                    
                    # Verify function calls
                    mock_flash.assert_called_once()
                    assert 'All unmatched folders cleared successfully' in mock_flash.call_args[0][0]
                    assert 'success' in mock_flash.call_args[0]
                    
                    # Verify audit logging was called
                    mock_log_system_event.assert_called()
                    
                    # Verify session was updated
                    mock_session.__setitem__.assert_called_with('active_tab', 'unmatched')
                    
                    mock_url_for.assert_called_once_with('main.scan_management')
                    mock_redirect.assert_called_once_with('/scan-management')
                    
                    assert result == mock_redirect_response

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_all_false(self, mock_logger, mock_flash, mock_url_for,
                                              mock_redirect, mock_log_system_event, app, db_session, sample_unmatched_folders):
        """Test deleting only 'Unmatched' status folders when all=False."""
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        with app.app_context():
            with app.test_request_context():
                # Mock Flask-Login current_user and session within context
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=False)
                    
                    # Verify function calls (check that correct message type was flashed)
                    mock_flash.assert_called_once()
                    assert 'Unmatched folders with status "Unmatched" cleared successfully' in mock_flash.call_args[0][0]
                    assert 'success' in mock_flash.call_args[0]
                    
                    # Verify audit logging was called
                    mock_log_system_event.assert_called()
                    
                    # Verify session was updated
                    mock_session.__setitem__.assert_called_with('active_tab', 'unmatched')
                    
                    assert result == mock_redirect_response

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.db.session.execute')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_database_error(self, mock_logger, mock_flash, mock_url_for,
                                                   mock_redirect, mock_execute, mock_log_system_event, app, db_session):
        """Test handling of database errors in handle_delete_unmatched."""
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        # Mock database error on first call
        mock_execute.side_effect = SQLAlchemyError("Database connection failed")
        
        with app.app_context():
            with app.test_request_context():
                # Mock Flask-Login current_user and session within context
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=True)
                    
                    # Verify error handling - generic message to user
                    mock_flash.assert_called_once()
                    assert 'Database error occurred while clearing folders' in mock_flash.call_args[0][0]
                    assert 'error' in mock_flash.call_args[0]
                    
                    # Verify error audit logging was called
                    mock_log_system_event.assert_called()
                    
                    assert result == mock_redirect_response

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.db.session.execute')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_unexpected_error(self, mock_logger, mock_flash, mock_url_for,
                                                     mock_redirect, mock_execute, mock_log_system_event, app, db_session):
        """Test handling of unexpected errors in handle_delete_unmatched."""
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        # Mock unexpected error on first call
        mock_execute.side_effect = Exception("Unexpected error occurred")
        
        with app.app_context():
            with app.test_request_context():
                # Mock Flask-Login current_user and session within context
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=False)
                    
                    # Verify error handling - generic message to user
                    mock_flash.assert_called_once()
                    assert 'An unexpected error occurred while clearing folders' in mock_flash.call_args[0][0]
                    assert 'error' in mock_flash.call_args[0]
                    
                    # Verify error audit logging was called
                    mock_log_system_event.assert_called()
                    
                    assert result == mock_redirect_response

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_no_folders_to_delete(self, mock_logger, mock_flash, mock_url_for,
                                                         mock_redirect, mock_log_system_event, app, db_session, 
                                                         sample_library, sample_scan_job):
        """Test handle_delete_unmatched when no folders exist to delete."""
        # Create only non-unmatched folders
        folder = UnmatchedFolder(
            id=str(uuid4()),
            library_uuid=sample_library.uuid,
            scan_job_id=sample_scan_job.id,
            folder_path='/test/path/pending_folder',
            failed_time=datetime.now(timezone.utc),
            content_type='Games',
            status='Pending'
        )
        db_session.add(folder)
        db_session.flush()
        
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        with app.app_context():
            with app.test_request_context():
                # Mock Flask-Login current_user and session within context
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    result = handle_delete_unmatched(all=False)
                    
                    # Verify success message even with 0 deletions
                    mock_flash.assert_called_once()
                    assert 'Unmatched folders with status "Unmatched" cleared successfully' in mock_flash.call_args[0][0]
                    assert 'success' in mock_flash.call_args[0]
                    
                    # Verify audit logging was called
                    mock_log_system_event.assert_called()
                    
                    assert result == mock_redirect_response

    @patch('modules.utils_unmatched.log_system_event')
    @patch('modules.utils_unmatched.redirect')
    @patch('modules.utils_unmatched.url_for')
    @patch('modules.utils_unmatched.flash')
    @patch('modules.utils_unmatched.logger')
    def test_handle_delete_unmatched_logging_output(self, mock_logger, mock_flash, mock_url_for,
                                                   mock_redirect, mock_log_system_event, app, db_session, sample_unmatched_folders):
        """Test that proper logging output is generated."""
        mock_url_for.return_value = '/scan-management'
        mock_redirect_response = MagicMock()
        mock_redirect.return_value = mock_redirect_response
        
        with app.app_context():
            with app.test_request_context():
                # Mock Flask-Login current_user and session within context
                with patch('modules.utils_unmatched.current_user') as mock_current_user, \
                     patch('modules.utils_unmatched.request') as mock_request, \
                     patch('modules.utils_unmatched.session') as mock_session:
                    
                    mock_current_user.name = 'testuser'
                    mock_current_user.role = 'admin'
                    mock_current_user.is_authenticated = True
                    mock_request.method = 'POST'
                    mock_session.__setitem__ = MagicMock()
                    
                    handle_delete_unmatched(all=True)
                    
                    # Verify proper logging calls were made
                    mock_logger.info.assert_called()
                    
                    # Verify audit logging was called
                    mock_log_system_event.assert_called()
                    
                    # Check that the logger was called with user info
                    log_calls = [str(call) for call in mock_logger.info.call_args_list]
                    assert any('testuser' in call for call in log_calls)