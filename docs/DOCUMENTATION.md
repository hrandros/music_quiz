# Rock Music Quiz System - Comprehensive Technical Documentation

## Executive Summary

The **Rock Music Quiz** platform is a full-stack, real-time interactive quiz application designed for hosting live music quizzes in venues or online events. The system consists of:
1. **Desktop Admin Launcher** (`local_launcher.py`): A PySide6 desktop GUI for quiz hosts providing quiz management, local MP3/video scanning and importing, audio waveform editing, live gameplay control, real-time host grading, and database management.
2. **Web Application & Game Server** (`app.py`): A Flask and Flask-SocketIO server serving mobile web clients for players (`/player`) and TV screen displays (`/screen`) for public leaderboard and media presentation.
3. **Core Application Logic** (`musicquiz/`): Relational ORM models (SQLAlchemy), grading services, question/quiz handlers, file import utilities, and real-time Socket.IO event handlers.

---

## 1. System Architecture & High-Level Overview

```
                          ┌──────────────────────────┐
                          │   PySide6 Desktop Admin  │
                          │   (Host Launcher GUI)    │
                          └─────────────┬────────────┘
                                        │
                         Flask-SocketIO / REST Calls
                                        │
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            Flask Game Server (`app.py`)                       │
│                                                                              │
│ ┌──────────────────┐    ┌────────────────────┐    ┌────────────────────────┐ │
│ │  Routes Engine   │    │  Socket.IO Engine  │    │  Services Layer        │ │
│ │  - Admin BP      │    │  - Admin Events    │    │  - Grading Service     │ │
│ │  - Public BP     │    │  - Player Events   │    │  - Question Service    │ │
│ │  - Screen BP     │    │  - Screen Events   │    │  - Quiz Service        │ │
│ │  - File BP       │    │                    │    │  - Deezer API Service  │ │
│ └──────────────────┘    └────────────────────┘    └────────────────────────┘ │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                      SQLAlchemy ORM   │   Flask-SocketIO Websockets
                                       ▼               ▲
                           ┌──────────────────────┐    │
                           │   SQLite / Postgres  │    │
                           │   Database (kviz.db) │    │
                           └──────────────────────┘    │
                                                       │
                           ┌───────────────────────────┴───────────────────────────┐
                           │                                                       │
                           ▼                                                       ▼
            ┌─────────────────────────────┐                         ┌─────────────────────────────┐
            │     TV Display (`/screen`)  │                         │    Player Web (`/player`)   │
            │  - Live Timer & Audio/Video │                         │  - Answer Submission Inputs │
            │  - Leaderboard & Correct Ans│                         │  - Anti-Cheat Monitoring    │
            └─────────────────────────────┘                         └─────────────────────────────┘
```

---

## 2. Database Models & Schema Specifications

Defined in `musicquiz/models/`:

| Model | Table Name | Key Fields | Description |
|---|---|---|---|
| **`Quiz`** | `quiz` | `id`, `title`, `event_date`, `date_created`, `is_active` | Represents a quiz session. Only one quiz can be active (`is_active=True`) at a time. |
| **`Question`** | `question` | `id`, `quiz_id`, `round_number`, `position`, `type`, `duration` | Core question model. Uniquely indexed by `(quiz_id, round_number, position)`. Types: `audio`, `video`, `text`, `text_multiple`, `simultaneous`. |
| **`Song`** | `song` | `id`, `question_id`, `filename`, `artist`, `title`, `start_time` | Details for `audio` questions. Stores audio clip filename in `songs/`, artist, title, and clip start offset in seconds. |
| **`Video`** | `video` | `id`, `question_id`, `filename`, `artist`, `title`, `start_time` | Details for `video` questions. Stores video clip filename in `videos/`, artist, title, and start offset. |
| **`TextQuestion`** | `text_question` | `id`, `question_id`, `question_text`, `answer_text` | Details for standard text open-ended questions. |
| **`TextMultiple`** | `text_multiple` | `id`, `question_id`, `question_text`, `choices`, `correct_index` | Details for 4-choice multiple choice questions. `choices` stored as JSON array string via `get_choices()` / `set_choices()`. |
| **`SimultaneousQuestion`** | `simultaneous_question` | `id`, `question_id`, `filename`, `artist`, `title`, `start_time`, `extra_question`, `extra_answer` | Details for simultaneous audio + text questions (e.g. "Finish the lyrics"). |
| **`Player`** | `player` | `id`, `name`, `pin`, `score`, `last_active` | Registered team/player record. `name` is unique. |
| **`Answer`** | `answer` | `id`, `player_name`, `round_number`, `question_id`, `artist_guess`, `title_guess`, `extra_guess`, `choice_selected`, `artist_points`, `title_points`, `extra_points`, `is_locked`, `submission_time`, `timestamp` | Submission record. Uniquely constrained by `(player_name, question_id)`. Tracks guesses, calculated points (0.0, 0.5, 1.0), and submission speed into question duration. |
| **`LogEntry`** | `log_entries` | `id`, `created_at`, `source`, `message` | Application logging table for auditing server/socket/UI events. |

