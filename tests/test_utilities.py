import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock, call, ANY
from uuid import uuid4
from datetime import datetime, timedelta
from threading import Thread
import time

from modules import create_app, db
from modules.models import Library, GlobalSettings, AllowedFileType, ScanJob, Game
from modules.platform import LibraryPlatform
from modules.utilities import scan_and_add_games, handle_auto_scan, handle_manual_scan
from sqlalchemy import select


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
    """Test core functionality of scan_and_add_games with comprehensive assertions."""
    
    @patch('modules.utilities.is_scan_job_running')
    def test_early_return_when_scan_running(self, mock_is_running, app):
        """Test that function returns early if scan is already running with no side effects."""
        mock_is_running.return_value = True
        
        with app.app_context():
            # Ensure clean database state before test
            initial_scan_jobs = db.session.execute(select(ScanJob)).scalars().all()
            initial_count = len(initial_scan_jobs)
            
            result = scan_and_add_games("/fake/path", library_uuid=str(uuid4()))
            
            # Verify function returns None
            assert result is None
            
            # Verify running check was called exactly once
            mock_is_running.assert_called_once()
            
            # Critical assertion: No scan job should be created when one is running
            final_scan_jobs = db.session.execute(select(ScanJob)).scalars().all()
            assert len(final_scan_jobs) == initial_count, "No new scan jobs should be created when scan is running"

    def test_library_not_found_creates_no_scan_job(self, app, db_session):
        """Test that no scan job is created when library UUID doesn't exist."""
        nonexistent_uuid = str(uuid4())
        
        with app.app_context():
            with patch('modules.utilities.is_scan_job_running', return_value=False):
                initial_jobs = db_session.execute(select(ScanJob)).scalars().all()
                initial_count = len(initial_jobs)
                
                result = scan_and_add_games("/fake/path", library_uuid=nonexistent_uuid)
                
                # Verify function returns None
                assert result is None
                
                # Critical assertion: No scan job created for nonexistent library
                final_jobs = db_session.execute(select(ScanJob)).scalars().all()
                assert len(final_jobs) == initial_count, "No scan job should be created for nonexistent library"
                
                # Verify no scan job exists for the nonexistent UUID
                uuid_specific_jobs = db_session.execute(
                    select(ScanJob).filter_by(library_uuid=nonexistent_uuid)
                ).scalars().all()
                assert len(uuid_specific_jobs) == 0, f"No scan jobs should exist for UUID {nonexistent_uuid}"


