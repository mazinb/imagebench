# Security Fixes

This document outlines the critical security vulnerabilities that have been fixed in this commit.

## Fixed Vulnerabilities

### 1. Shell Injection (CRITICAL)

**Location**: `src/imagebench/run.py:generate_cmd()`

**Issue**: The function used `subprocess.run(cmd, shell=True)` where `cmd` comes from user input via the `--cmd` argument. This allowed arbitrary command execution.

**Fix**: 
- Added timeout to prevent hanging processes
- Added output capture for better error reporting
- Added comment warning users that --cmd should be from trusted sources
- Sanitized environment variables to remove null bytes and limit length
- Added path validation to prevent path traversal attacks

**Note**: The shell=True is still present because the tool's design requires executing user shell commands. Users MUST ensure their --cmd argument is trusted. For production use, consider refactoring to use a safer approach.

### 2. Path Traversal Vulnerabilities

**Locations**: Multiple files

**Issue**: File paths from user input were not validated, allowing potential path traversal attacks.

**Fixes**:
- `run.py`: Validate output paths in `generate_cmd()` and `generate_openai()`
- `cli.py`: Validate run_id, output directories, and image paths
- `prompts.py`: Validate destination paths and filenames in `write_prompts()`

### 3. Resource Exhaustion

**Locations**: Multiple HTTP and file operations

**Issue**: No limits on file sizes or HTTP response sizes, allowing potential DoS via memory exhaustion.

**Fixes**:
- Added 20MB limit on image files for VLM scoring
- Added 50MB limit on decoded base64 images
- Added 100MB limit on HTTP responses for image generation
- Added 1MB limit on VLM scoring responses
- Added 10MB limit on prompt files
- Added 50MB limit on results JSON files
- Added response size limits in `_http_json()`

### 4. Missing Input Validation

**Locations**: Multiple functions

**Issue**: User inputs were not properly validated.

**Fixes**:
- Validate URL schemes (http:// or https:// only)
- Validate image dimensions (64-4096 pixels)
- Limit prompt text length (10,000 characters)
- Validate prompt file format and required fields
- Validate results file format
- Sanitize prompt IDs for filenames

### 5. Inadequate Error Handling

**Locations**: HTTP requests and JSON parsing

**Issue**: Poor error messages and missing try-catch blocks made debugging difficult and could expose sensitive information.

**Fixes**:
- Added comprehensive error handling for HTTP requests
- Added JSON parsing error handling
- Limited error message lengths to prevent information leakage
- Added validation of response formats

### 6. Environment Variable Injection

**Location**: `run.py:generate_cmd()`

**Issue**: Prompt data was passed directly to environment variables without sanitization.

**Fix**: Added `sanitize_env_value()` function to remove null bytes and limit string lengths.

## Recommendations

1. **Use Trusted Commands Only**: The `--cmd` parameter should only accept commands from trusted sources. Consider implementing a whitelist of allowed commands.

2. **Regular Security Audits**: Conduct regular security reviews of the codebase.

3. **Dependency Updates**: Keep all dependencies up-to-date to patch known vulnerabilities.

4. **Rate Limiting**: Consider adding rate limiting for HTTP requests to prevent abuse.

5. **Authentication**: If using with public APIs, ensure proper authentication is in place.

6. **Logging**: Add security logging for suspicious activities.

## Security Contact

For security issues, please follow responsible disclosure practices.
