-- Sprint 1 schema (M0+M1+M2). SQLite >= 3.37 (STRICT tables).
-- Append-only history + immutable versioning are honored even at this stage.
-- Apply with: python -m app.cli migrate   (idempotent: IF NOT EXISTS everywhere)

-- ─────────────────────────── Identity & tenancy ───────────────────────────
CREATE TABLE IF NOT EXISTS candidate (
    id                  INTEGER PRIMARY KEY,
    display_name        TEXT    NOT NULL,
    email               TEXT    NOT NULL UNIQUE,
    api_token           TEXT    NOT NULL UNIQUE,          -- per-candidate auth/isolation
    status              TEXT    NOT NULL DEFAULT 'ACTIVE'
                            CHECK (status IN ('ACTIVE','PAUSED','ARCHIVED')),
    consent_granted_at  TEXT,
    created_at          TEXT    NOT NULL,
    updated_at          TEXT,
    deleted_at          TEXT
) STRICT;

-- Versioned profile carrying the trajectory spec (the scoring config).
CREATE TABLE IF NOT EXISTS candidate_profile_version (
    id                       INTEGER PRIMARY KEY,
    candidate_id             INTEGER NOT NULL REFERENCES candidate(id) ON DELETE CASCADE,
    version_no               INTEGER NOT NULL,
    total_experience_months  INTEGER NOT NULL DEFAULT 0 CHECK (total_experience_months >= 0),
    seniority_label          TEXT,
    core_skills_json         TEXT    NOT NULL DEFAULT '[]',   -- skills the candidate HAS
    acquiring_skills_json    TEXT    NOT NULL DEFAULT '[]',   -- skills the candidate WANTS
    target_roles_json        TEXT    NOT NULL DEFAULT '[]',   -- ranked destination roles
    acceptable_roles_json    TEXT    NOT NULL DEFAULT '[]',
    avoid_roles_json         TEXT    NOT NULL DEFAULT '[]',   -- backward moves
    target_domain_signals_json TEXT  NOT NULL DEFAULT '[]',   -- e.g. LLM, RAG, agents
    location_prefs_json      TEXT    NOT NULL DEFAULT '{}',   -- {"cities":[...]}
    remote_required          INTEGER NOT NULL DEFAULT 0 CHECK (remote_required IN (0,1)),
    current_ctc              REAL,
    salary_min_multiplier    REAL    NOT NULL DEFAULT 1.3,
    salary_target_multiplier REAL    NOT NULL DEFAULT 1.7,
    salary_stretch_multiplier REAL   NOT NULL DEFAULT 2.5,
    weights_json             TEXT    NOT NULL DEFAULT '{}',   -- dimension weights override
    target_embedding_json    TEXT,                            -- cached target-profile vector
    target_embedding_model   TEXT,
    is_current               INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
    effective_from           TEXT    NOT NULL,
    created_at               TEXT    NOT NULL,
    UNIQUE (candidate_id, version_no)
) STRICT;

-- One current profile version per candidate.
CREATE UNIQUE INDEX IF NOT EXISTS ux_profile_current
    ON candidate_profile_version (candidate_id) WHERE is_current = 1;

-- ─────────────────────────── Resumes (versioned) ──────────────────────────
CREATE TABLE IF NOT EXISTS resume (
    id           INTEGER PRIMARY KEY,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id) ON DELETE CASCADE,
    label        TEXT    NOT NULL,
    target_role  TEXT,
    created_at   TEXT    NOT NULL,
    UNIQUE (candidate_id, label)
) STRICT;

CREATE TABLE IF NOT EXISTS resume_version (
    id             INTEGER PRIMARY KEY,
    resume_id      INTEGER NOT NULL REFERENCES resume(id) ON DELETE CASCADE,
    version_no     INTEGER NOT NULL,
    content_text   TEXT,
    content_sha256 TEXT    NOT NULL,
    file_path      TEXT,
    is_current     INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
    created_at     TEXT    NOT NULL,
    UNIQUE (resume_id, version_no)
) STRICT;

