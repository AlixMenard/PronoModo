CREATE DATABASE IF NOT EXISTS pronosmodo;

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";

CREATE TABLE `bets`
(
    `id`       int(11) PRIMARY KEY AUTO_INCREMENT,
    `modo`     int(11)  NOT NULL,
    `matchid`  int(11)  NOT NULL,
    `team1bet` int(11)  NOT NULL,
    `team2bet` int(11)  NOT NULL,
    `date`     datetime NOT NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci;

CREATE TABLE `matches`
(
    `tournament` varchar(250) NOT NULL,
    `team1`      varchar(10)  NOT NULL,
    `team2`      varchar(10)  NOT NULL,
    `score1`     int(11)      NOT NULL,
    `score2`     int(11)      NOT NULL,
    `date`       datetime     NOT NULL,
    `status`     varchar(10)  NOT NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci;

CREATE TABLE `modos`
(
    `id`        int(11) PRIMARY KEY AUTO_INCREMENT,
    `name`      varchar(64) NOT NULL,
    `bets`      int(11)     NOT NULL DEFAULT 0,
    `perfect`   int(11)     NOT NULL DEFAULT 0,
    `victories` int(11)     NOT NULL DEFAULT 0,
    `avg_rank`  float                DEFAULT NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci;


CREATE TABLE `scores`
(
    `modo`       int(11)      NOT NULL,
    `tournament` varchar(250) NOT NULL,
    `num_bets`   int(11)      NOT NULL,
    `score`      int(11)      NOT NULL,
    `perfect`    int(11)      NOT NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci;

CREATE TABLE `tournaments`
(
    `id`    int(11) PRIMARY KEY AUTO_INCREMENT,
    `name`  varchar(250) NOT NULL,
    `start` datetime     NOT NULL,
    `end`   datetime     NOT NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_general_ci;


ALTER TABLE `matches`
    ADD UNIQUE KEY `team1` (`team1`, `team2`, `date`);

--
-- Indexes for table `modos`
--
ALTER TABLE `modos`
    ADD UNIQUE KEY `name` (`name`);

--
-- Indexes for table `scores`
--
ALTER TABLE `scores`
    ADD PRIMARY KEY (`modo`, `tournament`);
