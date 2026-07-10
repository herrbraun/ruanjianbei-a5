-- AI digital human scenic tour guide auth schema.
-- Usage:
--   psql -h localhost -p 5432 -U postgres -d ai_tour_guide -f backend/sql/init_auth_schema.sql

BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255),
    nickname VARCHAR(100),
    role VARCHAR(20) NOT NULL CHECK (role IN ('visitor', 'admin')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);

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

COMMIT;
