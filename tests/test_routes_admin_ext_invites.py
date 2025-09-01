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
        
        assert response.status_code == 200
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
        
        assert response.status_code == 200
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
        
        assert response.status_code == 200
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
        
        assert response.status_code == 200
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
        
        assert response.status_code == 200
        
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
        
        assert response.status_code == 200
        
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
        
        assert response.status_code == 200
        
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
        
        assert response.status_code == 200

    def test_admin_can_add_large_number_invites(self, client, admin_user, regular_user, db_session):
        """Test admin can add large number of invites."""
        original_quota = regular_user.invite_quota
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        response = client.post('/admin/manage_invites', data={
            'user_id': regular_user.user_id,
            'invites_number': '1000'
        })
        
        assert response.status_code == 200
        
        db_session.refresh(regular_user)
        assert regular_user.invite_quota == original_quota + 1000


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
        
        # Should complete successfully but flash error for user not found
        assert response.status_code == 200

    def test_missing_invites_number_field(self, client, admin_user, regular_user):
        """Test POST request with missing invites_number field causes TypeError."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # This will cause TypeError: int() argument must be a string... not 'NoneType'
        with pytest.raises(TypeError):
            client.post('/admin/manage_invites', data={
                'user_id': regular_user.user_id
            })

    def test_non_numeric_invites_number(self, client, admin_user, regular_user):
        """Test POST request with non-numeric invites_number causes ValueError."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # This will cause ValueError: invalid literal for int() with base 10: 'not_a_number'
        with pytest.raises(ValueError):
            client.post('/admin/manage_invites', data={
                'user_id': regular_user.user_id,
                'invites_number': 'not_a_number'
            })

    def test_empty_invites_number(self, client, admin_user, regular_user):
        """Test POST request with empty invites_number causes ValueError."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True

        # This will cause ValueError: invalid literal for int() with base 10: ''
        with pytest.raises(ValueError):
            client.post('/admin/manage_invites', data={
                'user_id': regular_user.user_id,
                'invites_number': ''
            })

    @patch('modules.routes_admin_ext.invites.render_template')
    def test_database_error_handling(self, mock_render, client, admin_user, regular_user, monkeypatch):
        """Test that database errors propagate as expected."""
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

        # This should raise the database error since there's no error handling
        with pytest.raises(Exception, match="Database connection failed"):
            client.get('/admin/manage_invites')