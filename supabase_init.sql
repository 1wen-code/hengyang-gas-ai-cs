-- 在 Supabase SQL Editor 中执行此脚本
-- https://app.supabase.com → 你的项目 → SQL Editor

CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    user_question TEXT,
    risk_level TEXT,
    category TEXT DEFAULT '紧急事件',
    status TEXT DEFAULT '处理中',
    handler TEXT DEFAULT '调度中心A组',
    user_ip TEXT DEFAULT '',
    user_id TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    created_at TEXT NOT NULL,
    user_question TEXT,
    ai_reply TEXT,
    mode TEXT,
    source TEXT
);

CREATE TABLE IF NOT EXISTS emergency_logs (
    id SERIAL PRIMARY KEY,
    created_at TEXT NOT NULL,
    risk_level TEXT,
    user_ip TEXT,
    ticket_id TEXT,
    user_question TEXT
);

-- 开启公共访问（让 REST API 可读写）
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE emergency_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "允许所有操作" ON tickets FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "允许所有操作" ON chat_logs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "允许所有操作" ON emergency_logs FOR ALL USING (true) WITH CHECK (true);
