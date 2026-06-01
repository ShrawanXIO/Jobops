import hashlib
import re
from datetime import datetime, timedelta
from agent import db


def normalise_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def make_job_id(company_domain: str, title: str) -> str:
    normalised = normalise_text(company_domain) + "|" + normalise_text(title)
    return hashlib.sha256(normalised.encode()).hexdigest()


def make_field_hash(label: str) -> str:
    return hashlib.sha256(normalise_text(label).encode()).hexdigest()


def is_duplicate_job(job_id: str) -> bool:
    return db.job_exists(job_id)


def is_company_blocked(domain: str, user_id: str) -> bool:
    return db.company_is_blocked(domain, user_id)


def is_daily_cap_reached(user_id: str, cap: int) -> bool:
    return db.today_application_count(user_id) >= cap


def is_blocklisted_by_config(domain: str, blocklist_domains: list[str]) -> bool:
    return domain.lower() in [d.lower() for d in blocklist_domains]


def passes_all_checks(
    job_id: str,
    company_domain: str,
    user_id: str,
    daily_cap: int,
    blocklist_domains: list[str],
) -> tuple[bool, str]:
    if is_blocklisted_by_config(company_domain, blocklist_domains):
        return False, "company_in_config_blocklist"

    if is_duplicate_job(job_id):
        return False, "duplicate_job_hash"

    if is_company_blocked(company_domain, user_id):
        return False, "company_blocked_or_cooldown"

    if is_daily_cap_reached(user_id, daily_cap):
        return False, "daily_cap_reached"

    return True, "ok"


def record_application(
    company_domain: str,
    company_name: str,
    user_id: str,
    cooldown_days: int = 90,
) -> None:
    cooldown_until = (datetime.utcnow() + timedelta(days=cooldown_days)).isoformat()
    db.execute(
        """
        INSERT INTO companies_seen (domain, user_id, company_name, first_applied_at, cooldown_until)
        VALUES (?, ?, ?, DATETIME('now'), ?)
        ON CONFLICT(domain, user_id) DO NOTHING
        """,
        (company_domain, user_id, company_name, cooldown_until),
    )


def record_unknown_field(label: str, domain: str, user_id: str) -> None:
    field_hash = make_field_hash(label)
    now = datetime.utcnow().isoformat()
    existing = db.fetchone(
        "SELECT field_hash, seen_on_domains, seen_count FROM unknown_fields WHERE field_hash = ? AND user_id = ?",
        (field_hash, user_id),
    )
    if existing:
        import json
        domains = json.loads(existing["seen_on_domains"])
        if domain not in domains:
            domains.append(domain)
        db.execute(
            """
            UPDATE unknown_fields
            SET seen_on_domains = ?, seen_count = seen_count + 1, updated_at = ?
            WHERE field_hash = ? AND user_id = ?
            """,
            (json.dumps(domains), now, field_hash, user_id),
        )
    else:
        import json
        db.execute(
            """
            INSERT INTO unknown_fields
            (field_hash, user_id, label, seen_on_domains, seen_count, answered, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, 0, ?, ?)
            """,
            (field_hash, user_id, label, json.dumps([domain]), now, now),
        )
