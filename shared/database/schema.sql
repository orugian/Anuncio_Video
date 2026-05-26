-- Schema para o Supabase (PostgreSQL)

-- 1. Enum para status de jobs
CREATE TYPE job_status AS ENUM (
    'received',
    'scraping',
    'semantic_processing',
    'prompt_generation',
    'awaiting_approval',
    'video_generation',
    'completed',
    'failed'
);

-- 2. Tabela de Jobs (Entrada do Pipeline)
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR NOT NULL,
    url TEXT NOT NULL,
    status job_status DEFAULT 'received',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Tabela de Scraping (Dados Brutos)
CREATE TABLE scraped_content (
    job_id UUID PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    raw_json JSONB NOT NULL,
    images JSONB NOT NULL, -- Array of strings (URLs)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Tabela de Contexto Semântico (Processamento IA)
CREATE TABLE semantic_context (
    job_id UUID PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    semantic_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4.1 Tabela de Roteiros de Marketing
CREATE TABLE marketing_scripts (
    job_id UUID PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    script_json JSONB NOT NULL,
    feedback_history JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Tabela de Versões de Vídeo (Geração e Iteração)
CREATE TABLE video_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    prompt TEXT NOT NULL,
    video_url TEXT,
    status VARCHAR DEFAULT 'pending', -- 'pending', 'rendering', 'completed', 'failed'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(job_id, version_number)
);

-- 6. Tabela de Feedbacks (Ajustes via Telegram)
CREATE TABLE feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID REFERENCES video_versions(id) ON DELETE CASCADE,
    feedback_text TEXT NOT NULL,
    parsed_feedback JSONB NOT NULL, -- Ex: { "pacing": "slow", "brightness": "increase" }
    applied BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger para atualização automática do campo updated_at na tabela jobs
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_jobs_modtime
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION update_modified_column();
