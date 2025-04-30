CREATE DATABASE knowledge_mapping;

USE knowledge_mapping;

DROP TABLE IF EXISTS relationships;
DROP TABLE IF EXISTS links;
DROP TABLE IF EXISTS nodes;
DROP TABLE IF EXISTS maps;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS editors;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL, 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE maps (
    map_id VARCHAR(36) PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE nodes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    map_id VARCHAR(36) NOT NULL,  
    label VARCHAR(255) NOT NULL,  
    description TEXT,
    position_x FLOAT DEFAULT 0, 
    position_y FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (map_id) REFERENCES maps(map_id) ON DELETE CASCADE
);

CREATE TABLE links (
    id INT AUTO_INCREMENT PRIMARY KEY,
    map_id VARCHAR(255) NOT NULL,
    source_node_id INT NOT NULL,
    target_node_id INT NOT NULL,
    FOREIGN KEY (map_id) REFERENCES maps(map_id) ON DELETE CASCADE,
    FOREIGN KEY (source_node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE editors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    map_id VARCHAR(36), 
    user_id INT,
    edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (map_id) REFERENCES maps(map_id) ON DELETE CASCADE, 
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,   
    UNIQUE(map_id, user_id)  
);

CREATE TABLE ratings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    map_id VARCHAR(255),
    user_id INT,
    rating INT CHECK (rating BETWEEN 1 AND 5),
    UNIQUE (map_id, user_id)
);

CREATE TABLE shared_maps (
    id INT AUTO_INCREMENT PRIMARY KEY,
    map_id VARCHAR(36) NOT NULL,
    owner_id INT NOT NULL,
    shared_with_id INT NOT NULL,
    shared_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (map_id) REFERENCES maps(map_id) ON DELETE CASCADE,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(map_id, shared_with_id)
);
