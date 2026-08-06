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

-- =========================================================
-- 방문 통계 (일자별 집계) — 관리자 통계용
-- category: 'pv'(사람 페이지뷰 합계, name='total'), 'page'(경로별 name=path),
--           'visitor'(순방문 추정 name='unique'), 'ai'(AI 크롤러 name=봇),
--           'search'(검색 크롤러 name=봇), 'bot'(기타 봇 name=봇)
-- =========================================================
CREATE TABLE IF NOT EXISTS stat_counts (
  day       TEXT    NOT NULL,                       -- YYYY-MM-DD (KST)
  category  TEXT    NOT NULL,
  name      TEXT    NOT NULL,                       -- 경로/봇이름/'total'/'unique'/'__total__'
  hits      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, category, name)
);
CREATE INDEX IF NOT EXISTS idx_stat_counts_day ON stat_counts (day DESC);

-- 순 방문자(추정) 중복 제거용 (당일 IP 해시). 스냅샷 대상 아님(재배포 시 초기화 허용).
CREATE TABLE IF NOT EXISTS visitor_seen (
  day    TEXT NOT NULL,
  vhash  TEXT NOT NULL,
  PRIMARY KEY (day, vhash)
);
