CREATE TABLE IF NOT EXISTS jobs (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    company          TEXT NOT NULL,
    company_domain   TEXT,
    career_page_url  TEXT NOT NULL,
    source           TEXT NOT NULL,
    jd_text          TEXT,
    score            INTEGER DEFAULT 0,
    score_reason     TEXT,
    status           TEXT DEFAULT "new",
    scraped_at       DATETIME NOT NULL,
    user_id          TEXT NOT NULL DEFAULT "default"
);

CREATE TABLE IF NOT EXISTS applications (
    id                  TEXT PRIMARY KEY,
    job_id              TEXT NOT NULL REFERENCES jobs(id),
    user_id             TEXT NOT NULL,
    applied_at          DATETIME NOT NULL,
    ats_system          TEXT,
    fields_filled       INTEGER DEFAULT 0,
    fields_skipped      INTEGER DEFAULT 0,
    screenshot_path     TEXT,
    submit_status       TEXT DEFAULT "pending_review",
    pipeline_stage      TEXT DEFAULT "applied",
    pipeline_updated_at DATETIME,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS companies_seen (
    domain            TEXT NOT NULL,
    user_id           TEXT NOT NULL,
    company_name      TEXT,
    first_applied_at  DATETIME NOT NULL,
    cooldown_until    DATETIME,
    blocklist         INTEGER DEFAULT 0,
    PRIMARY KEY (domain, user_id)
);

CREATE TABLE IF NOT EXISTS outreach (
    id               TEXT PRIMARY KEY,
    job_id           TEXT NOT NULL REFERENCES jobs(id),
    user_id          TEXT NOT NULL,
    recruiter_name   TEXT,
    recruiter_email  TEXT,
    draft_subject    TEXT,
    draft_body       TEXT,
    gmail_draft_id   TEXT,
    created_at       DATETIME NOT NULL,
    sent_at          DATETIME,
    reply_received   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS unknown_fields (
    field_hash      TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    label           TEXT NOT NULL,
    seen_on_domains TEXT DEFAULT "[]",
    seen_count      INTEGER DEFAULT 1,
    your_answer     TEXT,
    answered        INTEGER DEFAULT 0,
    created_at      DATETIME NOT NULL,
    updated_at      DATETIME NOT NULL,
    PRIMARY KEY (field_hash, user_id)
);

CREATE TABLE IF NOT EXISTS run_logs (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    started_at  DATETIME NOT NULL,
    finished_at DATETIME,
    status      TEXT DEFAULT "running",
    sourced     INTEGER DEFAULT 0,
    scored      INTEGER DEFAULT 0,
    applied     INTEGER DEFAULT 0,
    skipped     INTEGER DEFAULT 0,
    failed      INTEGER DEFAULT 0,
    summary     TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_status       ON jobs(status, user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped      ON jobs(scraped_at, user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_score        ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_apps_date         ON applications(applied_at, user_id);
CREATE INDEX IF NOT EXISTS idx_companies_domain  ON companies_seen(domain, user_id);
CREATE INDEX IF NOT EXISTS idx_unknown_answered  ON unknown_fields(answered, user_id);
