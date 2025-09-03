"""
Unit tests for modules.routes_apis.browse

Tests the browse_folders_ss API endpoint including authentication, authorization,
directory browsing, security, and error handling.
"""

import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from uuid import uuid4

from modules.models import User


@pytest.fixture
def regular_user(db_session):
    """Create a test regular user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'regularuser_{user_uuid[:8]}',
        email=f'regular_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='user',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=5
    )
    user.set_password('regularpassword123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin_user(db_session):
    """Create a test admin user."""
    user_uuid = str(uuid4())
    user = User(
        name=f'adminuser_{user_uuid[:8]}',
        email=f'admin_{user_uuid[:8]}@example.com',
        password_hash='hashed_password',
        role='admin',
        user_id=user_uuid,
        avatarpath='newstyle/avatar_default.jpg',
        invite_quota=10
    )
    user.set_password('adminpassword123')
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def mock_filesystem():
    """Create a mock filesystem structure for testing."""
    return {
        'base_dir': '/test/base',
        'directories': ['subdir1', 'subdir2'],
        'files': [
            {'name': 'file1.txt', 'size': 100},
            {'name': 'file2.pdf', 'size': 200},
            {'name': 'file3', 'size': 50}  # No extension
        ]
    }


class TestBrowseFoldersSS:
    """Test the browse_folders_ss API endpoint."""
    
    def test_browse_requires_login(self, client):
        """Test that browse_folders_ss requires user login."""
        response = client.get('/api/browse_folders_ss')
        assert response.status_code == 302  # Redirect to login
    
    def test_browse_requires_admin(self, client, regular_user):
        """Test that browse_folders_ss requires admin privileges."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss')
        assert response.status_code == 302  # Redirect due to admin_required decorator
    
    @patch('modules.routes_apis.browse.os')
    @patch('modules.routes_apis.browse.current_app', new_callable=MagicMock)
    def test_browse_base_directory_posix(self, mock_current_app, mock_os, client, admin_user, mock_filesystem):
        """Test browsing the base directory on POSIX systems."""
        # Setup mocks
        mock_os.name = 'posix'
        mock_current_app.config.get.side_effect = lambda key: {
            'BASE_FOLDER_POSIX': mock_filesystem['base_dir'],
            'BASE_FOLDER_WINDOWS': None
        }.get(key)
        
        # Mock filesystem operations
        mock_os.path.abspath.return_value = mock_filesystem['base_dir']
        mock_os.path.join.side_effect = lambda *args: '/'.join(args)
        mock_os.listdir.return_value = mock_filesystem['directories'] + [f['name'] for f in mock_filesystem['files']]
        
        def mock_isdir_side_effect(path):
            # First check if this is the base directory itself
            if path == mock_filesystem['base_dir']:
                return True
            filename = os.path.basename(path)
            return filename in mock_filesystem['directories']
        
        def mock_getsize_side_effect(path):
            filename = os.path.basename(path)
            for file_info in mock_filesystem['files']:
                if file_info['name'] == filename:
                    return file_info['size']
            return 0
        
        mock_os.path.isdir.side_effect = mock_isdir_side_effect
        mock_os.path.getsize.side_effect = mock_getsize_side_effect
        mock_os.path.splitext.side_effect = lambda name: (name.rsplit('.', 1)[0], '.' + name.rsplit('.', 1)[1]) if '.' in name else (name, '')
        
        # Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, list)
        
        # Verify directories come first (isDir: True)
        directories = [item for item in data if item['isDir']]
        files = [item for item in data if not item['isDir']]
        
        assert len(directories) == 2
        assert len(files) == 3
        
        # Verify directory structure
        for directory in directories:
            assert directory['name'] in mock_filesystem['directories']
            assert directory['isDir'] is True
            assert directory['ext'] is None
            assert directory['size'] is None
    
    @patch('modules.routes_apis.browse.os')
    @patch('modules.routes_apis.browse.current_app', new_callable=MagicMock)
    def test_browse_base_directory_windows(self, mock_current_app, mock_os, client, admin_user, mock_filesystem):
        """Test browsing the base directory on Windows systems."""
        # Setup mocks
        mock_os.name = 'nt'
        mock_current_app.config.get.side_effect = lambda key: {
            'BASE_FOLDER_WINDOWS': 'C:\\test\\base',
            'BASE_FOLDER_POSIX': None
        }.get(key)
        
        # Mock filesystem operations
        mock_os.path.abspath.return_value = 'C:\\test\\base'
        mock_os.path.join.side_effect = lambda *args: '\\'.join(args)
        mock_os.listdir.return_value = ['testdir', 'testfile.txt']
        
        def mock_isdir_side_effect(path):
            if path == 'C:\\test\\base':
                return True
            return 'testdir' in path
        
        mock_os.path.isdir.side_effect = mock_isdir_side_effect
        mock_os.path.getsize.side_effect = lambda path: 150 if 'testfile.txt' in path else 0
        mock_os.path.splitext.side_effect = lambda name: (name.rsplit('.', 1)[0], '.' + name.rsplit('.', 1)[1]) if '.' in name else (name, '')
        
        # Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
    
    @patch('modules.routes_apis.browse.os')
    @patch('modules.routes_apis.browse.current_app', new_callable=MagicMock)
    def test_browse_subdirectory(self, mock_current_app, mock_os, client, admin_user):
        """Test browsing a subdirectory with proper path handling."""
        # Setup mocks
        mock_os.name = 'posix'
        base_dir = '/test/base'
        request_path = 'subdir1'
        expected_full_path = '/test/base/subdir1'
        
        mock_current_app.config.get.side_effect = lambda key: {
            'BASE_FOLDER_POSIX': base_dir,
            'BASE_FOLDER_WINDOWS': None
        }.get(key)
        
        mock_os.path.abspath.return_value = expected_full_path
        mock_os.path.join.side_effect = lambda *args: '/'.join(args)
        mock_os.path.isdir.return_value = True
        mock_os.listdir.return_value = ['nested_file.txt']
        
        # Mock that the path starts with base directory (security check)
        mock_os.path.abspath.return_value = expected_full_path
        
        mock_os.path.isdir.side_effect = lambda path: 'nested_file.txt' not in str(path)
        mock_os.path.getsize.side_effect = lambda path: 250 if 'nested_file.txt' in str(path) else 0
        mock_os.path.splitext.side_effect = lambda name: ('nested_file', '.txt') if name == 'nested_file.txt' else (name, '')
        
        # Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss', query_string={'path': request_path})
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 1
        
        file_item = data[0]
        assert file_item['name'] == 'nested_file.txt'
        assert file_item['isDir'] is False
        assert file_item['ext'] == 'txt'
        assert file_item['size'] == 250
    
    @patch('modules.routes_apis.browse.os')
    @patch('modules.routes_apis.browse.current_app', new_callable=MagicMock)
    def test_directory_traversal_prevention(self, mock_current_app, mock_os, client, admin_user):
        """Test that directory traversal attacks are prevented."""
        # Setup mocks
        mock_os.name = 'posix'
        base_dir = '/test/base'
        malicious_path = '../../../etc'
        
        mock_current_app.config.get.side_effect = lambda key: {
            'BASE_FOLDER_POSIX': base_dir,
            'BASE_FOLDER_WINDOWS': None
        }.get(key)
        
        # Mock that abspath resolves to a path outside base directory
        malicious_full_path = '/etc'
        mock_os.path.abspath.return_value = malicious_full_path
        mock_os.path.join.side_effect = lambda *args: '/'.join(args)
        
        # Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss', query_string={'path': malicious_path})
        assert response.status_code == 403
        
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'Access denied'
    
    @patch('modules.routes_apis.browse.os')
    @patch('modules.routes_apis.browse.current_app', new_callable=MagicMock)
    def test_nonexistent_directory(self, mock_current_app, mock_os, client, admin_user):
        """Test handling of nonexistent directories."""
        # Setup mocks
        mock_os.name = 'posix'
        base_dir = '/test/base'
        
        mock_current_app.config.get.side_effect = lambda key: {
            'BASE_FOLDER_POSIX': base_dir,
            'BASE_FOLDER_WINDOWS': None
        }.get(key)
        
        mock_os.path.abspath.return_value = '/test/base/nonexistent'
        mock_os.path.join.side_effect = lambda *args: '/'.join(args)
        mock_os.path.isdir.return_value = False  # Directory doesn't exist
        
        # Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss', query_string={'path': 'nonexistent'})
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert 'error' in data
        assert 'SS folder browser: Folder not found' in data['error']
    
    @patch('modules.routes_apis.browse.os')
    @patch('modules.routes_apis.browse.current_app', new_callable=MagicMock)
    def test_file_metadata_accuracy(self, mock_current_app, mock_os, client, admin_user):
        """Test that file metadata is accurate including extensions and sizes."""
        # Setup mocks
        mock_os.name = 'posix'
        base_dir = '/test/base'
        
        mock_current_app.config.get.side_effect = lambda key: {
            'BASE_FOLDER_POSIX': base_dir,
            'BASE_FOLDER_WINDOWS': None
        }.get(key)
        
        mock_os.path.abspath.return_value = base_dir
        mock_os.path.join.side_effect = lambda *args: '/'.join(args)
        
        # Mock files with different extensions and sizes
        test_files = [
            'document.pdf',
            'image.JPG',
            'archive.tar.gz',
            'noextension'
        ]
        mock_os.listdir.return_value = test_files
        
        def mock_isdir_side_effect(path):
            if path == base_dir:
                return True
            return False  # All other items are files
        
        def mock_getsize_side_effect(path):
            filename = os.path.basename(path)
            sizes = {
                'document.pdf': 1024,
                'image.JPG': 2048,
                'archive.tar.gz': 4096,
                'noextension': 512
            }
            return sizes.get(filename, 0)
        
        def mock_splitext_side_effect(name):
            if '.' in name:
                parts = name.rsplit('.', 1)
                return (parts[0], '.' + parts[1])
            return (name, '')
        
        mock_os.path.isdir.side_effect = mock_isdir_side_effect
        mock_os.path.getsize.side_effect = mock_getsize_side_effect
        mock_os.path.splitext.side_effect = mock_splitext_side_effect
        
        # Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == 4
        
        # Verify metadata for each file
        for item in data:
            assert item['isDir'] is False
            if item['name'] == 'document.pdf':
                assert item['ext'] == 'pdf'
                assert item['size'] == 1024
            elif item['name'] == 'image.JPG':
                assert item['ext'] == 'jpg'  # Should be lowercase
                assert item['size'] == 2048
            elif item['name'] == 'archive.tar.gz':
                assert item['ext'] == 'gz'  # Should get last extension
                assert item['size'] == 4096
            elif item['name'] == 'noextension':
                assert item['ext'] == ''  # No extension
                assert item['size'] == 512
    
    @patch('modules.routes_apis.browse.os')
    @patch('modules.routes_apis.browse.current_app', new_callable=MagicMock)
    def test_response_sorting(self, mock_current_app, mock_os, client, admin_user):
        """Test that response is properly sorted (directories first, then files alphabetically)."""
        # Setup mocks
        mock_os.name = 'posix'
        base_dir = '/test/base'
        
        mock_current_app.config.get.side_effect = lambda key: {
            'BASE_FOLDER_POSIX': base_dir,
            'BASE_FOLDER_WINDOWS': None
        }.get(key)
        
        mock_os.path.abspath.return_value = base_dir
        mock_os.path.join.side_effect = lambda *args: '/'.join(args)
        
        # Mix of directories and files in non-alphabetical order
        items = ['zebra_file.txt', 'alpha_dir', 'beta_file.txt', 'gamma_dir']
        mock_os.listdir.return_value = items
        
        def mock_isdir_side_effect(path):
            if path == base_dir:
                return True
            filename = os.path.basename(path)
            return filename in ['alpha_dir', 'gamma_dir']
        
        def mock_getsize_side_effect(path):
            filename = os.path.basename(path)
            return 100 if not filename.endswith('_dir') else 0
        
        mock_os.path.isdir.side_effect = mock_isdir_side_effect
        mock_os.path.getsize.side_effect = mock_getsize_side_effect
        mock_os.path.splitext.side_effect = lambda name: (name.rsplit('.', 1)[0], '.' + name.rsplit('.', 1)[1]) if '.' in name else (name, '')
        
        # Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert len(data) == 4
        
        # Verify directories come first
        directories = [item for item in data if item['isDir']]
        files = [item for item in data if not item['isDir']]
        
        assert len(directories) == 2
        assert len(files) == 2
        
        # Verify directories are alphabetically sorted
        dir_names = [d['name'] for d in directories]
        assert dir_names == ['alpha_dir', 'gamma_dir']
        
        # Verify files are alphabetically sorted
        file_names = [f['name'] for f in files]
        assert file_names == ['beta_file.txt', 'zebra_file.txt']
        
        # Verify overall order (directories first, then files)
        all_names = [item['name'] for item in data]
        assert all_names == ['alpha_dir', 'gamma_dir', 'beta_file.txt', 'zebra_file.txt']
    
    @patch('modules.routes_apis.browse.os')
    @patch('modules.routes_apis.browse.current_app', new_callable=MagicMock)
    def test_empty_directory(self, mock_current_app, mock_os, client, admin_user):
        """Test browsing an empty directory."""
        # Setup mocks
        mock_os.name = 'posix'
        base_dir = '/test/base'
        
        mock_current_app.config.get.side_effect = lambda key: {
            'BASE_FOLDER_POSIX': base_dir,
            'BASE_FOLDER_WINDOWS': None
        }.get(key)
        
        mock_os.path.abspath.return_value = base_dir
        mock_os.path.join.side_effect = lambda *args: '/'.join(args)
        mock_os.listdir.return_value = []  # Empty directory
        
        def mock_isdir_side_effect(path):
            return path == base_dir
        
        mock_os.path.isdir.side_effect = mock_isdir_side_effect
        
        # Login as admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/api/browse_folders_ss')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 0