-- ─────────────────────────── Companies & prefs ────────────────────────────
CREATE TABLE IF NOT EXISTS company (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    domain          TEXT,
    created_at      TEXT NOT NULL
) STRICT;

-- Per-candidate company preference. Distinct from scoring.
CREATE TABLE IF NOT EXISTS company_preference (
    id           INTEGER PRIMARY KEY,
    candidate_id INTEGER NOT NULL REFERENCES candidate(id) ON DELETE CASCADE,
    company_id   INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    preference   TEXT    NOT NULL
                    CHECK (preference IN ('PREFERRED','NEUTRAL','AVOID','BLOCKED')),
    note         TEXT,
    created_at   TEXT    NOT NULL,
    updated_at   TEXT,
    UNIQUE (candidate_id, company_id)
) STRICT;

-- ─────────────────────────────── Jobs ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS job (
    id                     INTEGER PRIMARY KEY,
    company_id             INTEGER NOT NULL REFERENCES company(id) ON DELETE RESTRICT,
    source                 TEXT    NOT NULL CHECK (source IN ('EMAIL','MANUAL','API')),
    discovery_method       TEXT    NOT NULL CHECK (discovery_method IN ('EMAIL','MANUAL','API')),
    source_ref             TEXT,                       -- e.g. LINKEDIN / NAUKRI / INDEED / gmail msg id
    source_url             TEXT,
    external_job_id        TEXT,
    title                  TEXT    NOT NULL,
    description_text       TEXT,
    location               TEXT,
    is_remote              INTEGER CHECK (is_remote IN (0,1)),
    min_experience_months  INTEGER,
    max_experience_months  INTEGER,
    salary_text            TEXT,
    salary_min             REAL,
    salary_max             REAL,
    currency               TEXT,
    dedup_hash             TEXT    NOT NULL UNIQUE,
    signal_density         TEXT    CHECK (signal_density IN ('RICH','THIN')),
    ingestion_status       TEXT    NOT NULL DEFAULT 'PARSED'
                              CHECK (ingestion_status IN ('RAW','PARSED','ACTIVE','CLOSED','ARCHIVED')),
    raw_payload_json       TEXT,
    posted_at              TEXT,
    role_class             TEXT,   -- M1.5 coarse role filter: KEEP | SOFT_DROP (DROP not stored)
    content_key            TEXT,   -- M1.5 cross-source dedup key (norm company|title|location)
    discovered_at          TEXT    NOT NULL,
    last_seen_at           TEXT    NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS ix_job_discovered_at ON job (discovered_at);
CREATE INDEX IF NOT EXISTS ix_job_company       ON job (company_id);
-- NOTE: ix_job_content_key is created in apply_schema() AFTER the additive
-- column migration, since content_key may not exist yet on a legacy DB.

-- Cached job embeddings (sidecar; keyed by model so a model change re-embeds).
CREATE TABLE IF NOT EXISTS job_embedding (
    id          INTEGER PRIMARY KEY,
    job_id      INTEGER NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    model       TEXT    NOT NULL,
    vector_json TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    UNIQUE (job_id, model)
) STRICT;

-- Remember processed Gmail messages so we never re-parse an alert.
CREATE TABLE IF NOT EXISTS processed_email (
    message_id   TEXT PRIMARY KEY,
    source_ref   TEXT,
    processed_at TEXT NOT NULL,
    job_count    INTEGER NOT NULL DEFAULT 0
) STRICT;

-- ─────────────────── Applications (candidate x job) + scores ───────────────
CREATE TABLE IF NOT EXISTS application (
    id                 INTEGER PRIMARY KEY,
    candidate_id       INTEGER NOT NULL REFERENCES candidate(id) ON DELETE CASCADE,
    job_id             INTEGER NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    current_state      TEXT    NOT NULL DEFAULT 'DISCOVERED'
                          CHECK (current_state IN (
                              'DISCOVERED','FILTERED','SCORED','SHORTLISTED',
                              'AWAITING_REVIEW','STALE_REVIEW','APPLICATION_PREPARED',
                              'VERIFY_SESSION','AWAITING_SESSION_LOGIN','APPLICATION_IN_PROGRESS',
                              'AWAITING_USER_INPUT','STALE_INPUT','READY_TO_SUBMIT',
                              'QUEUED_FOR_SUBMISSION','APPLICATION_LAUNCHED','SUBMITTED',
                              'REJECTED','FAILED')),
    reason_code        TEXT,                        -- e.g. COMPANY_BLOCKED, FILTERED_OUT
    profile_version_id INTEGER REFERENCES candidate_profile_version(id),
    priority_score     REAL,                        -- denormalized current total for ranking
    employer_outcome   TEXT    NOT NULL DEFAULT 'NONE'
                          CHECK (employer_outcome IN ('NONE','ACKED','REJECTED','INTERVIEW','OFFER')),
    verdict            TEXT,   -- M3 human triage: INTERESTED|NOT_INTERESTED|BOOKMARK|WRONG_MATCH
    verdict_note       TEXT,
    verdict_at         TEXT,
    created_at         TEXT    NOT NULL,
    updated_at         TEXT,
    deleted_at         TEXT,
    UNIQUE (candidate_id, job_id)
) STRICT;

CREATE INDEX IF NOT EXISTS ix_app_candidate_state
    ON application (candidate_id, current_state);
CREATE INDEX IF NOT EXISTS ix_app_candidate_priority
    ON application (candidate_id, priority_score DESC);

CREATE TABLE IF NOT EXISTS application_score (
    id                     INTEGER PRIMARY KEY,
    application_id         INTEGER NOT NULL REFERENCES application(id) ON DELETE CASCADE,
    trajectory_direction   TEXT    CHECK (trajectory_direction IN
                              ('LEAP','FORWARD','LATERAL','STALL','BACKWARD')),
    trajectory_score       REAL,
    skill_score            REAL,
    location_score         REAL,
    experience_score       REAL,
    salary_fit_score       REAL,
    career_alignment_score REAL,
    total_score            REAL    NOT NULL CHECK (total_score >= 0.0 AND total_score <= 1.0),
    confidence             REAL    CHECK (confidence >= 0.0 AND confidence <= 1.0),
    signal_density         TEXT    CHECK (signal_density IN ('RICH','THIN')),
    leap_override          INTEGER NOT NULL DEFAULT 0 CHECK (leap_override IN (0,1)),
    scoring_model_version  TEXT    NOT NULL,
    breakdown_json         TEXT,
    explanation_summary    TEXT,
    is_current             INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0,1)),
    scored_at              TEXT    NOT NULL
) STRICT;

