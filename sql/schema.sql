-- ETF Rebalance ETL - MySQL 스키마 DDL
-- 대상 DB: etf_rebalance (initSchema.py에서 CREATE DATABASE 수행)

-- 1. ETF 마스터 정보
CREATE TABLE IF NOT EXISTS etf_master (
    etf_code VARCHAR(10) PRIMARY KEY,
    etf_name VARCHAR(100) NOT NULL,
    issuer VARCHAR(50),
    benchmark_index VARCHAR(100),
    listing_date DATE,
    expense_ratio DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. 일일 NAV / 가격 시계열 (KIS API 중심, 증분)
CREATE TABLE IF NOT EXISTS etf_nav_daily (
    etf_code VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    nav DECIMAL(15,4),
    close_price DECIMAL(15,4),
    volume BIGINT,
    aum_estimate DECIMAL(20,2),
    change_rate DECIMAL(7,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (etf_code, trade_date),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Holdings Snapshot (지분 변동 시계열 핵심)
CREATE TABLE IF NOT EXISTS etf_holdings_snapshot (
    snapshot_date DATE NOT NULL,
    etf_code VARCHAR(10) NOT NULL,
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(100),
    weight_pct DECIMAL(6,3),
    shares BIGINT,
    market_value_krw DECIMAL(20,2),
    rank_in_portfolio INT,
    sector VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (snapshot_date, etf_code, stock_code),
    INDEX idx_etf_date (etf_code, snapshot_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. 리밸런싱 이벤트 로그 (변동 내역 요약)
CREATE TABLE IF NOT EXISTS rebalancing_event (
    event_id INT AUTO_INCREMENT PRIMARY KEY,
    event_date DATE NOT NULL,
    etf_code VARCHAR(10) NOT NULL,
    event_type ENUM('REGULAR', 'INDEX_REBALANCE', 'ADJUSTMENT') DEFAULT 'INDEX_REBALANCE',
    description TEXT,
    added_stocks_count INT DEFAULT 0,
    removed_stocks_count INT DEFAULT 0,
    changed_weights_count INT DEFAULT 0,
    total_turnover_pct DECIMAL(6,3),
    source VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_event (event_date, etf_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;