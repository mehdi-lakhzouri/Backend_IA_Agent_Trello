-- ================================
-- SCRIPT D'INITIALISATION MYSQL POUR LE DÉVELOPPEMENT
-- ================================

-- Création de la base de données si elle n'existe pas
CREATE DATABASE IF NOT EXISTS talanagent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Sélection de la base de données
USE talanagent;

-- Création de l'utilisateur avec permissions étendues
CREATE USER IF NOT EXISTS 'dev_user'@'%' IDENTIFIED BY 'dev_pwd';

-- Grant des permissions pour l'utilisateur de développement
GRANT ALL PRIVILEGES ON talanagent.* TO 'dev_user'@'%';
GRANT ALL PRIVILEGES ON *.* TO 'dev_user'@'%' WITH GRANT OPTION;

-- Mise à jour des permissions
FLUSH PRIVILEGES;

-- Message de confirmation
SELECT 'Base de données talanagent initialisée avec succès pour le développement' AS message;
