# File Upload Tests

This directory contains tests for the file upload functionality using pytest.

## Setup

First, install the test dependencies:

```bash
poetry install --with dev
```

This will install:
- pytest: Test framework

## Running Tests

### Run all tests
```bash
pytest
```

### Run only unit tests
```bash
pytest tests/test_upload_unit.py
```


### Run tests with coverage
```bash
pytest --cov=app --cov-report=html
```

## Test Structure

- `conftest.py`: Test fixtures and configuration
  - Flask app fixture for testing
  - Sample file fixtures (valid/invalid Parquet files)
  
- `test_upload_unit.py`: Unit tests using Flask test client
  - Tests the upload endpoint directly
  - No browser automation needed
  - Faster execution

- `test_file_upload.py`: Comprehensive tests
  - `TestFileUploadAPI`: API tests using Flask test client

## Test Scenarios Covered

1. **Valid file upload**: Tests successful upload of a valid Parquet file
2. **No file selected**: Tests error handling when no file is provided
3. **Invalid file type**: Tests rejection of non-Parquet files
4. **Corrupt Parquet file**: Tests handling of files with .parquet extension but invalid content
5. **Large file**: Tests file size limit enforcement
6. **HTMX functionality**: Verifies form submission without page refresh
7. **Form reset**: Ensures form is cleared after successful upload
8. **Loading indicator**: Tests UI feedback during upload

## Notes

- File size limit is set to 500MB in the application
- Uploaded files are saved with timestamps to avoid collisions