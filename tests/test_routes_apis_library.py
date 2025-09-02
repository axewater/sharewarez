import pytest
import json
from unittest.mock import patch, Mock
from uuid import uuid4
from flask import url_for

from modules import db
from modules.models import User, Library
from modules.platform import LibraryPlatform


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
    """Create a sample library for testing."""
    unique_id = str(uuid4())[:8]
    library = Library(
        name=f'Test Library_{unique_id}',
        platform=LibraryPlatform.PCWIN,
        image_url='/static/test_library.jpg',
        display_order=1
    )
    db_session.add(library)
    db_session.commit()
    return library


@pytest.fixture
def multiple_libraries(db_session):
    """Create multiple libraries for testing."""
    libraries = []
    for i in range(3):
        unique_id = str(uuid4())[:8]
        library = Library(
            name=f'Library_{i}_{unique_id}',
            platform=LibraryPlatform.PCWIN,
            image_url=f'/static/library_{i}.jpg' if i > 0 else None,
            display_order=i
        )
        db_session.add(library)
        libraries.append(library)
    
    db_session.commit()
    return libraries


class TestGetLibraries:
    """Tests for get_libraries endpoint."""
    
    def test_get_libraries_requires_auth(self, client):
        """Test that get_libraries requires authentication."""
        response = client.get('/api/get_libraries')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_get_libraries_empty_database(self, client, regular_user, db_session):
        """Test get_libraries with no libraries in database."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_libraries')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_get_libraries_single_library(self, client, regular_user, sample_library):
        """Test get_libraries with a single library."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_libraries')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 1
        
        library_data = data[0]
        assert library_data['uuid'] == sample_library.uuid
        assert library_data['name'] == sample_library.name
        assert library_data['image_url'] == '/static/test_library.jpg'
    
    def test_get_libraries_multiple_libraries(self, client, regular_user, multiple_libraries):
        """Test get_libraries with multiple libraries."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_libraries')
        assert response.status_code == 200
        
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 3
        
        # Verify all libraries are returned
        returned_uuids = {lib['uuid'] for lib in data}
        expected_uuids = {lib.uuid for lib in multiple_libraries}
        assert returned_uuids == expected_uuids
        
        # Verify structure of each library
        for library_data in data:
            assert 'uuid' in library_data
            assert 'name' in library_data
            assert 'image_url' in library_data
    
    def test_get_libraries_default_image_url(self, client, regular_user, multiple_libraries):
        """Test get_libraries returns default image for library without image_url."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_libraries')
        assert response.status_code == 200
        
        data = response.get_json()
        
        # Find the library without custom image (first one in our fixture)
        library_without_image = next(lib for lib in data if 'Library_0_' in lib['name'])
        assert library_without_image['image_url'] == '/static/newstyle/default_library.jpg'
    
    def test_get_libraries_json_response_format(self, client, regular_user, sample_library):
        """Test that get_libraries returns proper JSON format."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/get_libraries')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        # Verify JSON structure
        data = response.get_json()
        library = data[0]
        required_fields = ['uuid', 'name', 'image_url']
        for field in required_fields:
            assert field in library


class TestReorderLibraries:
    """Tests for reorder_libraries endpoint."""
    
    def test_reorder_libraries_requires_login(self, client):
        """Test that reorder_libraries requires login."""
        response = client.post('/api/reorder_libraries', 
                             json={'order': []})
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_reorder_libraries_requires_admin(self, client, regular_user):
        """Test that reorder_libraries requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/reorder_libraries',
                             json={'order': []})
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_reorder_libraries_successful_reorder(self, client, admin_user, multiple_libraries):
        """Test successful library reordering."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Create new order (reverse the current order)
        original_order = [lib.uuid for lib in sorted(multiple_libraries, key=lambda x: x.display_order)]
        new_order = list(reversed(original_order))
        
        response = client.post('/api/reorder_libraries',
                             json={'order': new_order})
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['status'] == 'success'
        
        # Verify the order was actually changed in the database
        for index, library_uuid in enumerate(new_order):
            library = db.session.get(Library, library_uuid)
            assert library.display_order == index
    
    def test_reorder_libraries_partial_order(self, client, admin_user, multiple_libraries):
        """Test reordering with only some libraries in the order."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Only include first two libraries in new order
        partial_order = [multiple_libraries[1].uuid, multiple_libraries[0].uuid]
        
        response = client.post('/api/reorder_libraries',
                             json={'order': partial_order})
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['status'] == 'success'
        
        # Verify the specified libraries got their new order
        lib1 = db.session.get(Library, partial_order[0])
        lib2 = db.session.get(Library, partial_order[1])
        assert lib1.display_order == 0
        assert lib2.display_order == 1
    
    def test_reorder_libraries_nonexistent_library(self, client, admin_user, multiple_libraries):
        """Test reordering with non-existent library UUID."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Include a non-existent UUID in the order
        fake_uuid = str(uuid4())
        order_with_fake = [multiple_libraries[0].uuid, fake_uuid, multiple_libraries[1].uuid]
        
        response = client.post('/api/reorder_libraries',
                             json={'order': order_with_fake})
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['status'] == 'success'
        
        # Verify existing libraries still got reordered correctly
        lib1 = db.session.get(Library, multiple_libraries[0].uuid)
        lib2 = db.session.get(Library, multiple_libraries[1].uuid)
        assert lib1.display_order == 0
        assert lib2.display_order == 2  # Should be index 2 because fake UUID was at index 1
    
    def test_reorder_libraries_empty_order(self, client, admin_user):
        """Test reordering with empty order list."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/reorder_libraries',
                             json={'order': []})
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['status'] == 'success'
    
    def test_reorder_libraries_missing_order_key(self, client, admin_user):
        """Test reordering without 'order' key in JSON."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/reorder_libraries',
                             json={'wrong_key': []})
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['status'] == 'success'  # Should default to empty list
    
    def test_reorder_libraries_invalid_json(self, client, admin_user):
        """Test reordering with invalid JSON."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/api/reorder_libraries',
                             data='invalid json',
                             content_type='application/json')
        assert response.status_code == 500  # Flask returns 500 for invalid JSON
    
    @patch('modules.routes_apis.library.db.session.commit')
    def test_reorder_libraries_database_error(self, mock_commit, client, admin_user, multiple_libraries):
        """Test reordering with database error."""
        mock_commit.side_effect = Exception("Database error")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        order = [lib.uuid for lib in multiple_libraries]
        
        response = client.post('/api/reorder_libraries',
                             json={'order': order})
        assert response.status_code == 500
        
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'Database error' in data['message']


