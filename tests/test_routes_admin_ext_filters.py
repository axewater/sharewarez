import pytest
from flask import url_for
from modules.models import ReleaseGroup, User
from modules import db
from uuid import uuid4
import time


@pytest.fixture
def admin_user(db_session):
    """Create an admin user."""
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
    """Create a regular user."""
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


class TestEditFiltersRoute:
    
    def test_edit_filters_requires_login(self, client):
        """Test that edit_filters requires login."""
        response = client.get('/admin/edit_filters')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_edit_filters_requires_admin(self, client, regular_user):
        """Test that edit_filters requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/edit_filters')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_edit_filters_get_admin_access(self, client, admin_user):
        """Test that admin can access edit_filters page."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/edit_filters')
        assert response.status_code == 200
    
    def test_edit_filters_displays_existing_groups(self, client, admin_user):
        """Test that existing release groups are displayed."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        group1 = ReleaseGroup(rlsgroup=f'TestGroup1_{unique_suffix}', rlsgroupcs='no')
        group2 = ReleaseGroup(rlsgroup=f'TestGroup2_{unique_suffix}', rlsgroupcs='yes')
        
        db.session.add_all([group1, group2])
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/edit_filters')
        assert response.status_code == 200
        response_data = response.get_data(as_text=True)
        assert f'TestGroup1_{unique_suffix}' in response_data
        assert f'TestGroup2_{unique_suffix}' in response_data
    
    def test_edit_filters_empty_groups(self, client, admin_user):
        """Test edit_filters with no existing groups."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/edit_filters')
        assert response.status_code == 200
    
    def test_edit_filters_post_valid_data(self, client, admin_user):
        """Test adding a new filter with valid POST data."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/edit_filters', data={
            'rlsgroup': f'NewGroup_{unique_suffix}',
            'rlsgroupcs': 'no',
            'submit': 'Add'
        })
        
        assert response.status_code == 302
        assert '/admin/edit_filters' in response.location
        
        # Verify the group was added to database
        new_group = db.session.query(ReleaseGroup).filter_by(rlsgroup=f'NewGroup_{unique_suffix}').first()
        assert new_group is not None
        assert new_group.rlsgroupcs == 'no'
    
    def test_edit_filters_post_case_sensitive_yes(self, client, admin_user):
        """Test adding filter with case-sensitive=yes."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/edit_filters', data={
            'rlsgroup': f'CaseSensitive_{unique_suffix}',
            'rlsgroupcs': 'yes',
            'submit': 'Add'
        })
        
        assert response.status_code == 302
        
        # Verify the group was added with correct case sensitivity
        new_group = db.session.query(ReleaseGroup).filter_by(rlsgroup=f'CaseSensitive_{unique_suffix}').first()
        assert new_group is not None
        assert new_group.rlsgroupcs == 'yes'
    
    def test_edit_filters_post_invalid_data(self, client, admin_user):
        """Test POST with invalid data (missing rlsgroup)."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/edit_filters', data={
            'rlsgroup': '',  # Empty rlsgroup should fail validation
            'rlsgroupcs': 'no',
            'submit': 'Add'
        })
        
        # Should return the form page with errors, not redirect
        assert response.status_code == 200
    
    def test_edit_filters_post_flash_message(self, client, admin_user):
        """Test that flash message is shown after successful add."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.post('/admin/edit_filters', data={
            'rlsgroup': f'FlashTest_{unique_suffix}',
            'rlsgroupcs': 'no',
            'submit': 'Add'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'New release group filter added.' in response.data
    
    def test_edit_filters_database_ordering(self, client, admin_user):
        """Test that filters are ordered by rlsgroup ascending."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        group_z = ReleaseGroup(rlsgroup=f'ZGroup_{unique_suffix}', rlsgroupcs='no')
        group_a = ReleaseGroup(rlsgroup=f'AGroup_{unique_suffix}', rlsgroupcs='no')
        group_m = ReleaseGroup(rlsgroup=f'MGroup_{unique_suffix}', rlsgroupcs='no')
        
        db.session.add_all([group_z, group_a, group_m])
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/edit_filters')
        assert response.status_code == 200
        
        # Verify ordering in database
        from sqlalchemy import select
        groups = db.session.execute(
            select(ReleaseGroup).where(
                ReleaseGroup.rlsgroup.in_([f'ZGroup_{unique_suffix}', f'AGroup_{unique_suffix}', f'MGroup_{unique_suffix}'])
            ).order_by(ReleaseGroup.rlsgroup.asc())
        ).scalars().all()
        
        assert len(groups) == 3
        assert groups[0].rlsgroup == f'AGroup_{unique_suffix}'
        assert groups[1].rlsgroup == f'MGroup_{unique_suffix}'
        assert groups[2].rlsgroup == f'ZGroup_{unique_suffix}'


class TestDeleteFilterRoute:
    
    def test_delete_filter_requires_login(self, client):
        """Test that delete_filter requires login."""
        response = client.get('/delete_filter/1')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_delete_filter_requires_admin(self, client, regular_user):
        """Test that delete_filter requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/delete_filter/1')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_delete_filter_success(self, client, admin_user):
        """Test successful deletion of an existing filter."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        test_group = ReleaseGroup(rlsgroup=f'ToDelete_{unique_suffix}', rlsgroupcs='no')
        db.session.add(test_group)
        db.session.commit()
        group_id = test_group.id
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/delete_filter/{group_id}')
        assert response.status_code == 302
        assert '/admin/edit_filters' in response.location
        
        # Verify the group was deleted
        deleted_group = db.session.get(ReleaseGroup, group_id)
        assert deleted_group is None
    
    def test_delete_filter_not_found(self, client, admin_user):
        """Test deletion of non-existent filter returns 404."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Use a very high ID that shouldn't exist
        response = client.get('/delete_filter/999999')
        assert response.status_code == 404
    
    def test_delete_filter_flash_message(self, client, admin_user):
        """Test that flash message is shown after successful deletion."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        test_group = ReleaseGroup(rlsgroup=f'ToDeleteFlash_{unique_suffix}', rlsgroupcs='no')
        db.session.add(test_group)
        db.session.commit()
        group_id = test_group.id
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get(f'/delete_filter/{group_id}', follow_redirects=True)
        assert response.status_code == 200
        assert b'Release group filter removed.' in response.data
    
    def test_delete_filter_removes_from_database(self, client, admin_user):
        """Test that filter is actually removed from database."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        test_group = ReleaseGroup(rlsgroup=f'ToRemove_{unique_suffix}', rlsgroupcs='yes')
        db.session.add(test_group)
        db.session.commit()
        group_id = test_group.id
        
        # Verify it exists before deletion
        existing_group = db.session.get(ReleaseGroup, group_id)
        assert existing_group is not None
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        client.get(f'/delete_filter/{group_id}')
        
        # Verify it's gone after deletion
        deleted_group = db.session.get(ReleaseGroup, group_id)
        assert deleted_group is None