---

## 3. Core Services & Implemented Logic

Located in `musicquiz/services/`:

### 3.1 Grading Service (`grading_service.py`)
- **Text Auto-Grading (`auto_grade_answer`)**:
  - Normalizes text by removing parenthetical metadata `(...)`, `feat`/`ft`, punctuation, multiple spaces, and folding diacritics/accents to base ASCII (`_fold_accents`).
  - Computes fuzzy string similarity using `difflib.SequenceMatcher`.
  - Grants substring bonus (+0.5) if one string is contained within the other.
  - Scores artist and title independently:
    - **1.0 point**: Similarity ratio $\ge 0.82$ (artist) / $\ge 0.84$ (title).
    - **0.5 points**: Similarity ratio $\ge 0.55$ (artist) / $\ge 0.58$ (title).
    - **0.0 points**: Otherwise.
- **Time Bonus Calculation (`calculate_time_bonus`)**:
  - Implements interval-based time multipliers for multiple-choice questions over total duration (e.g., 30s):
    - Interval 1 ($0 - \frac{1}{5}$ duration, 0–6s): Multiplier **1.0**
    - Interval 2 ($\frac{1}{5} - \frac{2}{5}$ duration, 6–12s): Multiplier **0.8**
    - Interval 3 ($\frac{2}{5} - \frac{3}{5}$ duration, 12–18s): Multiplier **0.6**
    - Interval 4 ($\frac{3}{5} - \frac{4}{5}$ duration, 18–24s): Multiplier **0.4**
    - Interval 5 ($\frac{4}{5} - \frac{5}{5}$ duration, 24–30s): Multiplier **0.2**
- **Question Type Dispatcher (`grade_answer_for_question`)**:
  - Dynamically routes scoring based on question type (`text_multiple`, `text`, `video`, `simultaneous`, `audio`).

### 3.2 Question Service (`question_service.py`)
- **`get_question_media(question)`**: Resolves streaming URL (`/stream_song/<filename>` or `/stream_video/<filename>`) and start time.
- **`get_question_display(question)`**: Transforms question ORM entity into display dictionary for UI lists and screen headers.
- **`get_question_unlock_payload(question)`**: Formats payload sent to players when input unlocks (contains choices, question text, extra questions).
- **`get_question_answer_key(question)`**: Extracts expected answer key for intermission display and player feedback.

### 3.3 Quiz Service (`quiz_service.py`)
- **`recompute_scores()`**: Sums `artist_points + title_points + extra_points` for all answers per player and updates `player.score`.
- **`get_active_quiz()`**: Returns current active `Quiz` instance.

### 3.4 File Import Service (`file_import_service.py`)
- **`scan_mp3_folder(folder_path)`**: Recursively scans folder and returns list of relative `.mp3` paths.
- **`import_song_file(source_path, filename)`**: Copies audio file to local `songs/` folder using `secure_filename`.
- **`file_md5(path)`**: Calculates MD5 hash for duplicate file verification.

