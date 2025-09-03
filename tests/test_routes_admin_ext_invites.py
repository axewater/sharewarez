"""
Unit tests for modules.routes_admin_ext.invites

Tests invite management routes including viewing users with invite quotas and updating invite counts.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import url_for
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from modules.models import User, InviteToken


@pytest.fixture(scope='function', autouse=True)
def clean_database(db_session):
    """Clean database before each test to ensure isolation."""
    # Clean up all related tables with CASCADE
    db_session.execute(text("TRUNCATE TABLE invite_tokens RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE games RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE libraries RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE game_genre_association RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE game_theme_association RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE game_game_mode_association RESTART IDENTITY CASCADE"))
    db_session.execute(text("TRUNCATE TABLE user_favorites RESTART IDENTITY CASCADE"))
    db_session.commit()


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
def invite_token_unused(db_session, regular_user):
    """Create an unused invite token."""
    token = InviteToken(
        token='test_unused_token_123',
        creator_user_id=regular_user.user_id,
        used=False,
        recipient_email='recipient@example.com'
    )
    db_session.add(token)
    db_session.commit()
    return token


@pytest.fixture
def invite_token_used(db_session, regular_user, admin_user):
    """Create a used invite token."""
    token = InviteToken(
        token='test_used_token_456',
        creator_user_id=regular_user.user_id,
        used=True,
        used_by=admin_user.user_id,
        used_at=datetime.now(timezone.utc),
        recipient_email='used_recipient@example.com'
    )
    db_session.add(token)
    db_session.commit()
    return token


class TestManageInvitesAuthentication:
    """Test authentication and authorization for manage_invites route."""

    def test_unauthenticated_get_redirects_to_login(self, client):
        """Test that unauthenticated users are redirected to login."""
        response = client.get('/admin/manage_invites')
        assert response.status_code == 302
        assert '/login' in response.location

    def test_unauthenticated_post_redirects_to_login(self, client):
        """Test that unauthenticated POST requests are redirected to login."""
        response = client.post('/admin/manage_invites', data={
            'user_id': 'test_id',
            'invites_number': '5'
        })
        assert response.status_code == 302
        assert '/login' in response.location

    def test_non_admin_get_redirects(self, client, regular_user):
        """Test that non-admin users are redirected when accessing GET."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/manage_invites')
        assert response.status_code == 302

    def test_non_admin_post_redirects(self, client, regular_user):
        """Test that non-admin users are redirected when accessing POST."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '5'
        })
        assert response.status_code == 302


class TestManageInvitesGet:
    """Test GET requests to manage_invites route."""

    @patch('modules.routes_admin_ext.invites.render_template')
    def test_admin_can_access_manage_invites_empty(self, mock_render, client, admin_user):
        """Test admin can access manage invites page with no users."""
        mock_render.return_value = 'mocked_template'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/manage_invites')
        
        assert response.status_code == 200  # Renders template after processing
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert args[0] == 'admin/admin_manage_invites.html'
        assert 'users' in kwargs
        assert 'user_unused_invites' in kwargs
        assert len(kwargs['users']) == 1  # Only the admin user
        assert kwargs['user_unused_invites'] == {admin_user.user_id: 0}

    @patch('modules.routes_admin_ext.invites.render_template')
    def test_admin_can_access_with_multiple_users(self, mock_render, client, admin_user, regular_user):
        """Test admin can access manage invites page with multiple users."""
        mock_render.return_value = 'mocked_template'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/manage_invites')
        
        assert response.status_code == 200  # Renders template after processing
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert len(kwargs['users']) == 2
        assert kwargs['user_unused_invites'][admin_user.user_id] == 0
        assert kwargs['user_unused_invites'][regular_user.user_id] == 0

    @patch('modules.routes_admin_ext.invites.render_template')
    def test_admin_sees_correct_unused_invite_count(self, mock_render, client, admin_user, regular_user, invite_token_unused, invite_token_used):
        """Test that unused invite counts are calculated correctly."""
        mock_render.return_value = 'mocked_template'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/manage_invites')
        
        assert response.status_code == 200  # Renders template after processing
        args, kwargs = mock_render.call_args
        # Regular user should have 1 unused invite (invite_token_used is used, invite_token_unused is not)
        assert kwargs['user_unused_invites'][regular_user.user_id] == 1
        assert kwargs['user_unused_invites'][admin_user.user_id] == 0

    @patch('modules.routes_admin_ext.invites.render_template')
    def test_admin_sees_multiple_unused_invites(self, mock_render, client, admin_user, regular_user, db_session):
        """Test that multiple unused invites are counted correctly."""
        # Create multiple unused invite tokens for regular user
        for i in range(3):
            token = InviteToken(
                token=f'unused_token_{i}',
                creator_user_id=regular_user.user_id,
                used=False,
                recipient_email=f'recipient{i}@example.com'
            )
            db_session.add(token)
        db_session.commit()
        
        mock_render.return_value = 'mocked_template'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.get('/admin/manage_invites')
        
        assert response.status_code == 200  # Renders template after processing
        args, kwargs = mock_render.call_args
        assert kwargs['user_unused_invites'][regular_user.user_id] == 3


class TestManageInvitesPost:
    """Test POST requests to manage_invites route."""

    def test_admin_can_update_user_invite_quota(self, client, admin_user, regular_user, db_session):
        """Test admin can successfully update user invite quota."""
        original_quota = regular_user.invite_quota
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '10'
        })
        
        assert response.status_code == 200  # Renders template after processing
        
        # Check that the user's invite quota was updated
        db_session.refresh(regular_user)
        assert regular_user.invite_quota == original_quota + 10

    def test_admin_can_add_negative_invites(self, client, admin_user, regular_user, db_session):
        """Test admin can reduce invite quota with negative numbers."""
        regular_user.invite_quota = 20
        db_session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '-5'
        })
        
        assert response.status_code == 200  # Renders template after processing
        
        db_session.refresh(regular_user)
        assert regular_user.invite_quota == 15

    def test_admin_can_add_zero_invites(self, client, admin_user, regular_user, db_session):
        """Test admin can submit zero invites without changing quota."""
        original_quota = regular_user.invite_quota
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '0'
        })
        
        assert response.status_code == 200  # Renders template after processing
        
        db_session.refresh(regular_user)
        assert regular_user.invite_quota == original_quota

    def test_admin_update_nonexistent_user(self, client, admin_user):
        """Test admin updating non-existent user shows error."""
        fake_user_id = str(uuid4())
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': fake_user_id,
            'invites_number': '5'
        })
        
        assert response.status_code == 200  # Renders template with error message

    def test_admin_can_add_large_number_invites(self, client, admin_user, regular_user, db_session):
        """Test admin can add large number of invites up to limit."""
        original_quota = regular_user.invite_quota
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '1000'  # Maximum allowed
        })
        
        assert response.status_code == 200  # Renders template after processing
        
        db_session.refresh(regular_user)
        assert regular_user.invite_quota == original_quota + 1000

    def test_admin_cannot_exceed_invite_limits(self, client, admin_user, regular_user):
        """Test admin cannot add more than 1000 invites at once."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '1001'  # Over the limit
        })
        
        assert response.status_code == 302  # Redirect due to error
        assert 'manage_invites' in response.location

    def test_admin_cannot_reduce_invites_too_much(self, client, admin_user, regular_user):
        """Test admin cannot reduce invites by more than 1000 at once."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '-1001'  # Below the limit
        })
        
        assert response.status_code == 302  # Redirect due to error
        assert 'manage_invites' in response.location

    def test_invalid_uuid_format_rejected(self, client, admin_user):
        """Test that invalid UUID format for user_id is rejected."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': 'not-a-valid-uuid',
            'invites_number': '5'
        })
        
        assert response.status_code == 302  # Redirect due to error
        assert 'manage_invites' in response.location


