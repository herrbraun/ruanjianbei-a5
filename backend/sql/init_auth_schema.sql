-- AI digital human scenic tour guide auth schema.
-- Usage:
--   psql -h localhost -p 5432 -U postgres -d ai_tour_guide -f backend/sql/init_auth_schema.sql

BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    nickname VARCHAR(100),
    avatar_url VARCHAR(500),
    role VARCHAR(20) NOT NULL CHECK (role IN ('visitor', 'admin')),
    is_guest BOOLEAN NOT NULL DEFAULT FALSE,
    guest_key_hash VARCHAR(64),
    guest_expires_at TIMESTAMPTZ,
    last_seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_guest BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS guest_key_hash VARCHAR(64);
ALTER TABLE users ADD COLUMN IF NOT EXISTS guest_expires_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);
CREATE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower ON users (LOWER(username)) WHERE username IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_guest_key_hash ON users (guest_key_hash);
CREATE INDEX IF NOT EXISTS ix_users_guest_expires_at ON users (guest_expires_at);

CREATE TABLE IF NOT EXISTS visitor_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interest VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_visitor_profiles_id ON visitor_profiles (id);
CREATE INDEX IF NOT EXISTS ix_visitor_profiles_user_id ON visitor_profiles (user_id);

CREATE TABLE IF NOT EXISTS admin_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    display_name VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_admin_profiles_id ON admin_profiles (id);
CREATE INDEX IF NOT EXISTS ix_admin_profiles_user_id ON admin_profiles (user_id);

CREATE TABLE IF NOT EXISTS login_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    role VARCHAR(20),
    login_time TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS ix_login_logs_id ON login_logs (id);
CREATE INDEX IF NOT EXISTS ix_login_logs_user_id ON login_logs (user_id);

-- Only create the default administrator when it does not already exist.
-- Re-running this script must not reset an existing administrator's password.
INSERT INTO users (username, password_hash, nickname, role)
VALUES (
    'admin',
    '$2b$12$wsX0PnbqAVJxcr6Lsky5GeZURKYW0HIn5JcCdkXCHJaltqeaTwrtu',
    '系统管理员',
    'admin'
)
ON CONFLICT (username) DO NOTHING;

INSERT INTO admin_profiles (user_id, display_name)
SELECT users.id, '系统管理员'
FROM users
WHERE users.username = 'admin'
AND NOT EXISTS (
    SELECT 1
    FROM admin_profiles
    WHERE admin_profiles.user_id = users.id
);