CREATE UNIQUE INDEX IF NOT EXISTS ux_score_current
    ON application_score (application_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS score_signal (
    id          INTEGER PRIMARY KEY,
    score_id    INTEGER NOT NULL REFERENCES application_score(id) ON DELETE CASCADE,
    signal_type TEXT    NOT NULL CHECK (signal_type IN
                  ('TRAJECTORY','ROLE','SKILL','EXPERIENCE','SALARY','LOCATION','REMOTE',
                   'SENIORITY','COMPANY')),
    direction   TEXT    NOT NULL CHECK (direction IN ('POSITIVE','NEGATIVE','NEUTRAL')),
    weight      REAL,
    label       TEXT    NOT NULL,
    detail      TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS ix_signal_score ON score_signal (score_id);

-- Append-only workflow transition log.
CREATE TABLE IF NOT EXISTS application_state_history (
    id             INTEGER PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES application(id) ON DELETE CASCADE,
    from_state     TEXT,
    to_state       TEXT    NOT NULL,
    actor_type     TEXT    NOT NULL DEFAULT 'SYSTEM'
                      CHECK (actor_type IN ('SYSTEM','CANDIDATE','ADAPTER','LLM')),
    reason         TEXT,
    created_at     TEXT    NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS ix_history_app ON application_state_history (application_id, created_at);

-- ══════════════════════ M1.5 Company Career Discovery ══════════════════════

-- Reference data: one row per ATS platform (Sprint M1.5 = GREENHOUSE, LEVER).
CREATE TABLE IF NOT EXISTS ats_platform (
    id                 INTEGER PRIMARY KEY,
    key                TEXT NOT NULL UNIQUE,        -- GREENHOUSE | LEVER
    display_name       TEXT NOT NULL,
    discovery_kind     TEXT NOT NULL CHECK (discovery_kind IN
                          ('JSON_API','UNDOCUMENTED_JSON','HTML','RSS')),
    endpoint_template  TEXT NOT NULL,               -- {token} placeholder
    supports_full_description INTEGER NOT NULL DEFAULT 0 CHECK (supports_full_description IN (0,1)),
    capability_tier_default   TEXT NOT NULL DEFAULT 'DISCOVERY_ONLY',
    automation_difficulty     TEXT,
    rate_limit_per_min INTEGER NOT NULL DEFAULT 30,
    notes              TEXT,
    created_at         TEXT NOT NULL
) STRICT;

-- Per-company discovery binding: which ATS/board, schedule, health.
CREATE TABLE IF NOT EXISTS company_ats (
    id                  INTEGER PRIMARY KEY,
    company_id          INTEGER NOT NULL REFERENCES company(id) ON DELETE CASCADE,
    ats_platform_id     INTEGER NOT NULL REFERENCES ats_platform(id) ON DELETE RESTRICT,
    board_token         TEXT    NOT NULL,
    board_url           TEXT,
    careers_url         TEXT,
    tier                TEXT    NOT NULL DEFAULT 'TIER2'
                          CHECK (tier IN ('TIER1','TIER2','TIER3')),
    priority_score      REAL,
    schedule_interval_minutes INTEGER NOT NULL DEFAULT 1440,
    next_check_at       TEXT,
    last_checked_at     TEXT,
    last_success_at     TEXT,
    last_change_at      TEXT,
    etag                TEXT,
    last_modified       TEXT,
    board_content_hash  TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    health_status       TEXT    NOT NULL DEFAULT 'HEALTHY'
                          CHECK (health_status IN ('HEALTHY','DEGRADED','BROKEN')),
    is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    disabled_reason     TEXT,
    created_at          TEXT    NOT NULL,
    updated_at          TEXT,
    UNIQUE (company_id, ats_platform_id, board_token)
) STRICT;

CREATE INDEX IF NOT EXISTS ix_company_ats_due
    ON company_ats (is_active, next_check_at);
CREATE INDEX IF NOT EXISTS ix_company_ats_platform
    ON company_ats (ats_platform_id);

-- Append-only observability + change log for each discovery fetch.
CREATE TABLE IF NOT EXISTS discovery_run (
    id             INTEGER PRIMARY KEY,
    company_ats_id INTEGER NOT NULL REFERENCES company_ats(id) ON DELETE CASCADE,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    status         TEXT NOT NULL CHECK (status IN ('OK','NOT_MODIFIED','ERROR','DISABLED')),
    http_status    INTEGER,
    jobs_seen      INTEGER NOT NULL DEFAULT 0,
    jobs_new       INTEGER NOT NULL DEFAULT 0,
    jobs_closed    INTEGER NOT NULL DEFAULT 0,
    jobs_dropped   INTEGER NOT NULL DEFAULT 0,   -- role-filtered out
    bytes          INTEGER,
    error          TEXT
) STRICT;

CREATE INDEX IF NOT EXISTS ix_discovery_run_cats
    ON discovery_run (company_ats_id, started_at);
