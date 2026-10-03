-- CampusNotes database setup (MySQL 8+)
-- Run:  mysql -u root -p < init.sql
--
-- WARNING: this script DROPS and recreates all CampusNotes tables.
-- Re-running it resets the database to the seed data below.
--
-- DEMO CREDENTIALS (local demo only, never use in production):
--   admin   : admin@campusnotes.demo   / Admin@123
--   student : student@campusnotes.demo / Student@123
-- password_hash values are Werkzeug generate_password_hash() output (scrypt),
-- so they can be verified with werkzeug.security.check_password_hash().

CREATE DATABASE IF NOT EXISTS campusnotes
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE campusnotes;

-- Drop in reverse dependency order so foreign keys do not block the drops.
DROP TABLE IF EXISTS notes;
DROP TABLE IF EXISTS units;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS semesters;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS users;

-- ---------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------

CREATE TABLE users (
  id            INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name          VARCHAR(100) NOT NULL,
  email         VARCHAR(255) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          ENUM('student', 'admin') NOT NULL DEFAULT 'student',
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;

CREATE TABLE courses (
  id   INT UNSIGNED NOT NULL AUTO_INCREMENT,
  name VARCHAR(150) NOT NULL,
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE semesters (
  id        INT UNSIGNED NOT NULL AUTO_INCREMENT,
  course_id INT UNSIGNED NOT NULL,
  number    TINYINT UNSIGNED NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_semesters_course_number (course_id, number),
  CONSTRAINT fk_semesters_course
    FOREIGN KEY (course_id) REFERENCES courses (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE subjects (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semester_id INT UNSIGNED NOT NULL,
  name        VARCHAR(150) NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_subjects_semester
    FOREIGN KEY (semester_id) REFERENCES semesters (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE units (
  id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  subject_id INT UNSIGNED NOT NULL,
  title      VARCHAR(200) NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_units_subject
    FOREIGN KEY (subject_id) REFERENCES subjects (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE notes (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  title          VARCHAR(200) NOT NULL,
  description    TEXT NULL,
  unit_id        INT UNSIGNED NOT NULL,
  uploader_id    INT UNSIGNED NOT NULL,
  file_path      VARCHAR(255) NOT NULL,
  file_type      VARCHAR(20) NOT NULL DEFAULT 'pdf',
  status         ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  download_count INT UNSIGNED NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  CONSTRAINT fk_notes_unit
    FOREIGN KEY (unit_id) REFERENCES units (id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_notes_uploader
    FOREIGN KEY (uploader_id) REFERENCES users (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------
-- Seed data
-- ---------------------------------------------------------------

INSERT INTO users (id, name, email, password_hash, role) VALUES
  (1, 'Demo Admin',   'admin@campusnotes.demo',
   'scrypt:32768:8:1$bhKu13PNtxlZL6XP$623e6dcfc8b80322c3746d384fe325e2452f01ea63a065c3023cec90d2dc24a4ee433ccaaaf6b034f6f4dc9024f365a2eb9ff2c238c531e53948f0a76bab6e15',
   'admin'),
  (2, 'Demo Student', 'student@campusnotes.demo',
   'scrypt:32768:8:1$bHx7ZhY2YP9nsVI3$7b5c239e6fd14272afd6c8caf4de26eefb917f15d06cdc8ae2f5b91e483adab0ea7537cbdbc83c99d11542987d6a65d1eff02f2d1a0dca340aeedf0db995d72c',
   'student');

INSERT INTO courses (id, name) VALUES
  (1, 'BCA');

INSERT INTO semesters (id, course_id, number) VALUES
  (1, 1, 1),
  (2, 1, 2);

INSERT INTO subjects (id, semester_id, name) VALUES
  (1, 1, 'Programming in C'),
  (2, 1, 'Computer Fundamentals'),
  (3, 2, 'Data Structures'),
  (4, 2, 'Database Management Systems');

INSERT INTO units (id, subject_id, title) VALUES
  (1, 1, 'Unit 1: Introduction to C Programming'),
  (2, 1, 'Unit 2: Control Statements and Loops'),
  (3, 2, 'Unit 1: Number Systems'),
  (4, 3, 'Unit 1: Arrays and Linked Lists'),
  (5, 3, 'Unit 2: Stacks and Queues'),
  (6, 4, 'Unit 1: Introduction to DBMS and ER Model'),
  (7, 4, 'Unit 2: SQL Basics');

-- file_path is relative to backend/. The PDFs themselves are added in a later stage.
INSERT INTO notes
  (id, title, description, unit_id, uploader_id, file_path, file_type, status, download_count) VALUES
  (1, 'Linked List Complete Notes',
   'Singly, doubly and circular linked lists with diagrams and C code.',
   4, 2, 'seed_files/linked_list_notes.pdf', 'pdf', 'approved', 12),
  (2, 'Stack and Queue Quick Revision',
   'One-page revision of stack and queue operations with exam questions.',
   5, 2, 'seed_files/stack_queue_revision.pdf', 'pdf', 'approved', 7),
  (3, 'SQL Joins Cheat Sheet',
   'INNER, LEFT, RIGHT and FULL joins explained with examples.',
   7, 1, 'seed_files/sql_joins_cheatsheet.pdf', 'pdf', 'approved', 5),
  (4, 'ER Model Handwritten Notes',
   'Entities, attributes, relationships and ER diagram examples.',
   6, 2, 'seed_files/er_model_notes.pdf', 'pdf', 'pending', 0),
  (5, 'C Loops Practice Questions',
   'Practice questions on for, while and do-while loops.',
   2, 2, 'seed_files/c_loops_practice.pdf', 'pdf', 'rejected', 0);
