import pytest
from modules.utils_functions import format_size
from modules.utils_filename import sanitize_filename
from modules.utils_gamenames import clean_game_name

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
    ("Cyberpunk.2077.Dodi.Repack", "Cyberpunk 2077")
])
def test_clean_game_name(filename_in, expected_output):
    """Tests the clean_game_name function with sample patterns."""
    insensitive_patterns = ["-GOG", ".GOG", "-FLT", "Dodi", "Repack"]
    sensitive_patterns = []
    assert clean_game_name(filename_in, insensitive_patterns, sensitive_patterns) == expected_output
