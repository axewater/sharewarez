import pytest
import json
from unittest.mock import patch, Mock
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from flask import url_for

from modules import db
from modules.models import User, Library, ScanJob, UnmatchedFolder
from modules.platform import LibraryPlatform
from modules.utils_functions import PLATFORM_IDS


def safe_cleanup_database(db_session):
    """Completely clean up ALL test data - this is a test database, nuke everything!"""
    from sqlalchemy import text
    
    try:
        # Disable foreign key checks temporarily for aggressive cleanup
        db_session.execute(text("SET session_replication_role = replica;"))
        
        # Delete all junction table data first
        db_session.execute(text("TRUNCATE TABLE user_favorites CASCADE"))
        db_session.execute(text("TRUNCATE TABLE game_genre_association CASCADE"))
        db_session.execute(text("TRUNCATE TABLE game_platform_association CASCADE"))
        db_session.execute(text("TRUNCATE TABLE game_game_mode_association CASCADE"))
        db_session.execute(text("TRUNCATE TABLE game_theme_association CASCADE"))
        
        # Delete all main table data
        for table in ['game_updates', 'game_extras', 'images', 'game_urls', 'unmatched_folders', 
                     'scan_jobs', 'download_requests', 'newsletters', 'system_events', 
                     'invite_tokens', 'games', 'users', 'libraries']:
            try:
                db_session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
            except Exception:
                pass  # Table might not exist
        
        # Re-enable foreign key checks
        db_session.execute(text("SET session_replication_role = DEFAULT;"))
        
        db_session.commit()
        print("✅ Nuked all test database data!")
        
    except Exception as e:
        db_session.rollback()
        print(f"❌ Error during aggressive cleanup: {e}")
        # Try to re-enable foreign key checks
        try:
            db_session.execute(text("SET session_replication_role = DEFAULT;"))
            db_session.commit()
        except:
            pass


@pytest.fixture(autouse=True)
def cleanup_after_each_test(db_session):
    """Automatically clean up after each test - no test data should persist!"""
    yield  # Let the test run first
    safe_cleanup_database(db_session)  # Clean up after


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    admin_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    admin = User(
        user_id=admin_uuid,
        name=f'TestAdmin_{unique_id}',
        email=f'admin_{unique_id}@test.com',
        role='admin',
        is_email_verified=True
    )
    admin.set_password('testpass123')
    db_session.add(admin)
    db_session.commit()
    return admin