class TestManageInvitesEdgeCases:
    """Test edge cases and error handling for manage_invites route."""

    def test_missing_user_id_field(self, client, admin_user):
        """Test POST request with missing user_id field."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Missing user_id should still work since request.form.get() returns None
        # and the route will try to find user with None ID, which returns None user
        response = client.post('/admin/manage_invites', data={
            'invites_number': '5'
        })
        
        # Missing user_id causes validation error and redirect
        assert response.status_code == 302

    def test_missing_invites_number_field(self, client, admin_user, regular_user):
        """Test POST request with missing invites_number field defaults to 0."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        original_quota = regular_user.invite_quota
        
        # Missing invites_number now defaults to 0, so no change expected
        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id
        })
        
        assert response.status_code == 200  # Renders template after processingful update
        # User quota should remain unchanged (added 0)
        from modules import db
        db.session.refresh(regular_user)
        assert regular_user.invite_quota == original_quota

    def test_non_numeric_invites_number(self, client, admin_user, regular_user):
        """Test POST request with non-numeric invites_number shows error and redirects."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # This will now be handled gracefully with error message and redirect
        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': 'not_a_number'
        })
        
        assert response.status_code == 302  # Redirect due to error
        assert 'manage_invites' in response.location

    def test_empty_invites_number(self, client, admin_user, regular_user):
        """Test POST request with empty invites_number defaults to 0."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        original_quota = regular_user.invite_quota
        
        # Empty invites_number now defaults to 0
        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': ''
        })
        
        assert response.status_code == 200  # Renders template after processingful update
        # User quota should remain unchanged (added 0)
        from modules import db
        db.session.refresh(regular_user)
        assert regular_user.invite_quota == original_quota

    @patch('modules.routes_admin_ext.invites.render_template')
    def test_database_error_handling_get(self, mock_render, client, admin_user, regular_user, monkeypatch):
        """Test that database errors in GET request are handled gracefully."""
        # Mock a database error
        def mock_execute_error(*args, **kwargs):
            raise Exception("Database connection failed")
        
        mock_render.return_value = 'mocked_template'
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Patch the db.session.execute method to raise an error
        from modules import db
        monkeypatch.setattr(db.session, 'execute', mock_execute_error)

        # This should now handle the database error gracefully
        response = client.get('/admin/manage_invites')
        assert response.status_code == 200
        
        # Check that template was called with empty data due to error
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert kwargs['users'] == []
        assert kwargs['user_unused_invites'] == {}

    def test_database_error_handling_post(self, client, admin_user, regular_user, monkeypatch):
        """Test that database errors in POST request are handled gracefully."""
        # Mock database error during user lookup
        def mock_execute_error(*args, **kwargs):
            raise Exception("Database connection failed")
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # Patch the db.session.execute method to raise an error
        from modules import db
        monkeypatch.setattr(db.session, 'execute', mock_execute_error)

        # This should handle the database error and redirect
        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '5'
        })
        
        assert response.status_code == 302  # Redirect due to error
        assert 'manage_invites' in response.location