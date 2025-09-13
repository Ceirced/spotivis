import os
import tempfile

import pytest

from app import create_app
from app.models import db


@pytest.fixture(scope="function")
def app():
    """Create and configure a test Flask application."""
    # Set test environment variables
    os.environ["APP_SETTINGS"] = "config.TestingConfig"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["FLASK_ENV"] = "testing"
    os.environ["REDIS_URL"] = "redis://localhost:6379"
    os.environ["SECRET_KEY"] = "test-secret-key"

    app = create_app()

    # Override config for testing
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for testing
            "SERVER_NAME": "localhost:5000",
            "SECURITY_LOGIN_WITHOUT_CONFIRMATION": True,
            "SECURITY_EMAIL_VALIDATOR_ARGS": {"check_deliverability": False},
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test runner for the Flask application."""
    return app.test_cli_runner()


@pytest.fixture
def authenticated_client(app, client):
    """Create an authenticated test client."""
    from flask_security import hash_password

    from app.extensions.security import user_datastore

    with app.app_context():
        # Create a test user with username (required by the system)
        user_datastore.create_user(
            email="test@example.com",
            username="testuser",
            password=hash_password("password"),
            active=True,
            confirmed_at=db.func.now(),
        )
        db.session.commit()

        # Log in the user
        client.post(
            "/login",
            data={"email": "test@example.com", "password": "password"},
            follow_redirects=True,
        )

        yield client


@pytest.fixture
def sample_parquet_file():
    """Create a sample Parquet file for testing."""
    from datetime import datetime

    import pyarrow as pa
    import pyarrow.parquet as pq

    # Create a temporary file
    fd, path = tempfile.mkstemp(suffix=".parquet")

    # Create sample data with required columns: isrc, playlist_id, thu_date
    data = {
        "isrc": ["US1234567890", "US2345678901", "US3456789012"],
        "playlist_id": ["playlist_1", "playlist_2", "playlist_1"],
        "thu_date": [datetime.now().isoformat()] * 3,
        "track_name": ["Song 1", "Song 2", "Song 3"],
        "artist_name": ["Artist 1", "Artist 2", "Artist 3"],
        "play_count": [100, 200, 150],
    }

    # Write to Parquet file
    table = pa.table(data)
    pq.write_table(table, path)

    yield path

    # Clean up
    os.close(fd)
    os.unlink(path)


@pytest.fixture
def invalid_file():
    """Create an invalid file (not Parquet) for testing."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write("This is not a parquet file")

    yield path

    # Clean up
    os.unlink(path)


@pytest.fixture
def large_file():
    """Create a large file for testing file size limits."""
    fd, path = tempfile.mkstemp(suffix=".parquet")

    # Create a file larger than MAX_FILE_SIZE (500MB)
    # For testing, we'll create a smaller file but mock the size check
    with os.fdopen(fd, "wb") as f:
        # Write 1MB of data
        f.write(b"0" * (1024 * 1024))

    yield path

    # Clean up
    os.unlink(path)
