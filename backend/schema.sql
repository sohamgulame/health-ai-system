CREATE DATABASE IF NOT EXISTS health_db;
USE health_db;

CREATE TABLE IF NOT EXISTS readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    temperature FLOAT,
    heart_rate INT,
    spo2 INT,
    prediction TEXT,
    advice TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