CREATE TABLE IF NOT EXISTS scenic_areas (
    id SERIAL PRIMARY KEY,
    code VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id SERIAL PRIMARY KEY,
    code VARCHAR(64) UNIQUE NOT NULL,
    name VARCHAR(120) NOT NULL,
    description TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rag_profiles (
    id SERIAL PRIMARY KEY,
    scenic_area_id INTEGER NOT NULL REFERENCES scenic_areas(id) ON DELETE CASCADE,
    name VARCHAR(120) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    embedding_model VARCHAR(100) NOT NULL DEFAULT 'text-embedding-v4',
    embedding_dimensions INTEGER NOT NULL DEFAULT 1024,
    top_k INTEGER NOT NULL DEFAULT 5,
    rerank_model VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_rag_profiles_scenic_area_id ON rag_profiles (scenic_area_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_profiles_one_active_per_scenic
    ON rag_profiles (scenic_area_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS rag_profile_knowledge_bases (
    id SERIAL PRIMARY KEY,
    rag_profile_id INTEGER NOT NULL REFERENCES rag_profiles(id) ON DELETE CASCADE,
    knowledge_base_id INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    retrieval_priority INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_rag_profile_knowledge_base UNIQUE (rag_profile_id, knowledge_base_id)
);
CREATE INDEX IF NOT EXISTS ix_rag_profile_knowledge_bases_profile ON rag_profile_knowledge_bases (rag_profile_id);
CREATE INDEX IF NOT EXISTS ix_rag_profile_knowledge_bases_base ON rag_profile_knowledge_bases (knowledge_base_id);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id SERIAL PRIMARY KEY,
    knowledge_base_id INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(120) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    source_priority INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'indexing', 'indexed', 'failed')),
    error_message TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    embedding_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMPTZ,
    CONSTRAINT uq_knowledge_documents_base_hash UNIQUE (knowledge_base_id, content_hash)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_documents_base_status ON knowledge_documents (knowledge_base_id, status);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    knowledge_base_id INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    spot_id VARCHAR(100),
    spot_name VARCHAR(160),
    section VARCHAR(255),
    ordinal INTEGER NOT NULL,
    content TEXT NOT NULL,
    source_locator VARCHAR(255),
    content_hash VARCHAR(64) NOT NULL,
    CONSTRAINT uq_knowledge_chunks_document_ordinal UNIQUE (document_id, ordinal)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_base_spot ON knowledge_chunks (knowledge_base_id, spot_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_document_id ON knowledge_chunks (document_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_knowledge_base_id ON knowledge_chunks (knowledge_base_id);

CREATE TABLE IF NOT EXISTS knowledge_embeddings (
    id SERIAL PRIMARY KEY,
    chunk_id INTEGER UNIQUE NOT NULL REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
    embedding_model VARCHAR(100) NOT NULL DEFAULT 'text-embedding-v4',
    dimensions INTEGER NOT NULL DEFAULT 1024,
    embedding DOUBLE PRECISION[] NOT NULL,
    indexed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rag_query_logs (
    id SERIAL PRIMARY KEY,
    scenic_area_id INTEGER NOT NULL REFERENCES scenic_areas(id) ON DELETE CASCADE,
    rag_profile_id INTEGER REFERENCES rag_profiles(id) ON DELETE SET NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    filters JSONB,
    hits JSONB,
    duration_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS digital_humans (
    id SERIAL PRIMARY KEY,
    name VARCHAR(80) NOT NULL UNIQUE,
    gender VARCHAR(20) NOT NULL DEFAULT 'unspecified' CHECK (gender IN ('female', 'male', 'unspecified')),
    role_title VARCHAR(120) NOT NULL,
    introduction TEXT,
    tts_provider VARCHAR(30) NOT NULL DEFAULT 'volcengine'
        CHECK (tts_provider IN ('volcengine', 'dashscope')),
    tts_voice VARCHAR(100) NOT NULL,
    tts_instructions TEXT,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tts_provider_settings (
    provider VARCHAR(30) PRIMARY KEY CHECK (provider IN ('volcengine', 'dashscope')),
    display_name VARCHAR(80) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    model VARCHAR(120) NOT NULL,
    default_voice VARCHAR(100) NOT NULL,
    first_chunk_timeout_ms INTEGER NOT NULL DEFAULT 4500
        CHECK (first_chunk_timeout_ms BETWEEN 500 AND 10000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_tts_provider_settings_one_default
    ON tts_provider_settings (is_default) WHERE is_default;
CREATE UNIQUE INDEX IF NOT EXISTS uq_tts_provider_settings_one_fallback
    ON tts_provider_settings (is_fallback) WHERE is_fallback;

INSERT INTO tts_provider_settings
    (provider, display_name, is_enabled, is_default, is_fallback, model, default_voice, first_chunk_timeout_ms)
VALUES
    ('volcengine', '火山引擎实时语音', TRUE, TRUE, FALSE, 'seed-tts-2.0', 'zh_female_vv_uranus_bigtts', 4500),
    ('dashscope', '阿里云百炼千问语音', TRUE, FALSE, TRUE, 'qwen3-tts-instruct-flash', 'Cherry', 4500)
ON CONFLICT (provider) DO NOTHING;

CREATE TABLE IF NOT EXISTS avatar_variants (
    id SERIAL PRIMARY KEY,
    digital_human_id INTEGER NOT NULL REFERENCES digital_humans(id) ON DELETE CASCADE,
    outfit_name VARCHAR(120) NOT NULL,
    version VARCHAR(40) NOT NULL DEFAULT 'v1',
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL UNIQUE,
    content_hash VARCHAR(64) NOT NULL,
    file_size INTEGER NOT NULL,
    thumbnail_url VARCHAR(500),
    validation_status VARCHAR(20) NOT NULL DEFAULT 'ready' CHECK (validation_status IN ('ready', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_avatar_variants_human_outfit_version UNIQUE (digital_human_id, outfit_name, version)
);
CREATE INDEX IF NOT EXISTS ix_avatar_variants_digital_human_id ON avatar_variants (digital_human_id);

CREATE TABLE IF NOT EXISTS scenic_avatar_configs (
    id SERIAL PRIMARY KEY,
    scenic_area_id INTEGER NOT NULL REFERENCES scenic_areas(id) ON DELETE CASCADE,
    avatar_variant_id INTEGER NOT NULL REFERENCES avatar_variants(id) ON DELETE CASCADE,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_scenic_avatar_configs_area_variant UNIQUE (scenic_area_id, avatar_variant_id)
);
CREATE INDEX IF NOT EXISTS ix_scenic_avatar_configs_scenic_area_id ON scenic_avatar_configs (scenic_area_id);
CREATE INDEX IF NOT EXISTS ix_scenic_avatar_configs_avatar_variant_id ON scenic_avatar_configs (avatar_variant_id);
CREATE INDEX IF NOT EXISTS ix_scenic_avatar_configs_area_enabled_sort ON scenic_avatar_configs (scenic_area_id, is_enabled, sort_order);
CREATE UNIQUE INDEX IF NOT EXISTS uq_scenic_avatar_configs_one_default
    ON scenic_avatar_configs (scenic_area_id) WHERE is_default AND is_enabled;

CREATE TABLE IF NOT EXISTS guide_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenic_area_id INTEGER NOT NULL REFERENCES scenic_areas(id) ON DELETE CASCADE,
    initial_rag_profile_id INTEGER REFERENCES rag_profiles(id) ON DELETE SET NULL,
    route_plan_id INTEGER,
    current_spot_id INTEGER,
    title VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE guide_sessions ADD COLUMN IF NOT EXISTS route_plan_id INTEGER;
ALTER TABLE guide_sessions ADD COLUMN IF NOT EXISTS current_spot_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_guide_sessions_user_id ON guide_sessions (user_id);
CREATE INDEX IF NOT EXISTS ix_guide_sessions_scenic_area_id ON guide_sessions (scenic_area_id);
CREATE INDEX IF NOT EXISTS ix_guide_sessions_initial_rag_profile_id ON guide_sessions (initial_rag_profile_id);
CREATE INDEX IF NOT EXISTS ix_guide_sessions_route_plan_id ON guide_sessions (route_plan_id);
CREATE INDEX IF NOT EXISTS ix_guide_sessions_current_spot_id ON guide_sessions (current_spot_id);
CREATE INDEX IF NOT EXISTS ix_guide_sessions_user_updated ON guide_sessions (user_id, updated_at);

CREATE TABLE IF NOT EXISTS guide_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES guide_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    input_mode VARCHAR(20) CHECK (input_mode IS NULL OR input_mode IN ('text', 'voice')),
    content TEXT NOT NULL,
    rag_profile_id INTEGER REFERENCES rag_profiles(id) ON DELETE SET NULL,
    sources JSONB,
    answer_model VARCHAR(100),
    answer_duration_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'failed')),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_guide_messages_session_id ON guide_messages (session_id);
CREATE INDEX IF NOT EXISTS ix_guide_messages_rag_profile_id ON guide_messages (rag_profile_id);
CREATE INDEX IF NOT EXISTS ix_guide_messages_session_created ON guide_messages (session_id, created_at);

CREATE TABLE IF NOT EXISTS guide_message_insights (
    id SERIAL PRIMARY KEY,
    scenic_area_id INTEGER NOT NULL REFERENCES scenic_areas(id) ON DELETE CASCADE,
    guide_session_id INTEGER NOT NULL REFERENCES guide_sessions(id) ON DELETE CASCADE,
    visitor_message_id INTEGER NOT NULL UNIQUE REFERENCES guide_messages(id) ON DELETE CASCADE,
    assistant_message_id INTEGER REFERENCES guide_messages(id) ON DELETE SET NULL,
    normalized_question VARCHAR(120), primary_topic VARCHAR(50), topic_tags JSON,
    intent VARCHAR(50), sentiment VARCHAR(20), sentiment_score DOUBLE PRECISION,
    issue_type VARCHAR(50), needs_attention BOOLEAN NOT NULL DEFAULT FALSE,
    resolution_status VARCHAR(20) NOT NULL DEFAULT 'unresolved', resolved_at TIMESTAMPTZ,
    resolved_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    analysis_status VARCHAR(20) NOT NULL DEFAULT 'pending', analysis_model VARCHAR(100),
    analysis_attempts INTEGER NOT NULL DEFAULT 0, error_message TEXT, analyzed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (analysis_status IN ('pending','processing','completed','failed')),
    CHECK (sentiment IS NULL OR sentiment IN ('positive','neutral','negative')),
    CHECK (sentiment_score IS NULL OR sentiment_score BETWEEN -1 AND 1),
    CHECK (resolution_status IN ('unresolved','resolved'))
);
CREATE INDEX IF NOT EXISTS ix_guide_insights_scenic_created ON guide_message_insights (scenic_area_id, created_at);
CREATE INDEX IF NOT EXISTS ix_guide_insights_scenic_sentiment_created ON guide_message_insights (scenic_area_id, sentiment, created_at);
CREATE INDEX IF NOT EXISTS ix_guide_insights_status_updated ON guide_message_insights (analysis_status, updated_at);
CREATE INDEX IF NOT EXISTS ix_guide_insights_attention_resolution_created ON guide_message_insights (needs_attention, resolution_status, created_at);

CREATE TABLE IF NOT EXISTS guide_feedbacks (
    id SERIAL PRIMARY KEY,
    guide_session_id INTEGER NOT NULL UNIQUE REFERENCES guide_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenic_area_id INTEGER NOT NULL REFERENCES scenic_areas(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5), tags JSON NOT NULL DEFAULT '[]', comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_guide_feedbacks_scenic_created ON guide_feedbacks (scenic_area_id, created_at);

CREATE TABLE IF NOT EXISTS scenic_insight_reports (
    id SERIAL PRIMARY KEY,
    scenic_area_id INTEGER NOT NULL REFERENCES scenic_areas(id) ON DELETE CASCADE,
    period_type VARCHAR(20) NOT NULL CHECK (period_type IN ('daily','weekly')),
    period_start DATE NOT NULL, period_end DATE NOT NULL, metrics_snapshot JSON NOT NULL,
    summary TEXT, attention_points JSON, risk_findings JSON, recommendations JSON,
    generation_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (generation_status IN ('pending','processing','completed','failed')),
    generation_model VARCHAR(100), error_message TEXT,
    trigger_source VARCHAR(20) NOT NULL DEFAULT 'manual' CHECK (trigger_source IN ('manual','scheduled')),
    deduplication_key VARCHAR(160) UNIQUE,
    generation_attempts INTEGER NOT NULL DEFAULT 0,
    processing_started_at TIMESTAMPTZ,
    created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    generated_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_scenic_insight_reports_scenic_period ON scenic_insight_reports (scenic_area_id, period_start, period_end);
ALTER TABLE scenic_insight_reports ADD COLUMN IF NOT EXISTS trigger_source VARCHAR(20) NOT NULL DEFAULT 'manual';
ALTER TABLE scenic_insight_reports ADD COLUMN IF NOT EXISTS deduplication_key VARCHAR(160);
ALTER TABLE scenic_insight_reports ADD COLUMN IF NOT EXISTS generation_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scenic_insight_reports ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ;
DO $$
BEGIN
    ALTER TABLE scenic_insight_reports
        ADD CONSTRAINT ck_scenic_insight_reports_trigger_source
        CHECK (trigger_source IN ('manual', 'scheduled'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS uq_scenic_insight_reports_deduplication_key
    ON scenic_insight_reports (deduplication_key) WHERE deduplication_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS insight_report_schedules (
    id SERIAL PRIMARY KEY,
    scenic_area_id INTEGER NOT NULL UNIQUE REFERENCES scenic_areas(id) ON DELETE CASCADE,
    daily_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    daily_run_time TIME NOT NULL DEFAULT '00:10:00',
    weekly_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    weekly_weekday INTEGER NOT NULL DEFAULT 0 CHECK (weekly_weekday BETWEEN 0 AND 6),
    weekly_run_time TIME NOT NULL DEFAULT '00:20:00',
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    updated_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO scenic_areas (code, name, description)
VALUES
    ('lingshan', '灵山胜境', '灵山胜境示范景区'),
    ('nianhuawan', '拈花湾禅意小镇', '拈花湾禅意小镇景区')
ON CONFLICT (code) DO NOTHING;

INSERT INTO insight_report_schedules (scenic_area_id)
SELECT id FROM scenic_areas WHERE is_enabled = TRUE
ON CONFLICT (scenic_area_id) DO NOTHING;

INSERT INTO knowledge_bases (code, name, description)
VALUES
    ('lingshan-structured', '灵山结构化景点资料库', '景点基础信息、开放时间与演艺安排'),
    ('lingshan-culture', '灵山历史文化资料库', '历史、文化和导览叙述资料'),
    ('nianhuawan-structured', '拈花湾结构化景点资料库', '景点基础信息、开放时间与演艺安排'),
    ('nianhuawan-culture', '拈花湾历史文化资料库', '历史、文化和导览叙述资料')
ON CONFLICT (code) DO NOTHING;

INSERT INTO rag_profiles (scenic_area_id, name, status)
SELECT id, '灵山正式版 RAG', 'active' FROM scenic_areas WHERE code = 'lingshan'
ON CONFLICT DO NOTHING;

INSERT INTO rag_profiles (scenic_area_id, name, status)
SELECT id, '拈花湾正式版 RAG', 'active' FROM scenic_areas WHERE code = 'nianhuawan'
ON CONFLICT DO NOTHING;

INSERT INTO rag_profile_knowledge_bases (rag_profile_id, knowledge_base_id, retrieval_priority)
SELECT profile.id, base.id, CASE WHEN base.code = 'lingshan-structured' THEN 100 ELSE 10 END
FROM rag_profiles profile
JOIN scenic_areas scenic ON scenic.id = profile.scenic_area_id
JOIN knowledge_bases base ON base.code IN ('lingshan-structured', 'lingshan-culture')
WHERE scenic.code = 'lingshan' AND profile.name = '灵山正式版 RAG'
ON CONFLICT (rag_profile_id, knowledge_base_id) DO NOTHING;

INSERT INTO rag_profile_knowledge_bases (rag_profile_id, knowledge_base_id, retrieval_priority)
SELECT profile.id, base.id, CASE WHEN base.code = 'nianhuawan-structured' THEN 100 ELSE 10 END
FROM rag_profiles profile
JOIN scenic_areas scenic ON scenic.id = profile.scenic_area_id
JOIN knowledge_bases base ON base.code IN ('nianhuawan-structured', 'nianhuawan-culture')
WHERE scenic.code = 'nianhuawan' AND profile.name = '拈花湾正式版 RAG'
ON CONFLICT (rag_profile_id, knowledge_base_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS scenic_spots (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(30),
    scenic_area VARCHAR(120) NOT NULL DEFAULT '灵山胜境',
    spot_type VARCHAR(20) NOT NULL DEFAULT 'attraction' CHECK (spot_type IN ('attraction', 'area', 'service')),
    name VARCHAR(120) NOT NULL,
    summary VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(500),
    opening_hours VARCHAR(1000),
    landscape_parameters TEXT,
    cultural_context TEXT,
    highlights TEXT,
    notes TEXT,
    source_name VARCHAR(255),
    recommended_duration_minutes INTEGER NOT NULL DEFAULT 30,
    priority INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'enabled' CHECK (status IN ('enabled', 'disabled')),
    cover_image_url VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_scenic_spots_external_id UNIQUE (external_id)
);
CREATE INDEX IF NOT EXISTS ix_scenic_spots_id ON scenic_spots (id);
CREATE INDEX IF NOT EXISTS ix_scenic_spots_external_id ON scenic_spots (external_id);
CREATE INDEX IF NOT EXISTS ix_scenic_spots_scenic_area ON scenic_spots (scenic_area);
CREATE INDEX IF NOT EXISTS ix_scenic_spots_spot_type ON scenic_spots (spot_type);
CREATE INDEX IF NOT EXISTS ix_scenic_spots_name ON scenic_spots (name);

CREATE TABLE IF NOT EXISTS spot_tags (
    id SERIAL PRIMARY KEY,
    spot_id INTEGER NOT NULL REFERENCES scenic_spots(id) ON DELETE CASCADE,
    name VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_spot_tags_spot_name UNIQUE (spot_id, name)
);
CREATE INDEX IF NOT EXISTS ix_spot_tags_id ON spot_tags (id);
CREATE INDEX IF NOT EXISTS ix_spot_tags_spot_id ON spot_tags (spot_id);
CREATE INDEX IF NOT EXISTS ix_spot_tags_name ON spot_tags (name);

CREATE TABLE IF NOT EXISTS spot_media_assets (
    id SERIAL PRIMARY KEY,
    spot_id INTEGER NOT NULL REFERENCES scenic_spots(id) ON DELETE CASCADE,
    media_type VARCHAR(20) NOT NULL CHECK (media_type IN ('image', 'video', 'audio')),
    url VARCHAR(1000) NOT NULL,
    description VARCHAR(255),
    sort_order INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'enabled' CHECK (status IN ('enabled', 'disabled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_spot_media_spot_url UNIQUE (spot_id, url)
);
CREATE INDEX IF NOT EXISTS ix_spot_media_assets_id ON spot_media_assets (id);
CREATE INDEX IF NOT EXISTS ix_spot_media_assets_spot_id ON spot_media_assets (spot_id);

CREATE TABLE IF NOT EXISTS route_recommendation_settings (
    id SERIAL PRIMARY KEY,
    tag_match_weight INTEGER NOT NULL DEFAULT 100 CHECK (tag_match_weight BETWEEN 0 AND 1000),
    priority_weight NUMERIC(6, 2) NOT NULL DEFAULT 1 CHECK (priority_weight BETWEEN 0 AND 100),
    max_spots INTEGER NOT NULL DEFAULT 12 CHECK (max_spots BETWEEN 1 AND 30),
    include_service_points BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS route_plans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    start_spot_id INTEGER REFERENCES scenic_spots(id) ON DELETE SET NULL,
    scenic_area VARCHAR(120) NOT NULL,
    interest VARCHAR(100) NOT NULL,
    preference VARCHAR(20) NOT NULL DEFAULT 'balanced' CHECK (preference IN ('balanced', 'priority', 'more_spots')),
    duration_minutes INTEGER NOT NULL,
    total_duration_minutes INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_route_plans_id ON route_plans (id);
CREATE INDEX IF NOT EXISTS ix_route_plans_user_id ON route_plans (user_id);
CREATE INDEX IF NOT EXISTS ix_route_plans_start_spot_id ON route_plans (start_spot_id);
CREATE INDEX IF NOT EXISTS ix_route_plans_scenic_area ON route_plans (scenic_area);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_guide_sessions_route_plan_id') THEN
        ALTER TABLE guide_sessions ADD CONSTRAINT fk_guide_sessions_route_plan_id
            FOREIGN KEY (route_plan_id) REFERENCES route_plans(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_guide_sessions_current_spot_id') THEN
        ALTER TABLE guide_sessions ADD CONSTRAINT fk_guide_sessions_current_spot_id
            FOREIGN KEY (current_spot_id) REFERENCES scenic_spots(id) ON DELETE SET NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS route_spots (
    id SERIAL PRIMARY KEY,
    route_plan_id INTEGER NOT NULL REFERENCES route_plans(id) ON DELETE CASCADE,
    spot_id INTEGER REFERENCES scenic_spots(id) ON DELETE SET NULL,
    sequence INTEGER NOT NULL,
    stay_minutes INTEGER NOT NULL,
    reason TEXT NOT NULL,
    CONSTRAINT uq_route_spots_plan_sequence UNIQUE (route_plan_id, sequence)
);
CREATE INDEX IF NOT EXISTS ix_route_spots_id ON route_spots (id);
CREATE INDEX IF NOT EXISTS ix_route_spots_route_plan_id ON route_spots (route_plan_id);
CREATE INDEX IF NOT EXISTS ix_route_spots_spot_id ON route_spots (spot_id);

CREATE TABLE IF NOT EXISTS route_feedback (
    id SERIAL PRIMARY KEY,
    route_plan_id INTEGER NOT NULL UNIQUE REFERENCES route_plans(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_route_feedback_id ON route_feedback (id);
CREATE INDEX IF NOT EXISTS ix_route_feedback_user_id ON route_feedback (user_id);

CREATE TABLE IF NOT EXISTS visitor_behavior_records (
    id SERIAL PRIMARY KEY,
    source_record_key VARCHAR(64) NOT NULL,
    tourist_id VARCHAR(30) NOT NULL,
    user_nickname VARCHAR(100) NOT NULL,
    age INTEGER NOT NULL,
    gender VARCHAR(10) NOT NULL,
    attraction_name VARCHAR(120) NOT NULL,
    attraction_content TEXT NOT NULL,
    attraction_type VARCHAR(50) NOT NULL,
    visit_date DATE NOT NULL,
    stay_duration_hours NUMERIC(6, 2) NOT NULL,
    ticket_cost NUMERIC(10, 2) NOT NULL,
    food_cost NUMERIC(10, 2) NOT NULL,
    shopping_cost NUMERIC(10, 2) NOT NULL,
    transport_cost NUMERIC(10, 2) NOT NULL,
    entertainment_cost NUMERIC(10, 2) NOT NULL,
    total_cost NUMERIC(10, 2) NOT NULL,
    group_size INTEGER NOT NULL,
    satisfaction INTEGER NOT NULL CHECK (satisfaction BETWEEN 1 AND 5),
    source_name VARCHAR(255) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_behavior_source_record_key UNIQUE (source_record_key)
);
CREATE INDEX IF NOT EXISTS ix_visitor_behavior_records_id ON visitor_behavior_records (id);
CREATE INDEX IF NOT EXISTS ix_visitor_behavior_records_source_record_key ON visitor_behavior_records (source_record_key);
CREATE INDEX IF NOT EXISTS ix_visitor_behavior_records_tourist_id ON visitor_behavior_records (tourist_id);
CREATE INDEX IF NOT EXISTS ix_visitor_behavior_records_attraction_name ON visitor_behavior_records (attraction_name);
CREATE INDEX IF NOT EXISTS ix_visitor_behavior_records_attraction_type ON visitor_behavior_records (attraction_type);
CREATE INDEX IF NOT EXISTS ix_visitor_behavior_records_visit_date ON visitor_behavior_records (visit_date);

COMMIT;