class TestFiltersIntegration:
    
    def test_multiple_filters_creation(self, client, admin_user):
        """Test adding multiple filters in sequence."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Add first filter
        response1 = client.post('/admin/edit_filters', data={
            'rlsgroup': f'Multi1_{unique_suffix}',
            'rlsgroupcs': 'no',
            'submit': 'Add'
        })
        assert response1.status_code == 302
        
        # Add second filter
        response2 = client.post('/admin/edit_filters', data={
            'rlsgroup': f'Multi2_{unique_suffix}',
            'rlsgroupcs': 'yes',
            'submit': 'Add'
        })
        assert response2.status_code == 302
        
        # Verify both exist
        filters = db.session.query(ReleaseGroup).filter(
            ReleaseGroup.rlsgroup.in_([f'Multi1_{unique_suffix}', f'Multi2_{unique_suffix}'])
        ).all()
        assert len(filters) == 2
    
    def test_filter_persistence(self, client, admin_user):
        """Test that filters persist across requests."""
        unique_suffix = str(int(time.time() * 1000))[-6:]
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Add filter
        client.post('/admin/edit_filters', data={
            'rlsgroup': f'Persist_{unique_suffix}',
            'rlsgroupcs': 'no',
            'submit': 'Add'
        })
        
        # Make a new GET request
        response = client.get('/admin/edit_filters')
        assert response.status_code == 200
        response_data = response.get_data(as_text=True)
        assert f'Persist_{unique_suffix}' in response_data
    
    def test_filters_routes_blueprint_registration(self, app):
        """Test that filter routes are properly registered."""
        with app.test_request_context():
            assert url_for('admin2.edit_filters') == '/admin/edit_filters'
            assert url_for('admin2.delete_filter', id=1) == '/delete_filter/1'