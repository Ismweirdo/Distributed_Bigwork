-- Demo data (only for H2; in production, use application.yml spring.sql.init.mode=never)
-- Password is BCrypt hash of "123456"
INSERT INTO users (username, password, nickname, status) VALUES
('alice', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5EHs', 'Alice', 0),
('bob', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5EHs', 'Bob', 0),
('charlie', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iAt6Z5EHs', 'Charlie', 0);