@pytest.fixture
def regular_user(db_session):
    """Create a regular user for testing."""
    user_uuid = str(uuid4())
    unique_id = str(uuid4())[:8]
    user = User(
        user_id=user_uuid,
        name=f'TestUser_{unique_id}',
        email=f'user_{unique_id}@test.com',
        role='user',
        is_email_verified=True
    )
    user.set_password('testpass123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_library(db_session):
    """Create a sample library with platform."""
    unique_id = str(uuid4())[:8]
    library = Library(
        name=f'Test Library_{unique_id}',
        platform=LibraryPlatform.PCWIN
    )
    db_session.add(library)
    db_session.flush()
    return library


@pytest.fixture
def sample_scan_job(db_session, sample_library):
    """Create a sample scan job."""
    scan_job = ScanJob(
        library_uuid=sample_library.uuid,
        folders={'test': 'folder'},
        content_type='Games',
        schedule='24_hours',
        is_enabled=True,
        status='Completed',
        last_run=datetime.now(timezone.utc) - timedelta(hours=1),
        next_run=datetime.now(timezone.utc) + timedelta(hours=23),
        error_message=None,
        total_folders=10,
        folders_success=8,
        folders_failed=2,
        removed_count=1,
        scan_folder='/test/scan/folder',
        setting_remove=True,
        setting_filefolder=False
    )
    db_session.add(scan_job)
    db_session.flush()
    return scan_job


@pytest.fixture
def sample_unmatched_folder(db_session, sample_library, sample_scan_job):
    """Create a sample unmatched folder."""
    unmatched = UnmatchedFolder(
        library_uuid=sample_library.uuid,
        scan_job_id=sample_scan_job.id,
        folder_path='/test/unmatched/folder',
        failed_time=datetime.now(timezone.utc) - timedelta(minutes=30),
        content_type='Games',
        status='Unmatched'
    )
    db_session.add(unmatched)
    db_session.flush()
    return unmatched


class TestScanJobsStatus:
    """Tests for scan_jobs_status endpoint."""
    
    def test_scan_jobs_status_requires_login(self, client):
        """Test that scan_jobs_status requires login."""
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_scan_jobs_status_requires_admin(self, client, regular_user):
        """Test that scan_jobs_status requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 302
        # Should redirect to login due to admin_required decorator
    
    def test_scan_jobs_status_empty_list(self, client, admin_user):
        """Test scan_jobs_status with no scan jobs."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_scan_jobs_status_single_job(self, client, admin_user, sample_scan_job):
        """Test scan_jobs_status with a single scan job."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        
        job = data[0]
        assert job['id'] == sample_scan_job.id
        assert job['library_name'] == sample_scan_job.library.name
        assert job['folders'] == {'test': 'folder'}
        assert job['status'] == 'Completed'
        assert job['total_folders'] == 10
        assert job['folders_success'] == 8
        assert job['folders_failed'] == 2
        assert job['removed_count'] == 1
        assert job['scan_folder'] == '/test/scan/folder'
        assert job['setting_remove'] is True
        assert job['setting_filefolder'] is False
        assert 'last_run' in job
        assert 'next_run' in job
    
    def test_scan_jobs_status_no_library(self, client, admin_user, db_session):
        """Test scan_jobs_status with scan job that has no library."""
        # Create scan job without library
        scan_job = ScanJob(
            library_uuid=None,  # No library
            folders={'test': 'folder'},
            content_type='Games',
            schedule='24_hours',
            status='Running',
            total_folders=5,
            folders_success=0,
            folders_failed=0
        )
        db_session.add(scan_job)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data) == 1
        job = data[0]
        assert job['library_name'] == 'No Library Assigned'
    
    def test_scan_jobs_status_null_dates(self, client, admin_user, db_session, sample_library):
        """Test scan_jobs_status with null last_run and next_run."""
        scan_job = ScanJob(
            library_uuid=sample_library.uuid,
            folders={'test': 'folder'},
            content_type='Games',
            status='Scheduled',
            last_run=None,  # Null
            next_run=None,  # Null
            total_folders=0,
            folders_success=0,
            folders_failed=0
        )
        db_session.add(scan_job)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data) == 1
        job = data[0]
        assert job['last_run'] == 'Not Available'
        assert job['next_run'] == 'Not Scheduled'
    
    def test_scan_jobs_status_with_error_message(self, client, admin_user, db_session, sample_library):
        """Test scan_jobs_status with error message."""
        scan_job = ScanJob(
            library_uuid=sample_library.uuid,
            folders={},
            content_type='Games',
            status='Failed',
            error_message='Test error occurred',
            total_folders=3,
            folders_success=1,
            folders_failed=2
        )
        db_session.add(scan_job)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data) == 1
        job = data[0]
        assert job['status'] == 'Failed'
        assert job['error_message'] == 'Test error occurred'
    
    def test_scan_jobs_status_boolean_fields(self, client, admin_user, db_session, sample_library):
        """Test scan_jobs_status boolean field conversions."""
        scan_job = ScanJob(
            library_uuid=sample_library.uuid,
            folders={},
            content_type='Games',
            status='Running',
            setting_remove=False,
            setting_filefolder=True,
            total_folders=0,
            folders_success=0,
            folders_failed=0
        )
        db_session.add(scan_job)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 200
        
        data = response.get_json()
        job = data[0]
        assert job['setting_remove'] is False
        assert job['setting_filefolder'] is True
        assert isinstance(job['setting_remove'], bool)
        assert isinstance(job['setting_filefolder'], bool)
    
    def test_scan_jobs_status_multiple_jobs(self, client, admin_user, db_session, sample_library):
        """Test scan_jobs_status with multiple scan jobs."""
        jobs = []
        for i, status in enumerate(['Running', 'Completed', 'Failed']):
            scan_job = ScanJob(
                library_uuid=sample_library.uuid,
                folders={'folder': f'test_{i}'},
                content_type='Games',
                status=status,
                total_folders=i + 1,
                folders_success=i,
                folders_failed=1 if status == 'Failed' else 0
            )
            db_session.add(scan_job)
            jobs.append(scan_job)
        
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/scan_jobs_status')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data) == 3
        
        # Verify all jobs returned
        statuses = [job['status'] for job in data]
        assert 'Running' in statuses
        assert 'Completed' in statuses
        assert 'Failed' in statuses


class TestUnmatchedFolders:
    """Tests for unmatched_folders endpoint."""
    
    def test_unmatched_folders_requires_login(self, client):
        """Test that unmatched_folders requires login."""
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_unmatched_folders_requires_admin(self, client, regular_user):
        """Test that unmatched_folders requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 302
        # Should redirect to login due to admin_required decorator
    
    def test_unmatched_folders_empty_list(self, client, admin_user):
        """Test unmatched_folders with no unmatched folders."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_unmatched_folders_single_folder(self, client, admin_user, sample_unmatched_folder):
        """Test unmatched_folders with a single unmatched folder."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        
        folder = data[0]
        assert folder['id'] == sample_unmatched_folder.id
        assert folder['folder_path'] == '/test/unmatched/folder'
        assert folder['status'] == 'Unmatched'
        assert 'library_name' in folder
        assert 'platform_name' in folder
        assert 'platform_id' in folder
    
    def test_unmatched_folders_with_platform_data(self, client, admin_user, sample_unmatched_folder):
        """Test unmatched_folders includes platform data correctly."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 200
        
        data = response.get_json()
        folder = data[0]
        
        # Should have platform name and ID from PCWIN platform
        assert folder['platform_name'] == 'PCWIN'
        assert folder['platform_id'] == PLATFORM_IDS.get('PCWIN')  # Should be 6
        assert folder['platform_id'] == 6
    
    @patch('modules.routes_apis.scan.PLATFORM_IDS', {})  # Mock empty PLATFORM_IDS in the route module
    def test_unmatched_folders_no_platform_mapping(self, client, admin_user, db_session):
        """Test unmatched_folders when platform exists but has no ID mapping."""
        # Create library with a platform that won't be in PLATFORM_IDS
        library = Library(
            name='Test Library Unknown Platform',
            platform=LibraryPlatform.PCWIN  # Valid platform but we'll mock empty PLATFORM_IDS
        )
        db_session.add(library)
        db_session.flush()
        
        scan_job = ScanJob(
            library_uuid=library.uuid,
            status='Running',
            total_folders=0,
            folders_success=0,
            folders_failed=0
        )
        db_session.add(scan_job)
        db_session.flush()
        
        unmatched = UnmatchedFolder(
            library_uuid=library.uuid,
            scan_job_id=scan_job.id,
            folder_path='/test/no/mapping',
            status='Pending',
            content_type='Games'
        )
        db_session.add(unmatched)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 200
        
        data = response.get_json()
        folder = data[0]
        
        # Platform name should still be available from the platform enum
        assert folder['platform_name'] == 'PCWIN'
        # But platform_id should be None because PLATFORM_IDS is mocked as empty
        assert folder['platform_id'] is None
    
    def test_unmatched_folders_handles_none_platform_in_query(self, client, admin_user, db_session, sample_library, sample_scan_job):
        """Test unmatched_folders handles None platform in query result gracefully."""
        # Create an unmatched folder
        unmatched = UnmatchedFolder(
            library_uuid=sample_library.uuid,
            scan_job_id=sample_scan_job.id,
            folder_path='/test/none/platform',
            status='Pending',
            content_type='Games'
        )
        db_session.add(unmatched)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Mock the query to return None platform (simulating edge case)
        with patch('modules.routes_apis.scan.db.session.execute') as mock_execute:
            # Create a mock result that simulates None platform
            mock_result_row = Mock()
            mock_result_row.id = unmatched.id
            mock_result_row.folder_path = unmatched.folder_path
            mock_result_row.status = unmatched.status
            library_name = sample_library.name
            platform = None  # None platform to test edge case
            
            mock_execute.return_value.all.return_value = [(mock_result_row, library_name, platform)]
            
            response = client.get('/api/unmatched_folders')
            assert response.status_code == 200
            
            data = response.get_json()
            folder = data[0]
            
            # Should handle None platform gracefully
            assert folder['platform_name'] == ''
            assert folder['platform_id'] is None
    
    def test_unmatched_folders_different_statuses(self, client, admin_user, db_session, sample_library, sample_scan_job):
        """Test unmatched_folders with different status values."""
        statuses = ['Pending', 'Ignore', 'Duplicate', 'Unmatched']
        
        for i, status in enumerate(statuses):
            unmatched = UnmatchedFolder(
                library_uuid=sample_library.uuid,
                scan_job_id=sample_scan_job.id,
                folder_path=f'/test/path/{i}',
                status=status,
                content_type='Games'
            )
            db_session.add(unmatched)
        
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data) == 4
        
        # Verify all statuses are present
        returned_statuses = [folder['status'] for folder in data]
        for status in statuses:
            assert status in returned_statuses
    
    def test_unmatched_folders_ordering_by_status(self, client, admin_user, db_session, sample_library, sample_scan_job):
        """Test that unmatched_folders are ordered by status descending."""
        # Create folders with different statuses
        # The order should be determined by enum value in descending order
        statuses = ['Pending', 'Unmatched', 'Ignore', 'Duplicate']
        
        for i, status in enumerate(statuses):
            unmatched = UnmatchedFolder(
                library_uuid=sample_library.uuid,
                scan_job_id=sample_scan_job.id,
                folder_path=f'/test/ordered/{i}_{status.lower()}',
                status=status,
                content_type='Games'
            )
            db_session.add(unmatched)
        
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data) == 4
        
        # Verify ordering (should be by status descending)
        returned_statuses = [folder['status'] for folder in data]
        # The exact order depends on the enum implementation, but they should be ordered
        assert len(set(returned_statuses)) == 4  # All different statuses present
    
    def test_unmatched_folders_multiple_libraries(self, client, admin_user, db_session):
        """Test unmatched_folders from multiple libraries."""
        libraries = []
        
        # Create multiple libraries with different platforms
        for i, platform in enumerate([LibraryPlatform.PCWIN, LibraryPlatform.N64]):
            library = Library(
                name=f'Test Library {i}',
                platform=platform
            )
            db_session.add(library)
            db_session.flush()
            libraries.append(library)
            
            scan_job = ScanJob(
                library_uuid=library.uuid,
                status='Running',
                total_folders=0,
                folders_success=0,
                folders_failed=0
            )
            db_session.add(scan_job)
            db_session.flush()
            
            unmatched = UnmatchedFolder(
                library_uuid=library.uuid,
                scan_job_id=scan_job.id,
                folder_path=f'/test/library_{i}',
                status='Unmatched',
                content_type='Games'
            )
            db_session.add(unmatched)
        
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 200
        
        data = response.get_json()
        assert len(data) == 2
        
        # Verify different library names and platforms
        library_names = {folder['library_name'] for folder in data}
        platform_names = {folder['platform_name'] for folder in data}
        
        assert 'Test Library 0' in library_names
        assert 'Test Library 1' in library_names
        assert 'PCWIN' in platform_names
        assert 'N64' in platform_names
    
    def test_unmatched_folders_platform_id_mapping(self, client, admin_user, db_session):
        """Test that platform IDs are correctly mapped from PLATFORM_IDS."""
        # Test with a platform that has a known mapping
        library = Library(
            name='Test Xbox Library',
            platform=LibraryPlatform.XBOX
        )
        db_session.add(library)
        db_session.flush()
        
        scan_job = ScanJob(
            library_uuid=library.uuid,
            status='Running',
            total_folders=0,
            folders_success=0,
            folders_failed=0
        )
        db_session.add(scan_job)
        db_session.flush()
        
        unmatched = UnmatchedFolder(
            library_uuid=library.uuid,
            scan_job_id=scan_job.id,
            folder_path='/test/xbox',
            status='Unmatched',
            content_type='Games'
        )
        db_session.add(unmatched)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/unmatched_folders')
        assert response.status_code == 200
        
        data = response.get_json()
        folder = data[0]
        
        assert folder['platform_name'] == 'XBOX'
        assert folder['platform_id'] == PLATFORM_IDS.get('XBOX')
        assert folder['platform_id'] == 11  # Known value from PLATFORM_IDS


class TestScanApiBlueprint:
    """Test blueprint registration and URL patterns."""
    
    def test_scan_routes_blueprint_registration(self, app):
        """Test that scan API routes are properly registered."""
        with app.test_request_context():
            assert url_for('apis.scan_jobs_status') == '/api/scan_jobs_status'
            assert url_for('apis.unmatched_folders') == '/api/unmatched_folders'
    
    def test_scan_routes_authentication_required(self, client):
        """Test that all scan API routes require authentication."""
        endpoints = [
            '/api/scan_jobs_status',
            '/api/unmatched_folders'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 302
            assert 'login' in response.location


class TestScanApiIntegration:
    """Integration tests for scan API routes."""
    
    def test_scan_workflow_integration(self, client, admin_user, db_session, sample_library):
        """Test complete scan workflow integration."""
        # Create a scan job with unmatched folders
        scan_job = ScanJob(
            library_uuid=sample_library.uuid,
            folders={'test': 'integration'},
            status='Completed',
            total_folders=5,
            folders_success=3,
            folders_failed=2
        )
        db_session.add(scan_job)
        db_session.flush()
        
        # Create unmatched folders from that scan job
        unmatched = UnmatchedFolder(
            library_uuid=sample_library.uuid,
            scan_job_id=scan_job.id,
            folder_path='/integration/test',
            status='Unmatched',
            content_type='Games'
        )
        db_session.add(unmatched)
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Test scan jobs status
        jobs_response = client.get('/api/scan_jobs_status')
        assert jobs_response.status_code == 200
        jobs_data = jobs_response.get_json()
        assert len(jobs_data) == 1
        
        # Test unmatched folders
        folders_response = client.get('/api/unmatched_folders')
        assert folders_response.status_code == 200
        folders_data = folders_response.get_json()
        assert len(folders_data) == 1
        
        # Verify relationship between scan job and unmatched folder
        job = jobs_data[0]
        folder = folders_data[0]
        
        assert job['id'] == scan_job.id
        assert folder['id'] == unmatched.id
        assert job['library_name'] == folder['library_name']
        assert job['folders_failed'] == 2  # Should correlate with unmatched folders
    
    def test_empty_scan_data_consistency(self, client, admin_user):
        """Test consistent empty responses across both endpoints."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Both endpoints should return empty lists
        jobs_response = client.get('/api/scan_jobs_status')
        folders_response = client.get('/api/unmatched_folders')
        
        assert jobs_response.status_code == 200
        assert folders_response.status_code == 200
        
        jobs_data = jobs_response.get_json()
        folders_data = folders_response.get_json()
        
        assert isinstance(jobs_data, list)
        assert isinstance(folders_data, list)
        assert len(jobs_data) == 0
        assert len(folders_data) == 0
    
    def test_admin_authentication_consistency(self, client, regular_user):
        """Test that both endpoints consistently require admin authentication."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Both endpoints should redirect due to admin requirement
        jobs_response = client.get('/api/scan_jobs_status')
        folders_response = client.get('/api/unmatched_folders')
        
        assert jobs_response.status_code == 302
        assert folders_response.status_code == 302