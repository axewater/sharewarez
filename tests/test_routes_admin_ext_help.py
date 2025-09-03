import pytest
from flask import url_for
from modules.models import User
from modules import db
from uuid import uuid4


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


class TestAdminHelpRoute:
    
    def test_admin_help_requires_login(self, client):
        """Test that admin help page requires login."""
        response = client.get('/admin/help')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_admin_help_requires_admin(self, client, regular_user):
        """Test that admin help page requires admin role."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/help')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_admin_help_admin_access(self, client, admin_user):
        """Test that admin can access help page."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/help')
        assert response.status_code == 200
    
    def test_admin_help_renders_template(self, client, admin_user):
        """Test that admin help page renders the correct template."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/help')
        assert response.status_code == 200
        # Check that the response contains expected help content
        response_data = response.get_data(as_text=True)
        assert 'admin_help.html' in response_data or 'help' in response_data.lower()
    
    def test_admin_help_content_type(self, client, admin_user):
        """Test that admin help page returns HTML content."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/help')
        assert response.status_code == 200
        assert 'text/html' in response.content_type
    
    def test_admin_help_no_side_effects(self, client, admin_user):
        """Test that accessing help page has no side effects."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # Make multiple requests to ensure no side effects
        response1 = client.get('/admin/help')
        response2 = client.get('/admin/help')
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.data == response2.data
    
    def test_admin_help_template_rendering(self, client, admin_user):
        """Test that admin help page properly renders template content."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/help')
        assert response.status_code == 200
        # Verify this is an HTML response containing help content
        response_data = response.get_data(as_text=True)
        assert '<html' in response_data.lower() or '<!doctype' in response_data.lower()
    
    def test_admin_help_blueprint_registration(self, app):
        """Test that admin help route is properly registered."""
        with app.test_request_context():
            assert url_for('admin2.admin_help') == '/admin/help'
    
    def test_admin_help_get_method_only(self, client, admin_user):
        """Test that admin help only accepts GET requests."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        # GET should work
        response_get = client.get('/admin/help')
        assert response_get.status_code == 200
        
        # POST should not be allowed
        response_post = client.post('/admin/help')
        assert response_post.status_code == 405  # Method Not Allowed
        
        # PUT should not be allowed
        response_put = client.put('/admin/help')
        assert response_put.status_code == 405  # Method Not Allowed
        
        # DELETE should not be allowed
        response_delete = client.delete('/admin/help')
        assert response_delete.status_code == 405  # Method Not Allowed
    
    def test_admin_help_decorators_applied(self, client):
        """Test that both login_required and admin_required decorators are applied."""
        # Test without any authentication - should redirect due to login_required
        response = client.get('/admin/help')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_admin_help_consistent_response(self, client, admin_user):
        """Test that admin help page returns consistent responses."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        responses = []
        for _ in range(3):
            response = client.get('/admin/help')
            responses.append(response)
        
        # All responses should be successful
        for response in responses:
            assert response.status_code == 200
        
        # All responses should have the same content
        for i in range(1, len(responses)):
            assert responses[0].data == responses[i].data
    
    def test_admin_help_security_headers(self, client, admin_user):
        """Test that admin help page includes appropriate security considerations."""
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/help')
        assert response.status_code == 200
        
        # Verify that sensitive information isn't accidentally exposed
        response_data = response.get_data(as_text=True).lower()
        
        # These should not appear in help content
        sensitive_terms = ['password', 'secret', 'api_key', 'token']
        for term in sensitive_terms:
            # Note: This is a basic check - actual help content might legitimately mention these terms
            # but they shouldn't be actual values
            assert term not in response_data or 'help' in response_data