class TestGetLibrary:
    """Tests for get_library endpoint."""
    
    def test_get_library_requires_login(self, client, sample_library):
        """Test that get_library requires login."""
        response = client.get(f'/api/library/{sample_library.uuid}')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_get_library_successful(self, client, regular_user, sample_library):
        """Test successful library retrieval."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/library/{sample_library.uuid}')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['uuid'] == sample_library.uuid
        assert data['name'] == sample_library.name
        assert data['platform'] == sample_library.platform.name
    
    def test_get_library_admin_access(self, client, admin_user, sample_library):
        """Test that admin can access library details."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/library/{sample_library.uuid}')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['uuid'] == sample_library.uuid
        assert data['name'] == sample_library.name
    
    def test_get_library_not_found(self, client, regular_user):
        """Test library not found scenario."""
        fake_uuid = str(uuid4())
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/library/{fake_uuid}')
        assert response.status_code == 404
        
        data = response.get_json()
        assert data['error'] == 'Library not found'
    
    def test_get_library_invalid_uuid_format(self, client, regular_user):
        """Test library retrieval with invalid UUID format."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/library/invalid-uuid')
        assert response.status_code == 404
        
        data = response.get_json()
        assert data['error'] == 'Library not found'
    
    def test_get_library_json_response_format(self, client, regular_user, sample_library):
        """Test that get_library returns proper JSON format."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/api/library/{sample_library.uuid}')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        # Verify JSON structure
        data = response.get_json()
        required_fields = ['uuid', 'name', 'platform']
        for field in required_fields:
            assert field in data
    
    def test_get_library_different_platforms(self, client, regular_user, db_session):
        """Test library retrieval for different platform types."""
        # Create libraries with different platforms
        platforms_to_test = [LibraryPlatform.PCWIN, LibraryPlatform.MAC, LibraryPlatform.LYNX]
        
        libraries_created = []
        for platform in platforms_to_test:
            unique_id = str(uuid4())[:8]
            library = Library(
                name=f'Library_{platform.name}_{unique_id}',
                platform=platform,
                display_order=0
            )
            db_session.add(library)
            libraries_created.append(library)
        
        db_session.commit()
        
        # Test each library with fresh authentication for each request
        for library in libraries_created:
            with client.session_transaction() as sess:
                sess['_user_id'] = str(regular_user.id)
                sess['_fresh'] = True
            
            response = client.get(f'/api/library/{library.uuid}')
            assert response.status_code == 200
            
            data = response.get_json()
            assert data['platform'] == library.platform.name