### 3.5 Deezer Service (`deezer_service.py`)
- **`query_deezer_metadata(query)`**: Calls Deezer public REST API (`https://api.deezer.com/search?q=...`) to return top track result (artist name, title, album, audio preview URL) during setup verification.

---

## 4. HTTP Routes & Endpoints

Defined in `musicquiz/routes/`:

1. **`admin_bp`** (`/admin`):
   - `GET/POST /admin/login`: Admin authentication against `Config.ADMIN_PASSWORD`.
   - `GET /admin/live`: Web live control view.
   - `GET /admin/setup`: Web quiz setup view.
   - `POST /admin/switch_quiz`: Switches current active quiz.
   - `POST /admin/create_quiz`: Creates new quiz.
   - `POST /admin/api_check_deezer`: Performs Deezer search lookup for track title/artist verification.
   - `POST /admin/scan_local_folder`: Scans local folder path for `.mp3` files.
   - `POST /admin/import_external_song`: Imports audio file and registers question.
   - `POST /admin/update_song`: Updates artist, title, start_time, duration for audio question.
   - `POST /admin/remove_song`: Deletes question and associated answers.
   - `POST /admin/reorder_songs`: Batch updates question positions after drag-and-drop reordering.
   - `POST /admin/api/update_score`: Updates score values (`0`, `0.5`, `1.0`) for specific answer fields.
   - `POST /admin/create_text_question`, `/admin/create_multiple_choice_question`, `/admin/create_video_question`, `/admin/create_simultaneous_question`: Endpoint handlers for creating specific question types.
2. **`public_bp`**:
   - `GET /`: Landing page.
   - `GET /player`: Player client web interface.
3. **`screen_bp`**:
   - `GET /screen`: TV display presentation interface.
4. **`file_bp`**:
   - `GET /images/<filename>`: Serves static image assets.
   - `GET /stream_song/<path:filename>`: Streams audio files from `songs/`.
   - `GET /stream_video/<path:filename>`: Streams video files from `videos/` with path traversal protection.

---

## 5. Real-Time Socket.IO Architecture & State Machine

Managed in `musicquiz/sockets/`:

```
                    ┌────────────────────────────┐
                    │  quiz_settings Global State│
                    │ - registrations_open       │
                    │ - quiz_started             │
                    │ - quiz_paused              │
                    │ - current_question_id      │
                    │ - current_question_phase   │
                    └──────────────┬─────────────┘
                                   │
               ┌───────────────────┴───────────────────┐
               │  Automated Sequence Lifecycle Loop     │
               │  (`auto_quiz_sequence`)               │
               └───────────────────┬───────────────────┘
                                   │
 1. Countdown Phase (30s)          │ `round_countdown_start` -> TV & Player
 ──────────────────────────────────┼────────────────────────────────────────
 2. Question Active Phase          │ `play_audio` (media stream + duration)
    (e.g., 30s)                    │ `player_unlock_input`
                                   │ `tv_start_timer`
                                   │ `timer_update` (1s server heartbeat)
 ──────────────────────────────────┼────────────────────────────────────────
 3. Question Locked Phase          │ `player_lock_input`
 ──────────────────────────────────┼────────────────────────────────────────
 4. Intermission/Answer Phase (15s)│ `screen_show_correct` -> TV
                                   │ `player_show_answer` -> Player
                                   │ [Background Auto-Grading & Leaderboard]
 ──────────────────────────────────┼────────────────────────────────────────
 5. Next Question / Round Summary  │ `screen_show_round_summary`
                                   │ `player_show_round_summary`
                                   │ `admin_round_finished`
```

### Key Socket Events Summary

- **Admin Events (`admin_events.py`)**:
  - `admin_start_auto_run`: Initiates round sequence with 30s countdown wrapper (`auto_quiz_sequence_with_countdown`).
  - `admin_play_song`: Triggers playback for single question.
  - `admin_toggle_pause`: Toggles pause state (`quiz_settings["quiz_paused"]`) and broadcasts `quiz_pause_state`.
  - `admin_update_score`: Handles host manual score override for artist/title/extra fields.
  - `admin_finalize_round`: Performs final auto-grading for all answers in round and broadcasts leaderboard.
  - `admin_toggle_registrations`: Enables/disables registration and shows welcome screen with QR code URL on TV screen.
  - `admin_lock_player` / `admin_delete_player`: Player moderation events.
