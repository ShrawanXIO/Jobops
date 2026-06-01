import pytest
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timedelta

SCHEMA_PATH = Path("data/schema.sql")


@pytest.fixture(autouse=True)
def use_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "jobs.db"
    import agent.db as db_module
    monkeypatch.setattr(db_module, "DB_PATH", test_db)
    monkeypatch.setattr(db_module, "SCHEMA_PATH", SCHEMA_PATH)
    db_module.init_db()
    yield
    # Close all connections before attempting delete on Windows
    try:
        conn = sqlite3.connect(str(test_db))
        conn.close()
    except Exception:
        pass
    try:
        test_db.unlink(missing_ok=True)
    except PermissionError:
        pass  # Windows may still hold the file — tmp_path cleanup handles it


def test_init_db_creates_file():
    import agent.db as db
    assert db.DB_PATH.exists()


def test_init_db_creates_all_tables():
    import agent.db as db
    tables = db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = [t["name"] for t in tables]
    assert "jobs" in names
    assert "applications" in names
    assert "companies_seen" in names
    assert "outreach" in names
    assert "unknown_fields" in names
    assert "run_logs" in names


def test_execute_inserts_row():
    import agent.db as db
    db.execute(
        """INSERT INTO jobs (id, title, company, career_page_url, source, scraped_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("abc123", "QA Engineer", "Stripe", "https://stripe.com/jobs/1",
         "wellfound", datetime.utcnow().isoformat(), "shrawan"),
    )
    row = db.fetchone("SELECT * FROM jobs WHERE id = ?", ("abc123",))
    assert row is not None
    assert row["title"] == "QA Engineer"
    assert row["company"] == "Stripe"


def test_fetchall_returns_multiple_rows():
    import agent.db as db
    for i in range(3):
        db.execute(
            """INSERT INTO jobs (id, title, company, career_page_url, source, scraped_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (f"id{i}", f"Role {i}", "Acme", f"https://acme.com/jobs/{i}",
             "wellfound", datetime.utcnow().isoformat(), "shrawan"),
        )
    rows = db.fetchall("SELECT * FROM jobs WHERE user_id = ?", ("shrawan",))
    assert len(rows) == 3


def test_fetchone_returns_none_for_missing():
    import agent.db as db
    row = db.fetchone("SELECT * FROM jobs WHERE id = ?", ("nonexistent",))
    assert row is None


def test_job_exists_true():
    import agent.db as db
    db.execute(
        """INSERT INTO jobs (id, title, company, career_page_url, source, scraped_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("exists1", "SDET", "Notion", "https://notion.so/jobs/1",
         "linkedin", datetime.utcnow().isoformat(), "shrawan"),
    )
    assert db.job_exists("exists1") is True


def test_job_exists_false():
    import agent.db as db
    assert db.job_exists("does_not_exist") is False


def test_today_application_count_zero():
    import agent.db as db
    assert db.today_application_count("shrawan") == 0


def test_today_application_count_increments():
    import agent.db as db
    db.execute(
        """INSERT INTO jobs (id, title, company, career_page_url, source, scraped_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("job1", "QA Lead", "Linear", "https://linear.app/jobs/1",
         "wellfound", datetime.utcnow().isoformat(), "shrawan"),
    )
    db.execute(
        """INSERT INTO applications (id, job_id, user_id, applied_at)
           VALUES (?, ?, ?, DATETIME('now'))""",
        (str(uuid.uuid4()), "job1", "shrawan"),
    )
    assert db.today_application_count("shrawan") == 1


def test_company_is_blocked_blocklist():
    import agent.db as db
    db.execute(
        """INSERT INTO companies_seen (domain, user_id, first_applied_at, blocklist)
           VALUES (?, ?, DATETIME('now'), 1)""",
        ("tcs.com", "shrawan"),
    )
    assert db.company_is_blocked("tcs.com", "shrawan") is True


def test_company_is_blocked_cooldown():
    import agent.db as db
    future = (datetime.utcnow() + timedelta(days=30)).isoformat()
    db.execute(
        """INSERT INTO companies_seen (domain, user_id, first_applied_at, cooldown_until)
           VALUES (?, ?, DATETIME('now'), ?)""",
        ("stripe.com", "shrawan", future),
    )
    assert db.company_is_blocked("stripe.com", "shrawan") is True


def test_company_is_not_blocked_expired_cooldown():
    import agent.db as db
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    db.execute(
        """INSERT INTO companies_seen (domain, user_id, first_applied_at, cooldown_until)
           VALUES (?, ?, DATETIME('now'), ?)""",
        ("notion.so", "shrawan", past),
    )
    assert db.company_is_blocked("notion.so", "shrawan") is False


def test_company_not_in_db_is_not_blocked():
    import agent.db as db
    assert db.company_is_blocked("newcompany.com", "shrawan") is False


def test_foreign_keys_enforced():
    import agent.db as db
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO applications (id, job_id, user_id, applied_at)
               VALUES (?, ?, ?, DATETIME('now'))""",
            ("app1", "nonexistent_job_id", "shrawan"),
        )