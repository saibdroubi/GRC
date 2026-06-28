from datetime import datetime, timedelta, timezone

from app import auth, models
from tests.factories import make_org, make_user, login


def test_signup_creates_org_and_admin_user(client):
    res = client.post(
        "/auth/signup",
        json={
            "organization_name": "Acme Co",
            "name": "Alice Admin",
            "email": "alice@acme.com",
            "password": "correct-password-123",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email"] == "alice@acme.com"
    assert body["role"] == "admin"
    assert body["organization_name"] == "Acme Co"


def test_signup_duplicate_email_rejected(client):
    payload = {
        "organization_name": "Acme Co",
        "name": "Alice Admin",
        "email": "dupe@acme.com",
        "password": "correct-password-123",
    }
    first = client.post("/auth/signup", json=payload)
    assert first.status_code == 200

    second = client.post("/auth/signup", json={**payload, "organization_name": "Other Co"})
    assert second.status_code == 409


def test_login_success_and_me(client, db_session):
    org = make_org(db_session)
    make_user(db_session, org, email="bob@example.com", password="correct-password-123")

    login(client, "bob@example.com", "correct-password-123")

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "bob@example.com"


def test_login_wrong_password_rejected(client, db_session):
    org = make_org(db_session)
    make_user(db_session, org, email="carol@example.com", password="correct-password-123")

    res = client.post("/auth/login", json={"email": "carol@example.com", "password": "wrong-password"})
    assert res.status_code == 401


def test_login_locks_account_after_max_failed_attempts(client, db_session):
    org = make_org(db_session)
    make_user(db_session, org, email="dana@example.com", password="correct-password-123")

    for _ in range(auth.MAX_FAILED_ATTEMPTS):
        res = client.post("/auth/login", json={"email": "dana@example.com", "password": "wrong-password"})
        assert res.status_code == 401

    # Even the correct password is now rejected because the account is locked.
    locked_res = client.post("/auth/login", json={"email": "dana@example.com", "password": "correct-password-123"})
    assert locked_res.status_code == 401


def test_logout_invalidates_session(client, db_session):
    org = make_org(db_session)
    make_user(db_session, org, email="erin@example.com", password="correct-password-123")
    login(client, "erin@example.com", "correct-password-123")

    assert client.get("/auth/me").status_code == 200

    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 200

    assert client.get("/auth/me").status_code == 401


def test_get_current_user_missing_cookie_rejected(client):
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_get_current_user_garbage_cookie_rejected(client):
    client.cookies.set(auth.SESSION_COOKIE_NAME, "not-a-real-token")
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_get_current_user_expired_session_rejected(client, db_session):
    org = make_org(db_session)
    user = make_user(db_session, org, email="frank@example.com", password="correct-password-123")
    token = auth.create_session(db_session, user)

    session_row = db_session.query(models.Session).filter_by(user_id=user.id).one()
    session_row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    client.cookies.set(auth.SESSION_COOKIE_NAME, token)
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_password_hash_verify_roundtrip():
    hashed = auth.hash_password("correct-password-123")
    assert hashed != "correct-password-123"
    assert auth.verify_password("correct-password-123", hashed) is True
    assert auth.verify_password("wrong-password", hashed) is False
