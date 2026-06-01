import pytest
import sqlite3
import uuid
import json
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
    try:
        test_db.unlink(missing_ok=True)
    except PermissionError:
        pass


def insert_job(job_id="job1", domain="stripe.com", title="QA Engineer", user_id="shrawan"):
    from agent import db
    db.execute(
        """INSERT INTO jobs (id, title, company, company_domain, career_page_url, source, scraped_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, title, "Stripe", domain, "https://stripe.com/jobs/1",
         "wellfound", datetime.utcnow().isoformat(), user_id),
    )


def insert_application(job_id="job1", user_id="shrawan"):
    from agent import db
    db.execute(
        "INSERT INTO applications (id, job_id, user_id, applied_at) VALUES (?, ?, ?, DATETIME('now'))",
        (str(uuid.uuid4()), job_id, user_id),
    )


class TestNormaliseText:
    def test_lowercases(self):
        from agent.dedup import normalise_text
        assert normalise_text("QA Engineer") == "qa engineer"

    def test_strips_whitespace(self):
        from agent.dedup import normalise_text
        assert normalise_text("  QA  Engineer  ") == "qa engineer"

    def test_collapses_spaces(self):
        from agent.dedup import normalise_text
        assert normalise_text("QA   Engineer") == "qa engineer"


class TestMakeJobId:
    def test_returns_hex_string(self):
        from agent.dedup import make_job_id
        result = make_job_id("stripe.com", "QA Engineer")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_inputs_same_hash(self):
        from agent.dedup import make_job_id
        assert make_job_id("stripe.com", "QA Engineer") == make_job_id("stripe.com", "QA Engineer")

    def test_different_inputs_different_hash(self):
        from agent.dedup import make_job_id
        assert make_job_id("stripe.com", "QA Engineer") != make_job_id("stripe.com", "SDET")

    def test_case_insensitive(self):
        from agent.dedup import make_job_id
        assert make_job_id("Stripe.com", "QA ENGINEER") == make_job_id("stripe.com", "qa engineer")


class TestMakeFieldHash:
    def test_returns_hex_string(self):
        from agent.dedup import make_field_hash
        result = make_field_hash("Expected salary")
        assert len(result) == 64

    def test_case_insensitive(self):
        from agent.dedup import make_field_hash
        assert make_field_hash("Expected Salary") == make_field_hash("expected salary")


class TestIsDuplicateJob:
    def test_new_job_is_not_duplicate(self):
        from agent.dedup import is_duplicate_job
        assert is_duplicate_job("nonexistent_id") is False

    def test_existing_job_is_duplicate(self):
        from agent.dedup import is_duplicate_job
        insert_job("existing_job")
        assert is_duplicate_job("existing_job") is True


class TestIsCompanyBlocked:
    def test_unknown_company_not_blocked(self):
        from agent.dedup import is_company_blocked
        assert is_company_blocked("newco.com", "shrawan") is False

    def test_blocklisted_company_is_blocked(self):
        from agent import db
        from agent.dedup import is_company_blocked
        db.execute(
            "INSERT INTO companies_seen (domain, user_id, first_applied_at, blocklist) VALUES (?, ?, DATETIME('now'), 1)",
            ("tcs.com", "shrawan"),
        )
        assert is_company_blocked("tcs.com", "shrawan") is True

    def test_cooldown_active_is_blocked(self):
        from agent import db
        from agent.dedup import is_company_blocked
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        db.execute(
            "INSERT INTO companies_seen (domain, user_id, first_applied_at, cooldown_until) VALUES (?, ?, DATETIME('now'), ?)",
            ("stripe.com", "shrawan", future),
        )
        assert is_company_blocked("stripe.com", "shrawan") is True

    def test_expired_cooldown_not_blocked(self):
        from agent import db
        from agent.dedup import is_company_blocked
        past = (datetime.utcnow() - timedelta(days=1)).isoformat()
        db.execute(
            "INSERT INTO companies_seen (domain, user_id, first_applied_at, cooldown_until) VALUES (?, ?, DATETIME('now'), ?)",
            ("notion.so", "shrawan", past),
        )
        assert is_company_blocked("notion.so", "shrawan") is False


class TestIsDailyCapReached:
    def test_zero_applications_cap_not_reached(self):
        from agent.dedup import is_daily_cap_reached
        assert is_daily_cap_reached("shrawan", 12) is False

    def test_at_cap_is_reached(self):
        from agent import db
        from agent.dedup import is_daily_cap_reached
        for i in range(12):
            insert_job(f"job_{i}", user_id="shrawan")
            insert_application(f"job_{i}", user_id="shrawan")
        assert is_daily_cap_reached("shrawan", 12) is True

    def test_below_cap_not_reached(self):
        from agent import db
        from agent.dedup import is_daily_cap_reached
        for i in range(5):
            insert_job(f"jobx_{i}", user_id="shrawan")
            insert_application(f"jobx_{i}", user_id="shrawan")
        assert is_daily_cap_reached("shrawan", 12) is False


class TestIsBlocklistedByConfig:
    def test_domain_in_blocklist(self):
        from agent.dedup import is_blocklisted_by_config
        assert is_blocklisted_by_config("tcs.com", ["tcs.com", "infosys.com"]) is True

    def test_domain_not_in_blocklist(self):
        from agent.dedup import is_blocklisted_by_config
        assert is_blocklisted_by_config("stripe.com", ["tcs.com", "infosys.com"]) is False

    def test_case_insensitive(self):
        from agent.dedup import is_blocklisted_by_config
        assert is_blocklisted_by_config("TCS.COM", ["tcs.com"]) is True

    def test_empty_blocklist(self):
        from agent.dedup import is_blocklisted_by_config
        assert is_blocklisted_by_config("stripe.com", []) is False


class TestPassesAllChecks:
    def test_new_job_passes(self):
        from agent.dedup import passes_all_checks, make_job_id
        job_id = make_job_id("stripe.com", "QA Engineer")
        passed, reason = passes_all_checks(job_id, "stripe.com", "shrawan", 12, [])
        assert passed is True
        assert reason == "ok"

    def test_fails_config_blocklist(self):
        from agent.dedup import passes_all_checks, make_job_id
        job_id = make_job_id("tcs.com", "QA Engineer")
        passed, reason = passes_all_checks(job_id, "tcs.com", "shrawan", 12, ["tcs.com"])
        assert passed is False
        assert reason == "company_in_config_blocklist"

    def test_fails_duplicate_job(self):
        from agent.dedup import passes_all_checks
        insert_job("dup_job", domain="stripe.com")
        passed, reason = passes_all_checks("dup_job", "stripe.com", "shrawan", 12, [])
        assert passed is False
        assert reason == "duplicate_job_hash"

    def test_fails_company_blocked(self):
        from agent import db
        from agent.dedup import passes_all_checks, make_job_id
        future = (datetime.utcnow() + timedelta(days=30)).isoformat()
        db.execute(
            "INSERT INTO companies_seen (domain, user_id, first_applied_at, blocklist) VALUES (?, ?, DATETIME('now'), 1)",
            ("blocked.com", "shrawan"),
        )
        job_id = make_job_id("blocked.com", "QA Engineer")
        passed, reason = passes_all_checks(job_id, "blocked.com", "shrawan", 12, [])
        assert passed is False
        assert reason == "company_blocked_or_cooldown"

    def test_fails_daily_cap(self):
        from agent.dedup import passes_all_checks, make_job_id
        for i in range(12):
            insert_job(f"cap_job_{i}", domain=f"co{i}.com")
            insert_application(f"cap_job_{i}")
        job_id = make_job_id("newco.com", "QA Engineer")
        passed, reason = passes_all_checks(job_id, "newco.com", "shrawan", 12, [])
        assert passed is False
        assert reason == "daily_cap_reached"


class TestRecordApplication:
    def test_inserts_company_seen(self):
        from agent import db
        from agent.dedup import record_application
        record_application("stripe.com", "Stripe", "shrawan", cooldown_days=90)
        row = db.fetchone(
            "SELECT * FROM companies_seen WHERE domain = ? AND user_id = ?",
            ("stripe.com", "shrawan"),
        )
        assert row is not None
        assert row["company_name"] == "Stripe"

    def test_does_not_duplicate_on_second_call(self):
        from agent import db
        from agent.dedup import record_application
        record_application("stripe.com", "Stripe", "shrawan")
        record_application("stripe.com", "Stripe", "shrawan")
        rows = db.fetchall(
            "SELECT * FROM companies_seen WHERE domain = ? AND user_id = ?",
            ("stripe.com", "shrawan"),
        )
        assert len(rows) == 1


class TestRecordUnknownField:
    def test_inserts_new_field(self):
        from agent import db
        from agent.dedup import record_unknown_field
        record_unknown_field("Expected salary", "stripe.com", "shrawan")
        rows = db.fetchall(
            "SELECT * FROM unknown_fields WHERE user_id = ?", ("shrawan",)
        )
        assert len(rows) == 1
        assert rows[0]["label"] == "Expected salary"
        assert rows[0]["answered"] == 0

    def test_increments_seen_count_on_second_domain(self):
        from agent import db
        from agent.dedup import record_unknown_field
        record_unknown_field("Expected salary", "stripe.com", "shrawan")
        record_unknown_field("Expected salary", "notion.so", "shrawan")
        row = db.fetchone(
            "SELECT * FROM unknown_fields WHERE user_id = ?", ("shrawan",)
        )
        assert row["seen_count"] == 2
        domains = json.loads(row["seen_on_domains"])
        assert "stripe.com" in domains
        assert "notion.so" in domains

    def test_same_domain_does_not_duplicate_domain(self):
        from agent import db
        from agent.dedup import record_unknown_field
        record_unknown_field("Expected salary", "stripe.com", "shrawan")
        record_unknown_field("Expected salary", "stripe.com", "shrawan")
        row = db.fetchone(
            "SELECT * FROM unknown_fields WHERE user_id = ?", ("shrawan",)
        )
        domains = json.loads(row["seen_on_domains"])
        assert domains.count("stripe.com") == 1
