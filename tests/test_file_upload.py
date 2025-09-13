import io


class TestFileUploadAPI:
    """Test file upload functionality using Flask test client (API tests)."""

    def test_upload_endpoint_exists(self, authenticated_client):
        """Test that the upload endpoint exists."""
        response = authenticated_client.post("/first/upload")
        # Should get 422 (no file) not 404
        assert response.status_code == 422

    def test_home_page_shows_upload_form(self, authenticated_client):
        """Test that the home page displays the upload form."""
        response = authenticated_client.get("/first/")
        assert response.status_code == 200
        assert b"Upload Your Spotify Data" in response.data
        assert b'name="file"' in response.data
        assert b'accept=".parquet"' in response.data

    def test_max_file_size_displayed(self, authenticated_client):
        """Test that the maximum file size is correctly displayed."""
        response = authenticated_client.get("/first/")
        assert response.status_code == 200
        # The backend sets MAX_FILE_SIZE to 500MB
        assert b"Max size 500MB" in response.data

    def test_upload_valid_parquet_file(self, authenticated_client, sample_parquet_file):
        """Test uploading a valid Parquet file."""
        with open(sample_parquet_file, "rb") as f:
            data = {"file": (f, "test_data.parquet", "application/octet-stream")}
            response = authenticated_client.post(
                "/first/upload", data=data, content_type="multipart/form-data"
            )

        assert response.status_code == 200
        assert b"File uploaded successfully" in response.data
        assert b"test_data.parquet" in response.data

    def test_upload_no_file(self, authenticated_client):
        """Test upload endpoint with no file."""
        response = authenticated_client.post("/first/upload", data={})

        assert response.status_code == 422
        assert b"No file part" in response.data

    def test_upload_empty_filename(self, authenticated_client):
        """Test upload with empty filename."""
        data = {"file": (io.BytesIO(b""), "", "application/octet-stream")}
        response = authenticated_client.post(
            "/first/upload", data=data, content_type="multipart/form-data"
        )

        assert response.status_code == 422
        assert b"No selected file" in response.data

    def test_upload_invalid_file_type(self, authenticated_client, invalid_file):
        """Test uploading a non-Parquet file."""
        with open(invalid_file, "rb") as f:
            data = {"file": (f, "test.txt", "text/plain")}
            response = authenticated_client.post(
                "/first/upload", data=data, content_type="multipart/form-data"
            )

        assert response.status_code == 422
        assert b"Invalid file type" in response.data

    def test_upload_invalid_parquet_content(self, authenticated_client):
        """Test uploading a file with .parquet extension but invalid content."""
        # Create a fake .parquet file with invalid content
        fake_parquet = io.BytesIO(b"This is not a valid parquet file")
        data = {"file": (fake_parquet, "fake.parquet", "application/octet-stream")}
        response = authenticated_client.post(
            "/first/upload", data=data, content_type="multipart/form-data"
        )

        assert response.status_code == 422
        assert b"Invalid parquet file" in response.data

    def test_upload_large_file(self, authenticated_client, app):
        """Test uploading a file larger than MAX_FILE_SIZE."""
        # For testing purposes, temporarily reduce MAX_FILE_SIZE
        from app.main.first import routes

        original_max_size = routes.MAX_FILE_SIZE
        routes.MAX_FILE_SIZE = 1024  # 1KB for testing

        try:
            # Create a file larger than our test limit
            large_data = io.BytesIO(b"0" * 2048)  # 2KB, larger than our 1KB limit
            data = {"file": (large_data, "large.parquet", "application/octet-stream")}
            response = authenticated_client.post(
                "/first/upload", data=data, content_type="multipart/form-data"
            )

            assert response.status_code == 422
            assert b"File too large" in response.data

        finally:
            # Restore original MAX_FILE_SIZE
            routes.MAX_FILE_SIZE = original_max_size

    def test_files_endpoint_exists(self, authenticated_client):
        """Test files endpoint responds correctly."""
        response = authenticated_client.get("/first/files")
        assert response.status_code == 200
        assert b"Uploaded Files" in response.data

    def test_files_endpoint_with_files(self, authenticated_client, sample_parquet_file):
        """Test files endpoint after uploading a file."""
        # First upload a file
        with open(sample_parquet_file, "rb") as f:
            data = {"file": (f, "test_data.parquet", "application/octet-stream")}
            upload_response = authenticated_client.post(
                "/first/upload", data=data, content_type="multipart/form-data"
            )
        assert upload_response.status_code == 200

        # Then check files endpoint
        response = authenticated_client.get("/first/files")
        assert response.status_code == 200
        assert b"Uploaded Files" in response.data
        assert b"test_data.parquet" in response.data

    def test_upload_time_parsing(self, authenticated_client, sample_parquet_file):
        """Test that upload time is correctly parsed and displayed."""
        from datetime import datetime

        # Upload a file
        with open(sample_parquet_file, "rb") as f:
            data = {"file": (f, "test_upload_time.parquet", "application/octet-stream")}
            upload_response = authenticated_client.post(
                "/first/upload", data=data, content_type="multipart/form-data"
            )
        assert upload_response.status_code == 200

        # Check files endpoint shows proper time
        response = authenticated_client.get("/first/files")
        assert response.status_code == 200

        # The upload time should not be "Unknown"
        assert b"Unknown" not in response.data or response.data.count(
            b"Unknown"
        ) < response.data.count(b"<tr>")

        # Check that we have a proper timestamp format (YYYY-MM-DD HH:MM:SS)
        response_text = response.data.decode()
        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        timestamps = re.findall(timestamp_pattern, response_text)

        # Should have at least one properly formatted timestamp
        assert len(timestamps) > 0, (
            f"No proper timestamps found in response: {response_text[:500]}..."
        )

        # The timestamp should be recent (within last few minutes)
        latest_timestamp = timestamps[0]  # First one should be the most recent
        parsed_time = datetime.strptime(latest_timestamp, "%Y-%m-%d %H:%M:%S")
        current_time = datetime.now()
        time_diff = (current_time - parsed_time).total_seconds()

        # Should be uploaded within the last 60 seconds
        assert time_diff < 60, (
            f"Upload time {latest_timestamp} is not recent enough (diff: {time_diff}s)"
        )
