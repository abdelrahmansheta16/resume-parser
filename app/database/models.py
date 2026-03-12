"""PostgreSQL schema reference (managed via Supabase migrations).

The actual schema lives in app/database/migrations/001_initial.sql and is
applied through the Supabase SQL Editor. This module is kept for documentation
and backward compatibility — SCHEMA_SQL is no longer executed at runtime.
"""
from __future__ import annotations

SCHEMA_SQL = """
-- PostgreSQL schema (Supabase) — reference only, not executed at runtime.
-- See app/database/migrations/001_initial.sql for the canonical version.

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    title TEXT,
    company TEXT,
    location TEXT,
    description TEXT,
    apply_url TEXT,
    required_skills JSONB DEFAULT '[]'::jsonb,
    preferred_skills JSONB DEFAULT '[]'::jsonb,
    salary_range TEXT,
    posting_date TEXT,
    source TEXT,
    raw_text TEXT,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    employment_type TEXT,
    required_years_experience REAL,
    education_requirements JSONB DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS searches (
    id BIGSERIAL PRIMARY KEY,
    connector TEXT,
    keywords TEXT,
    location TEXT,
    result_count INTEGER,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS applications (
    id BIGSERIAL PRIMARY KEY,
    job_id TEXT REFERENCES jobs(job_id),
    candidate_name TEXT,
    match_score REAL DEFAULT 0.0,
    ats_score REAL DEFAULT 0.0,
    docx_path TEXT,
    pdf_path TEXT,
    cover_letter_path TEXT,
    status TEXT DEFAULT 'generated',
    user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS scheduled_profiles (
    id BIGSERIAL PRIMARY KEY,
    profile_name TEXT NOT NULL,
    profile_json JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    interval_minutes INTEGER DEFAULT 360,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    user_id UUID REFERENCES auth.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES scheduled_profiles(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES jobs(job_id),
    match_score REAL NOT NULL,
    recommendation TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""
