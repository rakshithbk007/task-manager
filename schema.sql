-- Run this once in MySQL Workbench / the mysql command line
CREATE DATABASE IF NOT EXISTS taskdb;
USE taskdb;

-- The app also creates this table automatically on startup
CREATE TABLE IF NOT EXISTS tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    done TINYINT(1) NOT NULL DEFAULT 0
);