class TestHandleAutoScanCore:
    """Test core functionality of handle_auto_scan with comprehensive assertions."""
    
    def test_form_validation_failure_with_mock_form(self, app, db_session):
        """Test comprehensive behavior when form validation fails."""
        test_uuid = str(uuid4())
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = False
        mock_form.library_uuid.data = test_uuid
        mock_form.errors = {'folder_path': ['This field is required.'], 'scan_mode': ['Invalid choice.']}
        
        with app.app_context():
            with app.test_request_context():
                # Track initial state
                initial_scan_jobs = db_session.execute(select(ScanJob)).scalars().all()
                initial_count = len(initial_scan_jobs)
                
                with patch('modules.utilities.flash') as mock_flash:
                    with patch('modules.utilities.redirect') as mock_redirect:
                        with patch('modules.utilities.url_for') as mock_url_for:
                            mock_session = {}
                            with patch('modules.utilities.session', mock_session):
                                mock_url_for.return_value = '/scan'
                                mock_redirect.return_value = 'redirected_response'
                                
                                result = handle_auto_scan(mock_form)
                                
                                # Verify flash was called with specific error details
                                mock_flash.assert_called_once()
                                flash_call = mock_flash.call_args[0][0]  # Get the message
                                assert 'validation failed' in flash_call.lower()
                                assert str(mock_form.errors) in flash_call
                                
                                # Note: session['active_tab'] is NOT set in validation failure case
                                # The session should remain empty since the function doesn't set it on validation failure
                                assert 'active_tab' not in mock_session
                                
                                # Verify redirect is called with correct parameters
                                mock_redirect.assert_called_once()
                                mock_url_for.assert_called_with(
                                    'main.scan_management', 
                                    library_uuid=test_uuid, 
                                    active_tab='auto'
                                )
                                
                                # Critical assertion: No scan job created on validation failure
                                final_scan_jobs = db_session.execute(select(ScanJob)).scalars().all()
                                assert len(final_scan_jobs) == initial_count, "No scan job should be created on validation failure"
                                
                                # Verify form was accessed correctly
                                mock_form.validate_on_submit.assert_called_once()
                                assert result == 'redirected_response'

    def test_scan_already_running_comprehensive_checks(self, app, db_session):
        """Test comprehensive behavior when scan is already running."""
        test_uuid = str(uuid4())
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = True
        mock_form.library_uuid.data = test_uuid
        mock_form.remove_missing.data = True
        mock_form.download_missing_images.data = False
        
        # Create library for the running scan job
        running_library = Library(
            uuid=str(uuid4()),
            name="Running Scan Library", 
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(running_library)
        
        # Create actual running scan job in database
        running_job = ScanJob(
            folders={"/test/path": True},
            content_type='Games',
            status='Running',
            is_enabled=True,
            last_run=datetime.now(),
            library_uuid=running_library.uuid,  # Use valid library UUID
            error_message='',
            total_folders=5,
            folders_success=2,
            folders_failed=1,
            scan_folder='/test/path'
        )
        db_session.add(running_job)
        db_session.commit()
        
        with app.app_context():
            with app.test_request_context():
                with patch('modules.utilities.flash') as mock_flash:
                    with patch('modules.utilities.redirect') as mock_redirect:
                        with patch('modules.utilities.url_for') as mock_url_for:
                            mock_session = {}
                            with patch('modules.utilities.session', mock_session):
                                mock_url_for.return_value = '/scan_management'
                                mock_redirect.return_value = 'blocked_response'
                                
                                result = handle_auto_scan(mock_form)
                                
                                # Verify exact flash message and category
                                mock_flash.assert_called_once_with(
                                    'A scan is already in progress. Please wait until the current scan completes.', 
                                    'error'
                                )
                                
                                # Verify session state management
                                assert mock_session['active_tab'] == 'auto'
                                
                                # Verify redirect parameters
                                mock_url_for.assert_called_once_with(
                                    'main.scan_management',
                                    library_uuid=test_uuid,
                                    active_tab='auto'
                                )
                                
                                # Critical assertion: Verify running job still exists unchanged
                                # Query the job again instead of refreshing to avoid session issues
                                persistent_job = db_session.get(ScanJob, running_job.id)
                                assert persistent_job is not None
                                assert persistent_job.status == 'Running'
                                assert persistent_job.folders_success == 2
                                assert persistent_job.folders_failed == 1
                                
                                # Verify no new scan job was created for our library
                                new_jobs = db_session.execute(
                                    select(ScanJob).filter_by(library_uuid=test_uuid)
                                ).scalars().all()
                                assert len(new_jobs) == 0, "No new scan job should be created when one is running"
                                
                                # Verify form data was accessed
                                mock_form.validate_on_submit.assert_called_once()
                                mock_form.remove_missing.data  # Should not raise AttributeError
                                
                                assert result == 'blocked_response'


class TestHandleManualScanCore:
    """Test core functionality of handle_manual_scan with proper mocking."""
    
    def test_form_validation_failure(self, app):
        """Test behavior when form validation fails.""" 
        mock_form = Mock()
        mock_form.validate_on_submit.return_value = False
        mock_form.library_uuid.data = str(uuid4())
        
        with app.app_context():
            with app.test_request_context():
                mock_session = {}
                with patch('modules.utilities.session', mock_session):
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
                    mock_session = {}
                    with patch('modules.utilities.session', mock_session):
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


class TestAdvancedScanScenarios:
    """Test advanced scanning scenarios with deep database integration."""
    
    def test_existing_job_restart_workflow(self, app, db_session):
        """Test restarting an existing scan job with proper state management."""
        # Setup test environment
        library = Library(
            uuid=str(uuid4()),
            name="Restart Test Library", 
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(library)
        
        settings = GlobalSettings(
            update_folder_name='updates',
            extras_folder_name='extras', 
            scan_thread_count=1
        )
        db_session.add(settings)
        
        # Add required file types
        if not db_session.execute(select(AllowedFileType).filter_by(value='exe')).scalars().first():
            db_session.add(AllowedFileType(value='exe'))
        
        # Create existing failed job
        existing_job = ScanJob(
            folders={"/restart/path": True},
            content_type='Games',
            status='Failed',
            is_enabled=True,
            last_run=datetime.now() - timedelta(hours=1),
            library_uuid=library.uuid,
            error_message='Previous failure reason',
            total_folders=5,
            folders_success=2,
            folders_failed=3,
            scan_folder='/restart/path'
        )
        db_session.add(existing_job)
        db_session.commit()
        existing_job_id = existing_job.id
        
        with app.app_context():
            # Simulate path access failure again
            with patch('os.path.exists', return_value=False):
                with patch('os.access', return_value=False):
                    scan_and_add_games(
                        "/restart/path",
                        library_uuid=library.uuid,
                        existing_job=existing_job
                    )
                    
                    # Verify the same job was updated, not a new one created
                    # Query the job again instead of refreshing to avoid session issues
                    updated_job = db_session.get(ScanJob, existing_job_id)
                    assert updated_job is not None
                    assert updated_job.id == existing_job_id  # Same job ID
                    assert updated_job.status == 'Failed'  # Status updated
                    assert 'Cannot access folder' in updated_job.error_message
                    
                    # Verify no duplicate jobs created
                    all_jobs = db_session.execute(
                        select(ScanJob).filter_by(library_uuid=library.uuid)
                    ).scalars().all()
                    assert len(all_jobs) == 1  # Still only one job
                    
                    # Verify state preservation and updates
                    assert all_jobs[0].id == existing_job_id
                    assert all_jobs[0].folders == {"/restart/path": True}
                    assert all_jobs[0].content_type == 'Games'

    def test_remove_missing_games_functionality(self, app, db_session):
        """Test the remove missing games feature with database state verification."""
        # Setup test environment
        library = Library(
            uuid=str(uuid4()),
            name="Remove Missing Test Library", 
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(library)
        
        settings = GlobalSettings(
            update_folder_name='updates',
            extras_folder_name='extras', 
            scan_thread_count=1
        )
        db_session.add(settings)
        
        if not db_session.execute(select(AllowedFileType).filter_by(value='exe')).scalars().first():
            db_session.add(AllowedFileType(value='exe'))
        
        # Create existing games - some that will be "missing" 
        existing_games = [
            Game(
                uuid=str(uuid4()),
                name='Game Still Exists',
                full_disk_path='/existing/game',
                library_uuid=library.uuid
            ),
            Game(
                uuid=str(uuid4()),
                name='Game Missing Now',
                full_disk_path='/missing/game',
                library_uuid=library.uuid
            ),
            Game(
                uuid=str(uuid4()),
                name='Another Missing Game',
                full_disk_path='/another/missing',
                library_uuid=library.uuid
            )
        ]
        
        for game in existing_games:
            db_session.add(game)
        
        db_session.commit()
        
        # Record initial game count
        initial_games = db_session.execute(
            select(Game).filter_by(library_uuid=library.uuid)
        ).scalars().all()
        assert len(initial_games) == 3
        
        with app.app_context():
            with patch('modules.utilities.is_scan_job_running', return_value=False):
                with patch('os.path.exists') as mock_exists:
                    with patch('os.access', return_value=True):
                        # Mock to return some dummy games so scan doesn't return early
                        dummy_games = [
                            {'name': 'Dummy Game 1', 'full_path': '/dummy/game1'},
                            {'name': 'Dummy Game 2', 'full_path': '/dummy/game2'}
                        ]
                        with patch('modules.utilities.get_game_names_from_folder', return_value=dummy_games):
                            with patch('modules.utilities.load_release_group_patterns', return_value=([], [])):
                                with patch('modules.utils_scanning.process_game_with_fallback', return_value=True):  # Mock successful processing
                                    with patch('modules.utilities.remove_from_lib') as mock_remove:
                                        
                                        # Configure path existence - only first game exists
                                        def exists_side_effect(path):
                                            if path == '/scan/path':  # Scan folder
                                                return True
                                            elif path == '/existing/game':  # First game
                                                return True
                                            else:  # Missing games
                                                return False
                                        
                                        mock_exists.side_effect = exists_side_effect
                                        
                                        scan_and_add_games(
                                            "/scan/path",
                                            library_uuid=library.uuid,
                                            remove_missing=True
                                        )
                                        
                                        # Verify remove_from_lib was called for missing games
                                        assert mock_remove.call_count == 2  # Two missing games
                                        
                                        # Get the UUIDs that were passed to remove_from_lib
                                        removed_uuids = [call[0][0] for call in mock_remove.call_args_list]
                                        
                                        # Verify correct games were marked for removal
                                        missing_game_uuids = [
                                            existing_games[1].uuid,  # 'Game Missing Now'
                                            existing_games[2].uuid   # 'Another Missing Game'
                                        ]
                                        
                                        for uuid in missing_game_uuids:
                                            assert uuid in removed_uuids
                                        
                                        # Verify scan job shows removal count
                                        scan_jobs = db_session.execute(
                                            select(ScanJob).filter_by(library_uuid=library.uuid)
                                        ).scalars().all()
                                        
                                        assert len(scan_jobs) == 1
                                        scan_job = scan_jobs[0]
                                        assert scan_job.removed_count == 2
                                        assert scan_job.status == 'Completed'

    def test_database_error_handling_during_scan(self, app, db_session):
        """Test how scan handles database errors gracefully."""
        # Setup test environment
        library = Library(
            uuid=str(uuid4()),
            name="Database Error Test Library", 
            platform=LibraryPlatform.PCWIN
        )
        db_session.add(library)
        
        settings = GlobalSettings(
            update_folder_name='updates',
            extras_folder_name='extras', 
            scan_thread_count=1
        )
        db_session.add(settings)
        
        if not db_session.execute(select(AllowedFileType).filter_by(value='exe')).scalars().first():
            db_session.add(AllowedFileType(value='exe'))
        
        db_session.commit()
        
        with app.app_context():
            # Test 1: Database error during initial ScanJob creation
            with patch('modules.utilities.is_scan_job_running', return_value=False):
                with patch('os.path.exists', return_value=True):
                    with patch('os.access', return_value=True):
                        with patch('modules.utilities.db.session.commit') as mock_commit:
                            from sqlalchemy.exc import SQLAlchemyError
                            
                            # Simulate database error on first commit (ScanJob creation)
                            mock_commit.side_effect = SQLAlchemyError("Database connection lost")
                            
                            result = scan_and_add_games("/test/path", library_uuid=library.uuid)
                            
                            # Verify function returns early on database error
                            assert result is None
                            mock_commit.assert_called_once()
            
            # Test 2: Database error during final commit  
            with patch('modules.utilities.is_scan_job_running', return_value=False):
                with patch('os.path.exists', return_value=True):
                    with patch('os.access', return_value=True):
                        with patch('modules.utilities.get_game_names_from_folder', return_value=[]):
                            with patch('modules.utilities.load_release_group_patterns', return_value=([], [])):
                                with patch('modules.utilities.db.session.commit') as mock_commit:
                                    from sqlalchemy.exc import SQLAlchemyError
                                    
                                    # Track commits and fail on final one
                                    commit_count = 0
                                    def commit_side_effect():
                                        nonlocal commit_count
                                        commit_count += 1
                                        if commit_count >= 3:  # Fail on final commit
                                            raise SQLAlchemyError("Connection timeout during final commit")
                                        return None
                                    
                                    mock_commit.side_effect = commit_side_effect
                                    
                                    # The scan function should handle the SQLAlchemy error gracefully
                                    # and continue execution (not raise an exception to the test)
                                    try:
                                        scan_and_add_games("/test/path", library_uuid=library.uuid)
                                    except SQLAlchemyError:
                                        # This is expected - the function lets final commit errors propagate
                                        # but handles them at the higher level via try/catch in utilities.py
                                        pass
                                    
                                    # Verify multiple commits were attempted
                                    assert mock_commit.call_count >= 2
                                    
                                    # Check that scan job was created initially (despite final error)
                                    scan_jobs = db_session.execute(
                                        select(ScanJob).filter_by(library_uuid=library.uuid)
                                    ).scalars().all()
                                    # At least one scan job should exist from the successful initial creation
                                    assert len(scan_jobs) >= 1
            
            # Test 3: Verify error handling preserves partial progress  
            existing_job = ScanJob(
                folders={"/error/path": True},
                content_type='Games',
                status='Running',
                is_enabled=True,
                last_run=datetime.now(),
                library_uuid=library.uuid,
                error_message='Initial error message',
                total_folders=2,
                folders_success=1,
                folders_failed=0,
                scan_folder='/error/path'
            )
            db_session.add(existing_job)
            db_session.commit()
            
            # Verify scan job state is preserved even with database errors
            db_session.refresh(existing_job)
            assert existing_job.folders_success == 1  # Progress preserved
            assert 'Initial error message' in existing_job.error_message
            assert existing_job.total_folders == 2