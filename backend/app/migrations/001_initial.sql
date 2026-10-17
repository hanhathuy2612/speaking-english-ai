-- Initial schema: users and email tokens, practice history, lesson content.
--
-- Migration files are named NNN_name.sql and applied in name order by db.migrate()
-- (python -m scripts.migrate). Statements end with ';' at the end of a line; '--' lines are comments.
-- One small change per file. Never edit a file that has been applied: add a new one instead.
-- MySQL commits DDL at once, so a file that fails halfway is not undone, and it is rerun in full on the
-- next start. A non-idempotent file (e.g. ALTER ... ADD COLUMN) that failed halfway needs manual cleanup,
-- which is why the rule is one statement per file where possible.
-- Every table is utf8mb4_bin (ids and emails are case-sensitive).
-- CREATE TABLE IF NOT EXISTS lets a database made before migrations existed record this file as applied.

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,  -- lower case; the login name
    name VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,      -- scrypt$n$r$p$salt$hash (hash_password)
    role VARCHAR(20) NOT NULL DEFAULT 'user', -- 'user' | 'admin'
    verified_at VARCHAR(32),             -- NULL until the email address is confirmed
    disabled TINYINT(1) NOT NULL DEFAULT 0,
    created_at VARCHAR(32) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash VARCHAR(64) PRIMARY KEY,  -- sha256 of the token in the emailed link
    user_id INT NOT NULL,
    kind VARCHAR(20) NOT NULL,           -- 'verify' | 'reset'
    expires_at VARCHAR(32) NOT NULL,
    used_at VARCHAR(32),
    INDEX email_tokens_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    unit_id VARCHAR(100) NOT NULL,
    unit_title VARCHAR(255) NOT NULL,
    phrase_total INT NOT NULL,
    started_at VARCHAR(32) NOT NULL,
    completed TINYINT(1) NOT NULL DEFAULT 0,
    user_id INT,
    INDEX sessions_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS turns (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    created_at VARCHAR(32) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    source VARCHAR(20) NOT NULL,       -- 'voice' | 'text'
    unclear TINYINT(1) NOT NULL DEFAULT 0,
    words INT,
    wpm INT,
    wpm_speaking INT,
    long_pauses INT,
    avg_logprob DOUBLE,
    no_speech DOUBLE,
    used_phrases TEXT NOT NULL DEFAULT ('[]'),  -- JSON list of phrase indices used in this turn
    note TEXT,
    retry INT,
    stt_ms INT,
    first_audio_ms INT,
    audio VARCHAR(255),                -- recording file name in SAVE_AUDIO_DIR (services/recordings.py)
    INDEX turns_session_id (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS shadows (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    created_at VARCHAR(32) NOT NULL,
    target TEXT NOT NULL,
    heard TEXT NOT NULL,
    correct INT NOT NULL,              -- reference tokens heard correctly
    total INT NOT NULL,                -- reference tokens
    words INT,
    wpm_speaking INT,
    long_pauses INT,
    avg_logprob DOUBLE,
    INDEX shadows_session_id (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS retells (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_id INT NOT NULL,
    created_at VARCHAR(32) NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    words INT,
    original_words INT,                -- words of the first answer to the same question
    steps_done INT,
    steps_total INT,
    wpm_speaking INT,
    long_pauses INT,
    INDEX retells_session_id (session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS checks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,
    prompt_id VARCHAR(100) NOT NULL,
    prompt TEXT NOT NULL,
    text TEXT NOT NULL,
    words INT NOT NULL,
    duration_s DOUBLE NOT NULL,
    wpm INT,
    wpm_speaking INT,
    hesitations INT NOT NULL,          -- pauses > 0.7 s inside a sentence
    hesitations_per_100 DOUBLE,
    not_english TINYINT(1) NOT NULL,
    avg_logprob DOUBLE,
    passed INT NOT NULL,               -- targets met (docs/features/speaking-check.md)
    total INT NOT NULL,                -- number of targets
    stuck MEDIUMTEXT,                  -- JSON: hesitations with the words around them (check.stuck_points)
    review MEDIUMTEXT,                 -- JSON: the AI review asked for after the check (docs/features/talk-lessons.md)
    user_id INT,
    INDEX checks_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS talk_practice (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,
    source VARCHAR(20) NOT NULL,       -- 'talk' (practice after a talk lesson) | 'check' (retry after a check)
    ref VARCHAR(100) NOT NULL,         -- the talk id, or the check id
    prompt_id VARCHAR(100) NOT NULL,
    prompt TEXT NOT NULL,
    text TEXT NOT NULL,
    words INT NOT NULL,
    duration_s DOUBLE NOT NULL,
    wpm_speaking INT,                  -- NULL when not measurable, like checks
    hesitations INT NOT NULL,
    hesitations_per_100 DOUBLE,
    steps_done INT,                    -- frame steps said (talk practice)
    steps_total INT,
    user_id INT,
    INDEX talk_practice_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS drills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,
    set_id VARCHAR(100) NOT NULL,      -- docs/features/pronunciation-drills.md
    target TEXT NOT NULL,
    heard TEXT NOT NULL,
    correct INT NOT NULL,              -- reference tokens heard correctly
    total INT NOT NULL,
    focus_correct INT NOT NULL,        -- focus words heard correctly
    focus_total INT NOT NULL,
    avg_logprob DOUBLE,
    audio VARCHAR(255),                -- recording file name in SAVE_AUDIO_DIR, for "Nghe lại"
    user_id INT,
    INDEX drills_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS fluency (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,
    run VARCHAR(100) NOT NULL,         -- one 4/3/2 exercise (docs/features/fluency-432.md)
    round INT NOT NULL,                -- 1, 2, 3
    limit_s INT NOT NULL,
    prompt_id VARCHAR(100) NOT NULL,
    prompt TEXT NOT NULL,
    text TEXT NOT NULL,
    words INT NOT NULL,
    duration_s DOUBLE NOT NULL,
    wpm_speaking INT,                  -- NULL when not measurable, like checks
    hesitations INT NOT NULL,
    hesitations_per_100 DOUBLE,
    not_english TINYINT(1) NOT NULL,
    user_id INT,
    INDEX fluency_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS cards (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,
    kind VARCHAR(20) NOT NULL,         -- 'note' | 'phrase' | 'talk' (docs/features/review.md)
    session_id INT,
    turn_id INT UNIQUE,                -- note cards: undo removes them
    unit_id VARCHAR(100) NOT NULL,
    phrase_index INT,                  -- phrase cards
    question TEXT NOT NULL,
    said TEXT,                         -- note cards: the learner's original answer
    target TEXT NOT NULL,              -- the NOTE, or the phrase to use
    box INT NOT NULL DEFAULT 0,        -- Leitner box: 0 = new or forgotten
    due VARCHAR(32) NOT NULL,          -- YYYY-MM-DD
    reviews INT NOT NULL DEFAULT 0,
    lapses INT NOT NULL DEFAULT 0,
    suspended TINYINT(1) NOT NULL DEFAULT 0,
    UNIQUE (user_id, unit_id, phrase_index),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (turn_id) REFERENCES turns(id) ON DELETE CASCADE,
    user_id INT,
    INDEX cards_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS card_reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    card_id INT NOT NULL,
    created_at VARCHAR(32) NOT NULL,
    heard TEXT,                        -- NULL when the answer was revealed without speaking
    correct INT,
    total INT,
    result VARCHAR(20) NOT NULL,       -- 'good' | 'again' (the learner's own grade)
    INDEX card_reviews_card_id (card_id),
    FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS lesson_reads (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,
    unit_id VARCHAR(100) NOT NULL,     -- docs/features/lesson.md
    sentence INT NOT NULL,             -- index in the unit's lesson.sentences
    target TEXT NOT NULL,
    heard TEXT NOT NULL,
    correct INT NOT NULL,              -- reference tokens heard correctly
    total INT NOT NULL,
    avg_logprob DOUBLE,
    user_id INT,
    INDEX lesson_reads_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS lessons (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,   -- when the learner reached the end of the lesson part
    unit_id VARCHAR(100) NOT NULL,
    user_id INT,
    INDEX lessons_user (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS content_topics (
    id VARCHAR(100) PRIMARY KEY,
    position INT NOT NULL,
    data MEDIUMTEXT NOT NULL,          -- the topic as in units.json: {id, title, description}
    source VARCHAR(20) NOT NULL DEFAULT 'file', -- 'file' (follows units.json) | 'admin' (edited on the web)
    updated_at VARCHAR(32),
    updated_by INT,
    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS content_units (
    id VARCHAR(100) PRIMARY KEY,
    position INT NOT NULL,             -- roadmap order across all units
    data MEDIUMTEXT NOT NULL,          -- the unit as in units.json
    source VARCHAR(20) NOT NULL DEFAULT 'file',
    deleted TINYINT(1) NOT NULL DEFAULT 0,
    updated_at VARCHAR(32),
    updated_by INT,
    FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