- **Player Events (`player_events.py`)**:
  - `player_join`: Registers player with team name and 4-digit PIN. Reconnects late joiners during active questions.
  - `player_submit_answer`: Records player guesses (`artist`, `title`, `extra`, `choice`) and submission timestamp.
  - `player_cheat_detected`: Handles client anti-cheat trigger (window blur, tab switch, split screen), adds player to `locked_players`.
  - `player_activity_status`: Updates live online/away status.
- **Screen Events (`screen_events.py`)**:
  - `screen_ready`: Triggers initial leaderboard emission to TV display.

---

## 6. PySide6 Admin Desktop Launcher (`local_launcher.py` & `admin_ui/`)

The desktop launcher is built with PySide6 (Qt for Python) using a modular mixin architecture:

- **Main Window (`AdminLauncher`)**: Manages subprocess lifecycle for `app.py`, Socket.IO client connection (`sio`), QMediaPlayer preview audio output, countdown timers, and theme styling (Dark/Light QSS).
- **Setup Tab (`SetupTabMixin`)**:
  - Local repository scanner (`_RepoScanWorker` thread).
  - Audio/Video/Text/Simultaneous question creation forms.
  - Drag and drop reordering and round position management.
- **Live Tab (`LiveTabMixin`)**:
  - Dual control modes: **Server-Synced Mode** (drives live game server sequence) vs **Local DJ Mode** (local standalone Winamp-style player with playlist controls).
  - Interactive timer ring widget (`_TimerRingWidget`).
  - Real-time grading table with multi-column filtering.
  - Player lock/moderation controls.
- **Database Tab (`DatabaseTabMixin`)**:
  - Live inspection tool for database tables (`Quiz`, `Question`, `Song`, `Video`, `TextQuestion`, `TextMultiple`, `SimultaneousQuestion`, `Player`, `Answer`, `LogEntry`).
  - Sorting, column filtering, and record limit controls.
- **Custom Dialogs & Widgets (`admin_ui/dialogs.py` & `admin_ui/widgets.py`)**:
  - `AudioQuestionEditorDialog`: Incorporates custom Qt `WaveformWidget` for visual audio clip previewing, zoom controls, start offset adjustment, and clip range playback.
  - `QrPinDialog`: Generates QR codes and 4-digit PINs for team pre-registration and exports team list.

---

## 7. Requirement Verification Matrix

Comparison of requirements from `Quiz_rules_and_mechanics.txt` / `Opis_hr.docx` against current implementation:

| Requirement Category | Requirement Specification | Implementation Status | Implementation Notes |
|---|---|---|---|
| **Structure** | 5 rounds, unlimited questions per round (~15). | **COMPLIANT** | Enforced by `_validate_round` (1-5) and `Question.position` ordering. |
| **Question Types** | Audio, Text, Video, Simultaneous Audio & Text. | **COMPLIANT** | Supported via `Song`, `Video`, `TextQuestion`, `SimultaneousQuestion`, and `TextMultiple` models and dynamic UI renderers. |
| **Response Formats** | Separate text fields for specific data (Artist, Title, Extra); 4-choice Multiple Choice. | **COMPLIANT** | Model `Answer` has dedicated fields; `player.js` renders type-specific input templates. |
| **Timing** | Input active while question plays; locked upon timer expiration. | **COMPLIANT** | Server-side duration check and `player_lock_input` socket lock event. |
| **Scoring (Text)** | 1.0, 0.5, or 0.0 points based on accuracy. | **COMPLIANT** | Fuzzy matching algorithm in `grading_service.py` evaluates 1.0 / 0.5 / 0.0 tiers. |
| **Scoring (Multiple Choice)** | Time-sensitive scaling multiplier across 5 intervals (1.0, 0.8, 0.6, 0.4, 0.2). | **COMPLIANT** | `calculate_time_bonus` scales multiple choice points based on `submission_time / duration`. |
| **Input Integrity** | Designated separate fields; no random field placement. | **COMPLIANT** | Separate database columns and UI input fields for artist, title, and extra text. |
| **Fair Play** | Prohibit external aids / exiting quiz screen. | **COMPLIANT** | Client-side anti-cheat in `player.js` monitors window blur, visibility change, and split-screen resize; locks offending teams. |
| **Late Entry** | Players can join at any time during quiz. | **COMPLIANT** | Late joiners authenticated and synced with active question state upon connection. |
| **Quiz Workflow** | Host launch $\rightarrow$ QR code login $\rightarrow$ 30s round countdown $\rightarrow$ Question sequence $\rightarrow$ 15s intermission with correct answer & leaderboard $\rightarrow$ Round end summary $\rightarrow$ Host review & manual score adjustments $\rightarrow$ Next round launch. | **COMPLIANT** | Fully automated lifecycle in `admin_events.py` and TV screen presentation in `screen.js`. |
| **Preparation & Storage** | Local repository upload, start/end timestamps, API accuracy verification. | **COMPLIANT** | `songs/` / `videos/` local import, `WaveformWidget` timestamp editor, and Deezer REST API verification lookup. |

