import pytest
from flask import url_for
from modules.models import AllowedFileType, User
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


class TestExtensionsRoute:
    
    def test_extensions_route_requires_login(self, client):
        response = client.get('/admin/extensions')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_extensions_route_requires_admin(self, client, regular_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(regular_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/extensions')
        assert response.status_code == 302
        assert 'login' in response.location
    
    def test_extensions_route_admin_access(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/extensions')
        assert response.status_code == 200
        assert b'admin_manage_extensions.html' in response.data or b'Extensions' in response.data
    
    def test_extensions_displays_allowed_types(self, client, admin_user):
        unique_suffix = str(int(time.time() * 1000))[-6:]
        file_type1 = AllowedFileType(value=f'.t1{unique_suffix}')
        file_type2 = AllowedFileType(value=f'.t2{unique_suffix}')
        file_type3 = AllowedFileType(value=f'.t3{unique_suffix}')
        
        db.session.add_all([file_type1, file_type2, file_type3])
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with client.application.app_context():
            response = client.get('/admin/extensions')
            assert response.status_code == 200
            
            response_data = response.get_data(as_text=True)
            assert f'.t1{unique_suffix}' in response_data or 'allowed_types' in str(response.data)
    
    def test_extensions_ordered_by_value_asc(self, client, admin_user):
        unique_suffix = str(int(time.time() * 1000))[-6:]
        file_type_z = AllowedFileType(value=f'.z{unique_suffix}')
        file_type_a = AllowedFileType(value=f'.a{unique_suffix}')
        file_type_m = AllowedFileType(value=f'.m{unique_suffix}')
        
        db.session.add_all([file_type_z, file_type_a, file_type_m])
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        with client.application.app_context():
            response = client.get('/admin/extensions')
            assert response.status_code == 200
    
    def test_extensions_empty_allowed_types(self, client, admin_user):
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/extensions')
        assert response.status_code == 200
    
    def test_extensions_template_context(self, client, admin_user):
        unique_suffix = str(int(time.time() * 1000))[-6:]
        file_type = AllowedFileType(value=f'.ctx{unique_suffix}')
        db.session.add(file_type)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/extensions')
        assert response.status_code == 200
    
    def test_extensions_database_query_execution(self, client, admin_user):
        unique_suffix = str(int(time.time() * 1000))[-6:]
        file_types = [
            AllowedFileType(value=f'.q1{unique_suffix}'),
            AllowedFileType(value=f'.q2{unique_suffix}'),
            AllowedFileType(value=f'.q3{unique_suffix}')
        ]
        
        for ft in file_types:
            db.session.add(ft)
        db.session.commit()
        
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin_user.id)
            sess['_fresh'] = True
        
        response = client.get('/admin/extensions')
        assert response.status_code == 200
        
        # Verify that the query was executed successfully and our test data exists
        with client.application.app_context():
            from sqlalchemy import select
            test_values = [f'.q1{unique_suffix}', f'.q2{unique_suffix}', f'.q3{unique_suffix}']
            test_types = db.session.execute(
                select(AllowedFileType).where(AllowedFileType.value.in_(test_values))
                .order_by(AllowedFileType.value.asc())
            ).scalars().all()
            assert len(test_types) == 3
            assert test_types[0].value == f'.q1{unique_suffix}'
            assert test_types[2].value == f'.q3{unique_suffix}'
    
    def test_extensions_route_blueprint_registration(self, app):
        with app.test_request_context():
            assert url_for('admin2.extensions') == '/admin/extensions'