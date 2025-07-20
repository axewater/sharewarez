import pytest
from unittest.mock import patch, mock_open
from modules.utils_functions import format_size
from modules.utils_filename import sanitize_filename
from modules.utils_gamenames import clean_game_name
from modules.utils_uptime import format_uptime, get_system_uptime
from modules.utils_discord import get_folder_size_in_bytes

@pytest.mark.parametrize("bytes_in, expected_output", [
    (1024, "1.00 KB"),
    (1048576, "1.00 MB"),
    (1500000, "1.43 MB"),
    (0, "0.00 KB"),
    (None, "0 MB"),
    (2147483648, "2.00 GB")
])
def test_format_size(bytes_in, expected_output):
    """Tests the format_size function for various byte inputs."""
    assert format_size(bytes_in) == expected_output

@pytest.mark.parametrize("filename_in, expected_output", [
    ("My Game: The Adventure Begins!.zip", "My_Game_The_Adventure_Begins.zip"),
    ("file/with\\slashes.doc", "filewithslashes.doc"),
    (".hiddenfile", "hiddenfile"),
    ("", "unnamed_file"),
    ("a" * 250 + ".txt", "a" * 196 + ".txt")
])
def test_sanitize_filename(filename_in, expected_output):
    """Tests the sanitize_filename function for various filenames."""
    assert sanitize_filename(filename_in) == expected_output

@pytest.mark.parametrize("filename_in, expected_output", [
    ("The.Witcher.3.Wild.Hunt-GOG", "The Witcher 3 Wild Hunt"),
    ("Some.Game.v1.2.3-FLT", "Some Game"),
    ("Cyberpunk.2077.Dodi.Repack", "Cyberpunk 2077"),
    ("setup_Grand.Theft.Auto.V-SKIDROW", "Grand Theft Auto V"),
    ("Portal.2.Complete-STEAM", "Portal 2 Complete"),
    ("Half_Life_2_Episode_One-VALVE", "Half Life 2 Episode One"),
    ("Doom.Eternal.Deluxe-CODEX", "Doom Eternal Deluxe")
])
def test_clean_game_name(filename_in, expected_output):
    """Tests the clean_game_name function with sample patterns."""
    insensitive_patterns = ["-GOG", ".GOG", "-FLT", "Dodi", "Repack", "-SKIDROW", "-STEAM", "-VALVE", "-CODEX"]
    sensitive_patterns = []
    assert clean_game_name(filename_in, insensitive_patterns, sensitive_patterns) == expected_output

@pytest.mark.parametrize("seconds_in, expected_output", [
    (3661, "1 hour, 1 minute"),
    (86400, "1 day"),
    (90061, "1 day, 1 hour, 1 minute"),
    (59, "Less than 1 minute"),
    (None, "Unavailable"),
    (172800, "2 days")
])
def test_format_uptime(seconds_in, expected_output):
    """Tests the format_uptime function with various time inputs."""
    assert format_uptime(seconds_in) == expected_output

@patch('builtins.open', mock_open(read_data='12345.67 9876.54\n'))
def test_get_system_uptime_linux():
    """Tests get_system_uptime function on Linux systems."""
    with patch('platform.system', return_value='Linux'):
        result = get_system_uptime()
        assert result == 12345.67

@patch('os.path.getsize')
@patch('os.path.isfile')
def test_get_folder_size_in_bytes_single_file(mock_isfile, mock_getsize):
    """Tests get_folder_size_in_bytes function with a single file."""
    mock_isfile.return_value = True
    mock_getsize.return_value = 1024
    
    result = get_folder_size_in_bytes('/path/to/file.txt')
    assert result == 1024

@patch('os.walk')
@patch('os.path.exists')
@patch('os.path.getsize')
@patch('os.path.isfile')
def test_get_folder_size_in_bytes_directory(mock_isfile, mock_getsize, mock_exists, mock_walk):
    """Tests get_folder_size_in_bytes function with a directory."""
    mock_isfile.return_value = False
    mock_walk.return_value = [('/test', [], ['file1.txt', 'file2.txt'])]
    mock_exists.return_value = True
    mock_getsize.side_effect = [512, 256]
    
    result = get_folder_size_in_bytes('/test')
    assert result == 768
