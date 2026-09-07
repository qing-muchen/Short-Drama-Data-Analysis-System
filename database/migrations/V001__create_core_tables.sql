-- Migration V001: core and master tables
USE short_drama_analysis;
SET time_zone = '+00:00';

CREATE TABLE users (
  user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(100) NULL,
  role_code VARCHAR(32) NOT NULL DEFAULT 'USER',
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  last_login_at DATETIME(6) NULL,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (user_id),
  CONSTRAINT uq_users_username UNIQUE (username),
  CONSTRAINT chk_users_username_nonempty CHECK (CHAR_LENGTH(TRIM(username)) > 0),
  CONSTRAINT chk_users_password_hash_nonempty CHECK (CHAR_LENGTH(TRIM(password_hash)) > 0),
  CONSTRAINT chk_users_role CHECK (role_code IN ('ADMINISTRATOR', 'USER')),
  CONSTRAINT chk_users_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE dramas (
  drama_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  drama_code VARCHAR(32) NOT NULL,
  drama_name VARCHAR(200) NOT NULL,
  synopsis TEXT NULL,
  episode_count SMALLINT UNSIGNED NULL,
  episode_duration_seconds INT UNSIGNED NULL,
  premiere_date DATE NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (drama_id),
  CONSTRAINT uq_dramas_code UNIQUE (drama_code),
  CONSTRAINT chk_dramas_code_nonempty CHECK (CHAR_LENGTH(TRIM(drama_code)) > 0),
  CONSTRAINT chk_dramas_name_nonempty CHECK (CHAR_LENGTH(TRIM(drama_name)) > 0),
  CONSTRAINT chk_dramas_episode_count CHECK (episode_count IS NULL OR episode_count > 0),
  CONSTRAINT chk_dramas_episode_duration CHECK (episode_duration_seconds IS NULL OR episode_duration_seconds > 0),
  CONSTRAINT chk_dramas_status CHECK (status IN ('DRAFT', 'SERIALIZING', 'COMPLETED', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE actors (
  actor_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  actor_name VARCHAR(100) NOT NULL,
  profile_note TEXT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (actor_id),
  CONSTRAINT chk_actors_name_nonempty CHECK (CHAR_LENGTH(TRIM(actor_name)) > 0),
  CONSTRAINT chk_actors_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE directors (
  director_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  director_name VARCHAR(100) NOT NULL,
  profile_note TEXT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (director_id),
  CONSTRAINT chk_directors_name_nonempty CHECK (CHAR_LENGTH(TRIM(director_name)) > 0),
  CONSTRAINT chk_directors_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE companies (
  company_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  company_name VARCHAR(200) NOT NULL,
  description TEXT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (company_id),
  CONSTRAINT chk_companies_name_nonempty CHECK (CHAR_LENGTH(TRIM(company_name)) > 0),
  CONSTRAINT chk_companies_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE platforms (
  platform_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  platform_name VARCHAR(100) NOT NULL,
  description TEXT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (platform_id),
  CONSTRAINT uq_platforms_name UNIQUE (platform_name),
  CONSTRAINT chk_platforms_name_nonempty CHECK (CHAR_LENGTH(TRIM(platform_name)) > 0),
  CONSTRAINT chk_platforms_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE tags (
  tag_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tag_name VARCHAR(100) NOT NULL,
  status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (tag_id),
  CONSTRAINT uq_tags_name UNIQUE (tag_name),
  CONSTRAINT chk_tags_name_nonempty CHECK (CHAR_LENGTH(TRIM(tag_name)) > 0),
  CONSTRAINT chk_tags_status CHECK (status IN ('ACTIVE', 'INACTIVE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
