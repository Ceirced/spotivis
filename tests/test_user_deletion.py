import os

import pytest

from app import create_app, db
from app.models import FriendRequest, User


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    # Set required environment variables for testing
    os.environ["APP_SETTINGS"] = "config.TestingConfig"
    os.environ["APP_NAME"] = "Test App"

    app = create_app()
    app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()


def test_user_deletion_cascades_friend_requests(app):
    """Test that deleting a user also deletes associated friend requests."""
    with app.app_context():
        from app.extensions.security import user_datastore

        # Create two users using Flask-Security's user_datastore
        user1 = user_datastore.create_user(
            email="user1@test.com",
            username="user1",
            password="password123",
            active=True,
        )
        user2 = user_datastore.create_user(
            email="user2@test.com",
            username="user2",
            password="password123",
            active=True,
        )
        db.session.commit()

        # Get user IDs
        user1_id = user1.id
        user2_id = user2.id

        # Create a friend request from user1 to user2
        friend_request = FriendRequest(sender_id=user1_id, receiver_id=user2_id)
        db.session.add(friend_request)
        db.session.commit()

        request_id = friend_request.request_id

        # Verify friend request exists
        assert db.session.get(FriendRequest, request_id) is not None

        # Delete user1
        db.session.delete(user1)
        db.session.commit()

        # Verify user1 is deleted
        assert db.session.get(User, user1_id) is None

        # Verify friend request is also deleted (CASCADE)
        assert db.session.get(FriendRequest, request_id) is None

        # Verify user2 still exists
        assert db.session.get(User, user2_id) is not None


def test_user_deletion_cascades_both_sender_and_receiver(app):
    """Test that deleting a user deletes friend requests where they are sender OR receiver."""
    with app.app_context():
        from app.extensions.security import user_datastore

        # Create three users using Flask-Security's user_datastore
        user1 = user_datastore.create_user(
            email="user1@test.com",
            username="user1",
            password="password123",
            active=True,
        )
        user2 = user_datastore.create_user(
            email="user2@test.com",
            username="user2",
            password="password123",
            active=True,
        )
        user3 = user_datastore.create_user(
            email="user3@test.com",
            username="user3",
            password="password123",
            active=True,
        )
        db.session.commit()

        user2_id = user2.id

        # Create friend requests:
        # - user1 -> user2 (user2 is receiver)
        # - user2 -> user3 (user2 is sender)
        request1 = FriendRequest(sender_id=user1.id, receiver_id=user2_id)
        request2 = FriendRequest(sender_id=user2_id, receiver_id=user3.id)

        db.session.add_all([request1, request2])
        db.session.commit()

        request1_id = request1.request_id
        request2_id = request2.request_id

        # Verify both friend requests exist
        assert db.session.get(FriendRequest, request1_id) is not None
        assert db.session.get(FriendRequest, request2_id) is not None

        # Delete user2
        db.session.delete(user2)
        db.session.commit()

        # Verify user2 is deleted
        assert db.session.get(User, user2_id) is None

        # Verify both friend requests are deleted (CASCADE)
        assert db.session.get(FriendRequest, request1_id) is None
        assert db.session.get(FriendRequest, request2_id) is None

        # Verify user1 and user3 still exist
        assert db.session.get(User, user1.id) is not None
        assert db.session.get(User, user3.id) is not None
