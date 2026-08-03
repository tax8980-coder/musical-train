-- =========================================================
-- 세무법인 지율 — 리드(상담 신청) 저장 스키마
-- SQLite 기준. 다른 DBMS로 이전할 경우 타입만 조정하면 됩니다.
--   INTEGER PRIMARY KEY AUTOINCREMENT -> BIGSERIAL / BIGINT AUTO_INCREMENT
--   TEXT                              -> VARCHAR / TEXT
--   INTEGER (0/1)                     -> BOOLEAN
-- =========================================================

CREATE TABLE IF NOT EXISTS leads (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,             -- 내부 식별자
  created_at    TEXT    NOT NULL,                              -- 접수 일시 (KST, ISO 8601)
  receipt_no    TEXT    NOT NULL UNIQUE,                       -- 접수번호 YY-MMDD-###
  name          TEXT    NOT NULL,                              -- 성함
  company       TEXT,                                          -- 회사명/상호 (선택)
  phone         TEXT    NOT NULL,                              -- 연락처 (하이픈 포함 저장)
  email         TEXT    NOT NULL,                              -- 이메일
  inquiry_type  TEXT    NOT NULL,                              -- 문의 유형
  message       TEXT    NOT NULL,                              -- 문의 내용
  privacy_agreed INTEGER NOT NULL DEFAULT 0                    -- 개인정보 수집·이용 동의 (0/1)
                 CHECK (privacy_agreed IN (0, 1)),
  agreed_at     TEXT,                                          -- 동의 시각 (ISO 8601)
  status        TEXT    NOT NULL DEFAULT '신규'                -- 진행 상태
                 CHECK (status IN ('신규', '연락완료', '상담진행', '수임', '보류')),
  assignee      TEXT,                                          -- 담당자
  memo          TEXT,                                          -- 내부 메모
  source        TEXT                                           -- 유입 경로 (예: website-landing)
);

CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_status     ON leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_receipt_no ON leads (receipt_no);

-- =========================================================
-- 세무칼럼 조회수 (slug별 누적)
-- =========================================================
CREATE TABLE IF NOT EXISTS post_views (
  slug        TEXT    PRIMARY KEY,                 -- posts.json 의 slug
  views       INTEGER NOT NULL DEFAULT 0,          -- 누적 조회수
  updated_at  TEXT                                 -- 마지막 조회 시각 (KST, ISO 8601)
);
