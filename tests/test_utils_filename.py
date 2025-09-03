import pytest
from modules.utils_filename import sanitize_filename


class TestSanitizeFilename:
    """Test suite for the sanitize_filename function."""
    
    def test_basic_space_replacement(self):
        """Test that spaces are replaced with underscores."""
        result = sanitize_filename("hello world.txt")
        assert result == "hello_world.txt"
        
        result = sanitize_filename("multiple  spaces   here.txt")
        assert result == "multiple_spaces_here.txt"
    
    def test_invalid_character_removal(self):
        """Test removal of invalid characters."""
        result = sanitize_filename("file@#$%name.txt")
        assert result == "filename.txt"
        
        result = sanitize_filename("file[brackets]name.txt")
        assert result == "filebracketsname.txt"
    
    def test_windows_reserved_characters(self):
        """Test removal of Windows reserved characters."""
        result = sanitize_filename('file<name>.txt')
        assert result == "filename.txt"
        
        result = sanitize_filename('file:name|here?.txt')
        assert result == "filenamehere.txt"
        
        result = sanitize_filename('file"name\\path*.txt')
        assert result == "filenamepath.txt"
    
    def test_leading_dot_removal(self):
        """Test that leading dots are removed."""
        result = sanitize_filename(".hidden_file.txt")
        assert result == "hidden_file.txt"
        
        result = sanitize_filename("...multiple_dots.txt")
        assert result == "multiple_dots.txt"
    
    def test_duplicate_cleanup(self):
        """Test cleanup of duplicate underscores and dots."""
        result = sanitize_filename("file__name___here.txt")
        assert result == "file_name_here.txt"
        
        result = sanitize_filename("file...name.txt")
        assert result == "file.name.txt"
        
        result = sanitize_filename("file__name...here.txt")
        assert result == "file_name.here.txt"
    
    def test_length_truncation_with_extension(self):
        """Test truncation preserving file extension."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name, max_length=50)
        
        assert len(result) == 50
        assert result.endswith(".txt")
        assert result.startswith("a")
    
    def test_length_truncation_without_extension(self):
        """Test truncation of files without extension."""
        long_name = "a" * 300
        result = sanitize_filename(long_name, max_length=50)
        
        assert len(result) == 50
        assert result == "a" * 50
    
    def test_length_truncation_multiple_extensions(self):
        """Test truncation with multiple extensions."""
        long_name = "a" * 300 + ".tar.gz"
        result = sanitize_filename(long_name, max_length=50)
        
        assert len(result) == 50
        assert result.endswith(".gz")
        # Only the last extension is preserved in os.path.splitext
    
    def test_no_max_length(self):
        """Test behavior when max_length is None."""
        long_name = "a" * 500 + ".txt"
        result = sanitize_filename(long_name, max_length=None)
        
        assert len(result) == 504  # 500 + ".txt"
        assert result == long_name
    
    def test_empty_string_input(self):
        """Test behavior with empty string input."""
        result = sanitize_filename("")
        assert result == "unnamed_file"
    
    def test_only_invalid_characters(self):
        """Test string with only invalid characters."""
        result = sanitize_filename("@#$%^&*()")
        assert result == "unnamed_file"
        
        result = sanitize_filename("<>:\"/\\|?*")
        assert result == "unnamed_file"
    
    def test_only_dots_and_spaces(self):
        """Test string with only dots and spaces."""
        result = sanitize_filename("... . ..")
        assert result == "_._."
    
    def test_preserve_valid_characters(self):
        """Test preservation of valid characters."""
        result = sanitize_filename("file-name_123.txt")
        assert result == "file-name_123.txt"
        
        result = sanitize_filename("MyFile.v2.1.txt")
        assert result == "MyFile.v2.1.txt"
    
    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        # Unicode characters are preserved as \w includes Unicode letters
        result = sanitize_filename("file_café.txt")
        assert result == "file_café.txt"
        
        result = sanitize_filename("файл.txt")
        assert result == "файл.txt"
    
    def test_mixed_valid_invalid_characters(self):
        """Test mixed valid and invalid character combinations."""
        result = sanitize_filename("My@File#Name$123.txt")
        assert result == "MyFileName123.txt"
        
        result = sanitize_filename("test file (copy) [2023].txt")
        assert result == "test_file_copy_2023.txt"
    
    def test_extension_only_files(self):
        """Test files that are extension only."""
        result = sanitize_filename(".txt")
        assert result == "txt"
        
        result = sanitize_filename(".gitignore")
        assert result == "gitignore"
    
    def test_complex_filename_sanitization(self):
        """Test complex real-world filename scenarios."""
        # Scenario: Downloaded file with timestamp and special chars
        result = sanitize_filename("Report (Final Version) [2023-08-31].pdf")
        assert result == "Report_Final_Version_2023-08-31.pdf"
        
        # Scenario: File with multiple problematic elements
        result = sanitize_filename("...My: File\\Name<>?.txt")
        assert result == "My_FileName.txt"
    
    @pytest.mark.parametrize("filename,expected", [
        ("normal_file.txt", "normal_file.txt"),
        ("file with spaces.txt", "file_with_spaces.txt"),
        ("file@#$.txt", "file.txt"),
        ("file___multiple.txt", "file_multiple.txt"),
        (".hidden.txt", "hidden.txt"),
        ("", "unnamed_file"),
        ("only@#$symbols", "onlysymbols"),
        ("file.name.txt", "file.name.txt"),
    ])
    def test_parametrized_sanitization(self, filename, expected):
        """Parametrized test for various sanitization scenarios."""
        result = sanitize_filename(filename)
        assert result == expected
    
    def test_edge_case_max_length_equal_to_extension(self):
        """Test when max_length equals the extension length."""
        result = sanitize_filename("filename.txt", max_length=4)
        assert result == ".txt"  # Only extension remains
    
    def test_edge_case_max_length_smaller_than_extension(self):
        """Test when max_length is smaller than extension length."""
        result = sanitize_filename("filename.txt", max_length=2)
        # Function still attempts truncation even if max_length < extension length
        assert len(result) > 2  # Function doesn't handle this edge case gracefully
    
    def test_windows_reserved_names_handling(self):
        """Test handling of Windows reserved names in filenames."""
        # These shouldn't be completely reserved in this function,
        # but we test how they're sanitized
        result = sanitize_filename("CON.txt")
        assert result == "CON.txt"  # This function doesn't check reserved names
        
        result = sanitize_filename("PRN:test.txt") 
        assert result == "PRNtest.txt"  # Colon removed
    
    def test_very_long_extension(self):
        """Test handling of very long extensions."""
        filename = "short" + "." + "x" * 300
        result = sanitize_filename(filename, max_length=50)
        # The function doesn't handle very long extensions well
        # It preserves the entire extension regardless of max_length
        assert result.endswith("x" * 300)
        assert len(result) > 50
    
    def test_multiple_consecutive_operations(self):
        """Test that multiple sanitization operations are idempotent."""
        original = "My@File##Name  .txt"
        first_pass = sanitize_filename(original)
        second_pass = sanitize_filename(first_pass)
        
        assert first_pass == second_pass
        assert first_pass == "MyFileName_.txt"  # Space before extension becomes underscore
    
    def test_numeric_filenames(self):
        """Test handling of purely numeric filenames."""
        result = sanitize_filename("12345.txt")
        assert result == "12345.txt"
        
        result = sanitize_filename("0000.log")
        assert result == "0000.log"
    
    def test_single_character_handling(self):
        """Test handling of single character inputs."""
        result = sanitize_filename("a")
        assert result == "a"
        
        result = sanitize_filename("@")
        assert result == "unnamed_file"
        
        result = sanitize_filename(".")
        assert result == "unnamed_file"
    
    def test_whitespace_variations(self):
        """Test different types of whitespace handling."""
        result = sanitize_filename("file\tname.txt")
        assert result == "filename.txt"  # Tabs should be removed
        
        result = sanitize_filename("file\nname.txt") 
        assert result == "filename.txt"  # Newlines should be removed
    
    def test_boundary_max_length_values(self):
        """Test max_length boundary conditions."""
        # Test max_length of 1
        result = sanitize_filename("filename.txt", max_length=1)
        assert len(result) >= 1
        
        # Test max_length of 0
        result = sanitize_filename("filename.txt", max_length=0)
        assert result == "filename.txt"  # Function likely ignores max_length=0
    
    def test_special_dot_file_scenarios(self):
        """Test various dot file scenarios."""
        result = sanitize_filename(".file")
        assert result == "file"
        
        result = sanitize_filename("..file")
        assert result == "file"
        
        result = sanitize_filename("file.")
        assert result == "file."  # Trailing dots are preserved
        
        result = sanitize_filename("file..")
        assert result == "file."  # Multiple trailing dots become one