---

## 8. Identified Gaps, Bugs & Technical Recommendations

### 8.1 Critical & High Priority Gaps

1. **Host Manual Score Override Overwrite Risk (`is_manually_graded`)**:
   - *Issue*: In `admin_events.py`, `finalize_round(round_num)` calls `grade_answer_for_question` for every answer in the round.
   - *Risk*: If the host manually adjusts a player's points in the Live Tab (e.g. giving 1.0 point for a recognized typo), triggering `finalize_round` later will re-execute auto-grading and **overwrite** the host's manual override.
   - *Recommendation*: Add an `is_manually_graded = db.Column(db.Boolean, default=False)` field to the `Answer` model. When `admin_update_score` is called, set `is_manually_graded = True`. Modify `grade_answer_for_question` to skip auto-grading if `is_manually_graded` is True.

2. **Player Disconnection / Reconnection Session Restoration**:
   - *Issue*: If a mobile player refreshes their browser or briefly loses connection during intermission or round summary, they rejoin room but do not automatically receive the current state if no event is currently firing.
   - *Recommendation*: Expand `player_join` socket event handler to send current round phase payload (e.g. `current_question_phase == "answer"` or `current_question_phase == "round_summary"`) upon re-joining.

3. **Desktop Admin UI Video Question Preview & Playback**:
   - *Issue*: In PySide6 Admin Launcher (`local_launcher.py`), the Winamp-style player and playlist handles audio tracks from `songs/`. Video questions play on the TV screen (`/screen`), but desktop launcher player preview for video files is limited.
   - *Recommendation*: Embed a `QVideoWidget` into `LiveTabMixin` or popup preview dialog for host previewing of video questions.

4. **Web Admin Setup Video Upload Endpoint**:
   - *Issue*: The desktop PySide6 setup tab provides local video file picking via `import_video_file`, but the web admin setup interface (`/admin/setup`) requires videos to be manually placed in the `videos/` directory beforehand.
   - *Recommendation*: Add an HTTP multipart file upload route `/admin/upload_video` in `admin_routes.py`.

5. **Server Host IP Detection in Local Network Environments**:
   - *Issue*: `socket.gethostbyname(socket.gethostname())` in `app.py` and `admin_events.py` can resolve to `127.0.0.1` on Linux/Docker environments.
   - *Recommendation*: Use `admin_ui.utils.get_local_ip()` socket UDP probe to accurately resolve outward-facing LAN IP address for QR codes.

### 8.2 Architectural & Quality Recommendations

1. **Automated Unit & Integration Test Suite**:
   - Expand `tests/` to include automated unit tests using `pytest` and Flask test client / SocketIO test client, testing `grading_service.py` string normalization, time bonus calculations, and socket event emissions.
2. **Database Export & Backup Feature**:
   - Add JSON/CSV export functionality in `DatabaseTabMixin` to allow hosts to backup quiz questions, player scores, and log entries.
