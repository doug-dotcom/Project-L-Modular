-- =====================================================
-- PROJECT L
-- SHORT-TERM MEMORY TABLES
-- =====================================================

-- =====================================================
-- IDENTITY
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_identity (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- FAMILY
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_family (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- FRIENDS / PARTNERS
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_relationships (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- HEALTH
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_health (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- FINANCE
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_finance (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- SPORT
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_sport (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- KNOWLEDGE
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_knowledge (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- RECOVERY
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_recovery (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- PROJECT L
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_project_l (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =====================================================
-- GENERAL
-- =====================================================

CREATE TABLE IF NOT EXISTS short_term_general (
    id BIGSERIAL PRIMARY KEY,
    role TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

