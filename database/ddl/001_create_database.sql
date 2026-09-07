-- TASK-P3-06R / MySQL 8.x bootstrap
-- Run this file once before the ordered DDL or migrations.

CREATE DATABASE IF NOT EXISTS short_drama_analysis
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

USE short_drama_analysis;
SET NAMES utf8mb4 COLLATE utf8mb4_0900_ai_ci;
SET time_zone = '+00:00';
