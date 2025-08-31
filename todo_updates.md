# Improvement Plan for utils_filename.py

## Overview
This document outlines suggested improvements for the `utils_filename.py` module based on analysis of the current implementation and comprehensive testing.

## 1. Fix Edge Cases in Truncation Logic
- **Issue**: When max_length is smaller than extension length, the function produces unexpected results
- **Solution**: Add validation to ensure minimum viable length and handle edge cases gracefully
- **Implementation**: Check if max_length < extension length and either preserve minimum name or raise warning

## 2. Add Windows Reserved Names Handling
- **Issue**: Function doesn't check for Windows reserved filenames (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
- **Solution**: Add a check for reserved names and append a suffix if needed
- **Implementation**: Create a set of reserved names and check against them (case-insensitive)

## 3. Improve Unicode Handling with Configuration
- **Current**: Unicode characters are preserved (via \w regex)
- **Enhancement**: Add parameter to control Unicode behavior (preserve/transliterate/remove)
- **Implementation**: Add `unicode_handling` parameter with options: 'preserve', 'ascii_only', 'transliterate'

## 4. Add Path Traversal Protection
- **Security**: Prevent directory traversal attacks
- **Solution**: Remove '../' sequences and validate no path separators remain
- **Implementation**: Strip path separators and parent directory references

## 5. Performance Optimizations
- **Issue**: Multiple regex operations could be combined
- **Solution**: Combine regex patterns where possible, compile patterns as constants
- **Implementation**: Pre-compile regex patterns at module level for reuse

## 6. Add Configurable Replacement Character
- **Enhancement**: Allow customizing what spaces/invalid chars are replaced with
- **Implementation**: Add `replacement_char` parameter (default='_')

## 7. Better Extension Handling
- **Issue**: Only handles single extension (file.tar.gz becomes file.tar + .gz)
- **Solution**: Add option to preserve compound extensions
- **Implementation**: Add `preserve_compound_extension` parameter

## 8. Add Validation Mode
- **Enhancement**: Option to validate without modifying
- **Implementation**: Add `validate_only` parameter that returns tuple (is_valid, issues)

## 9. Logging Support
- **Enhancement**: Add optional logging for debugging sanitization operations
- **Implementation**: Use Python logging module with configurable verbosity

## 10. Create Additional Utility Functions
- **New function**: `is_valid_filename()` - Check if filename is already valid
- **New function**: `suggest_filename()` - Generate unique filename if collision detected
- **New function**: `split_filename_safely()` - Better handling of compound extensions

## Implementation Priority
1. Fix truncation edge cases (Critical bug fix)
2. Add Windows reserved names handling (Security/compatibility)
3. Add path traversal protection (Security)
4. Performance optimizations (User experience)
5. Additional features (Enhancement)

## Proposed Code Structure
```python
# Module-level constants
WINDOWS_RESERVED_NAMES = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}

COMPILED_PATTERNS = {
    'invalid_chars': re.compile(r'[^\w\-_.]'),
    'windows_chars': re.compile(r'[<>:"/\\|?*]'),
    'duplicate_underscores': re.compile(r'_{2,}'),
    'duplicate_dots': re.compile(r'\.{2,}'),
    'path_traversal': re.compile(r'\.\.+[/\\]?')
}

def sanitize_filename(
    filename: str,
    max_length: Optional[int] = 200,
    unicode_handling: str = 'preserve',
    replacement_char: str = '_',
    check_reserved: bool = True,
    preserve_compound_extension: bool = False,
    validate_only: bool = False
) -> Union[str, Tuple[bool, List[str]]]:
    """Enhanced filename sanitization with configurable options."""
    # Implementation with all improvements
    
def is_valid_filename(filename: str, strict: bool = False) -> bool:
    """Check if filename is already valid without modification."""
    # Validation without modification
    
def suggest_unique_filename(base_filename: str, existing_files: List[str]) -> str:
    """Generate unique filename to avoid collisions."""
    # Generate unique filename

def split_filename_safely(filename: str, preserve_compound: bool = True) -> Tuple[str, str]:
    """Better handling of compound extensions like .tar.gz"""
    # Enhanced extension splitting
```

## Current Usage Context
The module is currently used in:
- `modules/utils_download.py` - For sanitizing ZIP file names during game download operations
- Testing shows it's primarily used for creating safe filenames for ZIP archives

## Backward Compatibility
All proposed changes should maintain backward compatibility by using default parameter values that preserve current behavior.

## Testing Requirements
- Update existing tests in `test_utils_filename.py` to cover new functionality
- Add tests for Windows reserved names
- Add tests for path traversal protection
- Add performance benchmarks for regex optimizations
- Test Unicode handling options
- Test compound extension handling

## Security Considerations
- Path traversal protection is critical for security
- Windows reserved names can cause issues on Windows systems
- Unicode handling needs careful consideration for cross-platform compatibility