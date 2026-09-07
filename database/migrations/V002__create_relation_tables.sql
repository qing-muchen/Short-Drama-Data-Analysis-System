-- Migration V002: relationship and release tables
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE drama_actors (
  drama_actor_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NOT NULL,
  actor_id BIGINT UNSIGNED NOT NULL,
  role_name VARCHAR(100) NULL,
  role_type VARCHAR(32) NOT NULL DEFAULT 'OTHER',
  billing_order SMALLINT UNSIGNED NULL,
  relation_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (drama_actor_id),
  CONSTRAINT uq_drama_actors_pair UNIQUE (drama_id, actor_id),
  CONSTRAINT uq_drama_actors_billing UNIQUE (drama_id, billing_order),
  CONSTRAINT fk_drama_actors_drama FOREIGN KEY (drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_drama_actors_actor FOREIGN KEY (actor_id) REFERENCES actors (actor_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_drama_actors_role_type CHECK (role_type IN ('LEAD', 'SUPPORTING', 'GUEST', 'OTHER')),
  CONSTRAINT chk_drama_actors_billing CHECK (billing_order IS NULL OR billing_order > 0),
  CONSTRAINT chk_drama_actors_status CHECK (relation_status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE drama_directors (
  drama_director_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NOT NULL,
  director_id BIGINT UNSIGNED NOT NULL,
  relation_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (drama_director_id),
  CONSTRAINT uq_drama_directors_pair UNIQUE (drama_id, director_id),
  CONSTRAINT fk_drama_directors_drama FOREIGN KEY (drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_drama_directors_director FOREIGN KEY (director_id) REFERENCES directors (director_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_drama_directors_status CHECK (relation_status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE drama_companies (
  drama_company_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NOT NULL,
  company_id BIGINT UNSIGNED NOT NULL,
  relation_type VARCHAR(32) NOT NULL,
  relation_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (drama_company_id),
  CONSTRAINT uq_drama_companies_role UNIQUE (drama_id, company_id, relation_type),
  CONSTRAINT fk_drama_companies_drama FOREIGN KEY (drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_drama_companies_company FOREIGN KEY (company_id) REFERENCES companies (company_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_drama_companies_type CHECK (relation_type IN ('PRODUCER', 'PRODUCTION', 'DISTRIBUTOR', 'CO_PRODUCTION', 'OTHER')),
  CONSTRAINT chk_drama_companies_status CHECK (relation_status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE drama_tags (
  drama_tag_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NOT NULL,
  tag_id BIGINT UNSIGNED NOT NULL,
  relation_status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (drama_tag_id),
  CONSTRAINT uq_drama_tags_pair UNIQUE (drama_id, tag_id),
  CONSTRAINT fk_drama_tags_drama FOREIGN KEY (drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_drama_tags_tag FOREIGN KEY (tag_id) REFERENCES tags (tag_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_drama_tags_status CHECK (relation_status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE drama_platforms (
  drama_platform_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_id BIGINT UNSIGNED NOT NULL,
  platform_id BIGINT UNSIGNED NOT NULL,
  platform_drama_code VARCHAR(100) NULL,
  online_at DATETIME(6) NULL,
  page_url VARCHAR(2048) NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'PLANNED',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (drama_platform_id),
  CONSTRAINT uq_drama_platforms_pair UNIQUE (drama_id, platform_id),
  CONSTRAINT uq_drama_platforms_external_code UNIQUE (platform_id, platform_drama_code),
  CONSTRAINT fk_drama_platforms_drama FOREIGN KEY (drama_id) REFERENCES dramas (drama_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT fk_drama_platforms_platform FOREIGN KEY (platform_id) REFERENCES platforms (platform_id) ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT chk_drama_platforms_status CHECK (status IN ('PLANNED', 'ONLINE', 'OFFLINE')),
  CONSTRAINT chk_drama_platforms_online_time CHECK (status = 'PLANNED' OR online_at IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
