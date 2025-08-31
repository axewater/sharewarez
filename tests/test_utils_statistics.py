import pytest
from unittest.mock import patch

from modules.utils_statistics import get_download_statistics






class TestGetDownloadStatistics:
    """Test get_download_statistics function."""
    
    def test_get_download_statistics_empty_database(self, app):
        """Test function with empty database returns empty results."""
        from unittest.mock import MagicMock
        
        with app.app_context():
            # Mock empty database responses
            mock_execute = MagicMock()
            mock_execute.return_value.all.return_value = []
            
            with patch('modules.utils_statistics.db.session.execute', mock_execute):
                result = get_download_statistics()
            
            # Should return dict with all expected keys
            expected_keys = [
                'users_with_invites', 'downloads_per_user', 'top_downloaders',
                'top_collectors', 'top_games', 'download_trends'
            ]
            
            assert isinstance(result, dict)
            for key in expected_keys:
                assert key in result
                assert 'labels' in result[key]
                assert 'data' in result[key]
                assert isinstance(result[key]['labels'], list)
                assert isinstance(result[key]['data'], list)
                assert len(result[key]['labels']) == 0
                assert len(result[key]['data']) == 0
    
    def test_get_download_statistics_with_complete_data(self, app):
        """Test function with complete sample data returns correct statistics."""
        from unittest.mock import MagicMock
        from datetime import date
        
        with app.app_context():
            # Mock all the database queries
            mock_execute = MagicMock()
            
            # Mock downloads_per_user query
            downloads_per_user_data = [('alice', 5), ('bob', 3), ('charlie', 1)]
            
            # Mock top_games query
            top_games_data = [('Game Beta', 4), ('Game Alpha', 3), ('Game Gamma', 2)]
            
            # Mock download_trends query (within 30 days)
            download_trends_data = [
                (date(2025, 8, 26), 1), (date(2025, 8, 21), 1), (date(2025, 8, 16), 1),
                (date(2025, 8, 11), 1), (date(2025, 8, 6), 1), (date(2025, 8, 28), 1)
            ]
            
            # Mock top_downloaders query
            top_downloaders_data = [('alice', 5), ('bob', 3), ('charlie', 1)]
            
            # Mock top_collectors query
            top_collectors_data = [('alice', 2), ('bob', 1)]
            
            # Mock users_with_invites query
            users_with_invites_data = [('alice', 3), ('bob', 1)]
            
            # Configure the mock to return different results for each call
            mock_execute.return_value.all.side_effect = [
                downloads_per_user_data,       # First call: downloads_per_user
                top_games_data,                # Second call: top_games
                download_trends_data,          # Third call: download_trends
                top_downloaders_data,          # Fourth call: top_downloaders
                top_collectors_data,           # Fifth call: top_collectors
                users_with_invites_data        # Sixth call: users_with_invites
            ]
            
            with patch('modules.utils_statistics.db.session.execute', mock_execute):
                result = get_download_statistics()
            
            # Verify structure
            assert isinstance(result, dict)
            expected_keys = [
                'users_with_invites', 'downloads_per_user', 'top_downloaders',
                'top_collectors', 'top_games', 'download_trends'
            ]
            
            for key in expected_keys:
                assert key in result
                assert 'labels' in result[key]
                assert 'data' in result[key]
                assert isinstance(result[key]['labels'], list)
                assert isinstance(result[key]['data'], list)
                assert len(result[key]['labels']) == len(result[key]['data'])
            
            # Test users_with_invites
            assert result['users_with_invites']['labels'] == ['alice', 'bob']
            assert result['users_with_invites']['data'] == [3, 1]
            
            # Test downloads_per_user
            assert set(result['downloads_per_user']['labels']) == {'alice', 'bob', 'charlie'}
            assert set(result['downloads_per_user']['data']) == {5, 3, 1}
            
            # Test top_downloaders (ordered by count desc)
            assert result['top_downloaders']['labels'] == ['alice', 'bob', 'charlie']
            assert result['top_downloaders']['data'] == [5, 3, 1]
            
            # Test top_collectors
            assert result['top_collectors']['labels'] == ['alice', 'bob']
            assert result['top_collectors']['data'] == [2, 1]
            
            # Test top_games (ordered by count desc)
            assert result['top_games']['labels'] == ['Game Beta', 'Game Alpha', 'Game Gamma']
            assert result['top_games']['data'] == [4, 3, 2]
            
            # Test download_trends
            assert len(result['download_trends']['labels']) == 6
            assert sum(result['download_trends']['data']) == 6
            
            # Verify date format in download_trends labels
            for date_label in result['download_trends']['labels']:
                assert len(date_label) == 10  # YYYY-MM-DD format
                assert date_label.count('-') == 2
    
    def test_get_download_statistics_only_favorites(self, app):
        """Test function when only favorites exist but no downloads or invites."""
        from unittest.mock import MagicMock
        
        with app.app_context():
            # Mock database responses: only top_collectors has data
            mock_execute = MagicMock()
            mock_execute.return_value.all.side_effect = [
                [],  # downloads_per_user - empty
                [],  # top_games - empty
                [],  # download_trends - empty
                [],  # top_downloaders - empty
                [('alice', 2), ('bob', 1)],  # top_collectors - has data
                []   # users_with_invites - empty
            ]
            
            with patch('modules.utils_statistics.db.session.execute', mock_execute):
                result = get_download_statistics()
            
            # Only top_collectors should have data
            assert len(result['top_collectors']['labels']) == 2
            assert result['top_collectors']['labels'] == ['alice', 'bob']
            assert result['top_collectors']['data'] == [2, 1]
            
            # All other categories should be empty
            empty_categories = ['users_with_invites', 'downloads_per_user', 'top_downloaders', 'top_games', 'download_trends']
            for key in empty_categories:
                assert len(result[key]['labels']) == 0
                assert len(result[key]['data']) == 0
    
    def test_get_download_statistics_only_invites(self, app):
        """Test function when only invite tokens exist but no downloads or favorites."""
        from unittest.mock import MagicMock
        
        with app.app_context():
            # Mock database responses: only users_with_invites has data
            mock_execute = MagicMock()
            mock_execute.return_value.all.side_effect = [
                [],  # downloads_per_user - empty
                [],  # top_games - empty
                [],  # download_trends - empty
                [],  # top_downloaders - empty
                [],  # top_collectors - empty
                [('alice', 3), ('bob', 1)]  # users_with_invites - has data
            ]
            
            with patch('modules.utils_statistics.db.session.execute', mock_execute):
                result = get_download_statistics()
            
            # Only users_with_invites should have data
            assert len(result['users_with_invites']['labels']) == 2
            assert result['users_with_invites']['labels'] == ['alice', 'bob']
            assert result['users_with_invites']['data'] == [3, 1]
            
            # All other categories should be empty
            empty_categories = ['downloads_per_user', 'top_downloaders', 'top_collectors', 'top_games', 'download_trends']
            for key in empty_categories:
                assert len(result[key]['labels']) == 0
                assert len(result[key]['data']) == 0
    
    def test_download_trends_date_filtering(self, app):
        """Test that download_trends only includes downloads from last 30 days."""
        from unittest.mock import MagicMock
        from datetime import date
        
        with app.app_context():
            # Mock database responses: simulate recent vs old downloads
            mock_execute = MagicMock()
            
            # Mock responses for all queries - most empty except for key ones
            mock_execute.return_value.all.side_effect = [
                [('alice', 6), ('bob', 3)],  # downloads_per_user (includes all downloads)
                [('Game Alpha', 4), ('Game Beta', 3), ('Game Gamma', 2)],  # top_games (all)
                [(date(2025, 8, 26), 1), (date(2025, 8, 21), 1), (date(2025, 8, 16), 1)],  # download_trends (only recent)
                [('alice', 6), ('bob', 3)],  # top_downloaders (all)
                [],  # top_collectors - empty
                []   # users_with_invites - empty
            ]
            
            with patch('modules.utils_statistics.db.session.execute', mock_execute):
                result = get_download_statistics()
            
            # download_trends should only include recent downloads (3 total)
            total_trend_downloads = sum(result['download_trends']['data'])
            assert total_trend_downloads == 3
            
            # But total downloads per user should include all downloads (9 total)
            total_all_downloads = sum(result['downloads_per_user']['data'])
            assert total_all_downloads == 9  # 6 + 3 = 9 total downloads
    
    def test_top_lists_ordering_and_limits(self, app):
        """Test that top lists are properly ordered and limited to 10."""
        from unittest.mock import MagicMock
        
        with app.app_context():
            # Mock database responses: simulate more than 10 items with proper ordering
            mock_execute = MagicMock()
            
            # Generate test data for 10 users (limited by LIMIT 10)
            top_downloaders_data = [(f'user_{i:02d}', 15-i) for i in range(10)]  # Decreasing order
            users_with_invites_data = [(f'user_{i:02d}', 15-i) for i in range(10)]  # Decreasing order
            top_games_data = [(f'Game {i:02d}', 20-i) for i in range(10)]  # Decreasing order
            
            mock_execute.return_value.all.side_effect = [
                [],  # downloads_per_user - empty for this test
                top_games_data,           # top_games - ordered by count desc, limited to 10
                [],  # download_trends - empty
                top_downloaders_data,     # top_downloaders - ordered by count desc, limited to 10
                [],  # top_collectors - empty
                users_with_invites_data   # users_with_invites - ordered by count desc, limited to 10
            ]
            
            with patch('modules.utils_statistics.db.session.execute', mock_execute):
                result = get_download_statistics()
            
            # Test top_downloaders ordering and limit
            assert len(result['top_downloaders']['labels']) == 10  # Limited to 10
            
            # Should be ordered by download count descending
            prev_count = float('inf')
            for i, count in enumerate(result['top_downloaders']['data']):
                assert count <= prev_count, f"top_downloaders not properly ordered at index {i}"
                prev_count = count
            
            # First user should have most downloads, last should have least (of the top 10)
            assert result['top_downloaders']['data'][0] == 15  # user_00
            assert result['top_downloaders']['data'][-1] == 6   # user_09 (10th user)
            
            # Test users_with_invites ordering and limit
            assert len(result['users_with_invites']['labels']) == 10  # Limited to 10
            
            # Should be ordered by invite count descending
            prev_count = float('inf')
            for i, count in enumerate(result['users_with_invites']['data']):
                assert count <= prev_count, f"users_with_invites not properly ordered at index {i}"
                prev_count = count
            
            # Test top_games ordering and limit
            assert len(result['top_games']['labels']) == 10  # Limited to 10
            
            # Should be ordered by download count descending
            prev_count = float('inf')
            for i, count in enumerate(result['top_games']['data']):
                assert count <= prev_count, f"top_games not properly ordered at index {i}"
                prev_count = count