import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from modules import create_app, db
from modules.models import Library, GlobalSettings, AllowedFileType, ScanJob
from modules.platform import LibraryPlatform
from modules.utilities import scan_and_add_games, handle_auto_scan, handle_manual_scan


@pytest.fixture(scope='function')
def app():
    """Create and configure a test app."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['BASE_FOLDER_WINDOWS'] = 'C:\\Games'
    app.config['BASE_FOLDER_POSIX'] = '/var/games'
    yield app


@pytest.fixture(scope='function')  
def db_session(app):
    """Create a database session with rollback."""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        db.session.configure(bind=connection)
        
        yield db.session
        
        transaction.rollback()
        connection.close()
        db.session.remove()


class TestScanAndAddGamesCore:
    """Test core functionality of scan_and_add_games with minimal mocking."""
    
    @patch('modules.utilities.is_scan_job_running')
    def test_early_return_when_scan_running(self, mock_is_running, app):
        """Test that function returns early if scan is already running."""
        mock_is_running.return_value = True
        
        with app.app_context():
            result = scan_and_add_games("/fake/path")
            assert result is None
            mock_is_running.assert_called_once()

    @patch('modules.utilities.is_scan_job_running') 
    @patch('modules.utilities.db.session')
    def test_library_not_found_returns_none(self, mock_db_session, mock_is_running, app):
        """Test behavior when library UUID is not found."""
        mock_is_running.return_value = False
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
        
        with app.app_context():
            result = scan_and_add_games("/fake/path", library_uuid="nonexistent")
            assert result is None


class TestHandleAutoScanCore:
    """Test core functionality of handle_auto_scan with proper mocking."""
    
    def test_form_validation_failure_with_mock_form(self, app):
        """Test behavior when form validation fails."""
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = False
        mock_form.library_uuid.data = str(uuid4())
        mock_form.errors = {'field': ['error message']}
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utilities.flash') as mock_flash:
                    with patch('modules.utilities.redirect') as mock_redirect:
                        with patch('modules.utilities.url_for') as mock_url_for:
                            mock_url_for.return_value = '/scan'
                            
                            handle_auto_scan(mock_form)
                            
                            mock_flash.assert_called()
                            assert 'validation failed' in str(mock_flash.call_args)

    def test_scan_already_running_flash_message(self, app):
        """Test flash message when scan is already running."""
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = True
        mock_form.library_uuid.data = str(uuid4())
        
        mock_running_job = Mock()
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utilities.db.session') as mock_db_session:
                    with patch('modules.utilities.flash') as mock_flash:
                        with patch('modules.utilities.redirect'):
                            with patch('modules.utilities.url_for') as mock_url_for:
                                with patch('modules.utilities.session'):
                                    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_running_job
                                    mock_url_for.return_value = '/scan'
                                    
                                    handle_auto_scan(mock_form)
                                    
                                    mock_flash.assert_called_with(
                                        'A scan is already in progress. Please wait until the current scan completes.', 
                                        'error'
                                    )


class TestHandleManualScanCore:
    """Test core functionality of handle_manual_scan with proper mocking."""
    
    def test_form_validation_failure(self, app):
        """Test behavior when form validation fails.""" 
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = False
        mock_form.library_uuid.data = str(uuid4())
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utilities.session', {}) as mock_session:
                    with patch('modules.utilities.flash') as mock_flash:
                        with patch('modules.utilities.redirect'):
                            with patch('modules.utilities.url_for'):
                                handle_manual_scan(mock_form)
                                
                                mock_flash.assert_called_with('Manual scan form validation failed.', 'error')
                                assert mock_session['active_tab'] == 'manual'

    def test_scan_already_running(self, app):
        """Test behavior when scan is already running."""
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = True
        mock_form.library_uuid.data = str(uuid4())
        
        mock_running_job = Mock()
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utilities.db.session') as mock_db_session:
                    with patch('modules.utilities.session', {}) as mock_session:
                        with patch('modules.utilities.flash') as mock_flash:
                            with patch('modules.utilities.redirect'):
                                with patch('modules.utilities.url_for'):
                                    mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_running_job
                                    
                                    handle_manual_scan(mock_form)
                                    
                                    mock_flash.assert_called_with(
                                        'A scan is already in progress. Please wait until the current scan completes.', 
                                        'error'
                                    )
                                    assert mock_session['active_tab'] == 'manual'


class TestUtilitiesWithRealDatabase:
    """Test utilities with actual database integration (faster, focused tests)."""
    
    def test_scan_job_creation_with_real_db(self, app, db_session):
        """Test that scan job is created properly when library exists."""
        # Create test library
        library = Library(
            uuid=str(uuid4()),
            name="Test Library", 
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(library)
        
        # Create required settings
        settings = GlobalSettings(
            update_folder_name='updates',
            extras_folder_name='extras', 
            scan_thread_count=1
        )
        db_session.add(settings)
        
        # Create allowed file type to prevent empty list error (check if exists first)
        existing_file_type = db_session.query(AllowedFileType).filter_by(value='exe').first()
        if not existing_file_type:
            file_type = AllowedFileType(value='exe')
            db_session.add(file_type)
        
        db_session.commit()
        
        with app.app_context():
            with patch('modules.utilities.is_scan_job_running', return_value=False):
                with patch('os.path.exists', return_value=False):  # Force folder access failure
                    with patch('os.access', return_value=False):
                        scan_and_add_games("/nonexistent/path", library_uuid=library.uuid)
                        
                        # Check that scan job was created
                        scan_jobs = db_session.query(ScanJob).filter_by(library_uuid=library.uuid).all()
                        assert len(scan_jobs) > 0
                        assert scan_jobs[0].status == 'Failed'
                        assert 'Cannot access folder' in scan_jobs[0].error_message

    def test_library_validation(self, app, db_session):
        """Test that function handles missing library gracefully."""
        with app.app_context():
            with patch('modules.utilities.is_scan_job_running', return_value=False):
                result = scan_and_add_games("/fake/path", library_uuid="nonexistent-uuid")
                assert result is None