class TestLibraryApiBlueprint:
    """Test blueprint registration and URL patterns."""
    
    def test_library_routes_blueprint_registration(self, app):
        """Test that library API routes are properly registered."""
        with app.test_request_context():
            assert url_for('apis.get_libraries') == '/api/get_libraries'
            assert url_for('apis.reorder_libraries') == '/api/reorder_libraries'
            # Note: get_library requires a parameter, so we test with a sample UUID
            sample_uuid = str(uuid4())
            assert url_for('apis.get_library', library_uuid=sample_uuid) == f'/api/library/{sample_uuid}'
    
    def test_library_routes_http_methods(self, client, regular_user):
        """Test correct HTTP methods are supported."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # GET should work for get_libraries (with auth)
        response = client.get('/api/get_libraries')
        assert response.status_code == 200
        
        # POST should not work for get_libraries
        response = client.post('/api/get_libraries')
        assert response.status_code == 405  # Method Not Allowed
        
        # GET should not work for reorder_libraries
        response = client.get('/api/reorder_libraries')
        assert response.status_code == 405  # Method Not Allowed


class TestLibraryApiIntegration:
    """Integration tests for library API routes."""
    
    def test_library_workflow_get_and_reorder(self, client, admin_user, multiple_libraries):
        """Test complete workflow: get libraries then reorder them."""
        # Login as admin to get libraries
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # First, get all libraries
        response = client.get('/api/get_libraries')
        assert response.status_code == 200
        
        original_libraries = response.get_json()
        assert len(original_libraries) == 3
        
        # Reorder libraries (already logged in as admin)
        new_order = [lib['uuid'] for lib in reversed(original_libraries)]
        
        response = client.post('/api/reorder_libraries',
                             json={'order': new_order})
        assert response.status_code == 200
        
        # Get libraries again to verify order (still logged in)
        response = client.get('/api/get_libraries')
        assert response.status_code == 200
        
        updated_libraries = response.get_json()
        # Note: The API doesn't guarantee order in get_libraries response
        # but we can verify the display_order was updated in the database
        for index, uuid in enumerate(new_order):
            library = db.session.get(Library, uuid)
            assert library.display_order == index
    
    def test_library_data_consistency(self, client, regular_user, multiple_libraries):
        """Test that library data remains consistent across requests."""
        library = multiple_libraries[0]
        
        # Make multiple requests for the same library
        responses = []
        for i in range(3):
            with client.session_transaction() as sess:
                sess['_user_id'] = str(regular_user.id)
                sess['_fresh'] = True
            
            response = client.get(f'/api/library/{library.uuid}')
            assert response.status_code == 200
            responses.append(response.get_json())
        
        # All responses should be identical
        first_response = responses[0]
        for response_data in responses[1:]:
            assert response_data['uuid'] == first_response['uuid']
            assert response_data['name'] == first_response['name']
            assert response_data['platform'] == first_response['platform']
    
    def test_library_operations_isolation(self, client, regular_user, multiple_libraries):
        """Test that library operations work in isolation."""
        # Test that each operation works independently
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Get all libraries
        response1 = client.get('/api/get_libraries')
        assert response1.status_code == 200
        libraries_data = response1.get_json()
        assert len(libraries_data) >= 3
        
        # Get individual library details
        library = multiple_libraries[0]
        response2 = client.get(f'/api/library/{library.uuid}')
        assert response2.status_code == 200
        library_detail = response2.get_json()
        
        # Verify consistency between list and detail views
        matching_library = next(lib for lib in libraries_data if lib['uuid'] == library.uuid)
        assert matching_library['name'] == library_detail['name']
    
    def test_error_handling_consistency(self, client, regular_user):
        """Test that error responses follow consistent format."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        # Test various error scenarios
        responses = [
            client.get('/api/library/nonexistent-uuid'),  # Library not found
            client.get('/api/library/invalid-format'),    # Invalid UUID format
        ]
        
        for response in responses:
            assert response.status_code == 404
            data = response.get_json()
            assert 'error' in data
            assert data['error'] == 'Library not found'