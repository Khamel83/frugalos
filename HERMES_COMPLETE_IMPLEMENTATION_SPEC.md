# Hermes Complete Implementation Specification

## Executive Summary

**Hermes + Backend-Agnostic Talos + Meta-Learning**: Personal AI assistant that takes vague ideas and runs them to ground autonomously, using interchangeable AI backends, with smart conversation optimization, accessible from anywhere, growing smarter over time.

**Core Philosophy**: "Always keep moving - execute immediately, refine continuously, never block unless impossible."

**Architecture Principle**: "Hermes contains ALL intelligence, Talos is a completely dumb execution pipe that can be swapped with any AI backend (local models, GPT-5, server-side models, etc.)"

---

## System Architecture Overview

### Complete Component Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        HERMES (OCI VM)                         │
│              COMPLETE INTELLIGENCE & ORCHESTRATION              │
├─────────────────────────────────────────────────────────────────┤
│  🌐 Web Interface Layer                                         │
│  ├── Simple input form                                           │
│  ├── Real-time progress display                                 │
│  ├── Conversation management                                    │
│  └── Results presentation & download                            │
├─────────────────────────────────────────────────────────────────┤
│  🧠 COMPLETE META-LEARNING ENGINE                               │
│  ├── Front-loaded question generation                           │
│  ├── Pattern recognition & learning                            │
│  ├── Conversation optimization                                  │
│  ├── Personalization & adaptation                              │
│  └── ALL decision making & intelligence                        │
├─────────────────────────────────────────────────────────────────┤
│  📋 Job Management & Backend Selection                         │
│  ├── Job queue with priorities                                  │
│  ├── Dependency management                                      │
│  ├── Backend-agnostic job routing                              │
│  ├── Smart backend selection logic                              │
│  ├── Retry logic & failure handling                             │
│  └── Progress tracking & notifications                          │
├─────────────────────────────────────────────────────────────────┤
│  🔌 BACKEND MANAGER (NEW)                                      │
│  ├── Backend abstraction layer                                 │
│  ├── Dynamic backend registration                              │
│  ├── Load balancing & failover                                 │
│  ├── Health monitoring across all backends                     │
│  └── Cost optimization across backends                         │
├─────────────────────────────────────────────────────────────────┤
│  💾 Data Persistence Layer                                       │
│  ├── SQLite database (jobs, threads, patterns, backends)        │
│  ├── Text-based logging system                                  │
│  ├── Backend performance tracking                               │
│  ├── Configuration management                                   │
│  └── Backup & archival                                          │
├─────────────────────────────────────────────────────────────────┤
│  🔗 Communication & Notification Layer                          │
│  ├── Multi-backend connectivity                                 │
│  ├── Health monitoring & recovery                               │
│  ├── Telegram notifications                                      │
│  └── External API endpoints                                    │
└─────────────────────────────────────────────────────────────────┘

                    ↓ ↓ ↓ ↓ ↓ ↓ ↓ ↓ ↓ ↓

┌─────────────────────────────────────────────────────────────────┐
│                  EXECUTION BACKENDS (SWAPPABLE)                  │
│              "DUMB PIPES" - No Intelligence Required          │
├─────────────────────────────────────────────────────────────────┤
│  🤖 TALOS (Mac Mini)                                          │
│  └── Dumb execution pipe                                       │
│      "Receive prompt → Execute → Return result"                │
│                                                                │
│  🌐 REMOTE API BACKENDS                                        │
│  └── Dumb execution pipe                                       │
│      "Receive prompt → Execute → Return result"                │
│                                                                │
│  🏭 SERVER-SIDE MODELS                                        │
│  └── Dumb execution pipe                                       │
│      "Receive prompt → Execute → Return result"                │
│                                                                │
│  🚀 FUTURE BACKENDS (GPT-5, etc.)                            │
│  └── Dumb execution pipe                                       │
│      "Receive prompt → Execute → Return result"                │
└─────────────────────────────────────────────────────────────────┘
```

### Backend-Agnostic Communication Flow

```
User Input → Hermes Web Interface
    ↓
Quick Analysis & Immediate Execution (Draft 1)
    ↓
Hermes Backend Manager → Select Optimal Backend (Talos/API/Server)
    ↓
Send to Backend → Execute with Selected AI Model
    ↓
Results Back to Hermes → Display to User
    ↓
Meta-Learning Analysis → Smart Questions
    ↓
User Responses → Refined Understanding
    ↓
Optimized Execution (Draft 2) → Possibly Different Backend
    ↓
Learning Storage → Pattern Recognition Across All Backends
    ↓
Backend Performance Learning → Better Backend Selection
    ↓
Future Optimization → Better First Drafts & Backend Choices
```

---

## Database Schema Design

### Core Database Tables

#### 1. Idea Threads (Main Entity)
```sql
CREATE TABLE idea_threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,                    -- Public thread identifier
    title TEXT NOT NULL,                           -- Human-readable title
    original_request TEXT NOT NULL,               -- User's original input
    initial_clarity_score REAL DEFAULT 0.0,       -- How clear initial understanding was
    final_clarity_score REAL DEFAULT 0.0,         -- How clear final understanding became
    status TEXT DEFAULT 'active',                  -- active, paused, completed, archived, failed
    idea_type TEXT,                                -- research, creation, analysis, decision, mixed
    complexity_score INTEGER DEFAULT 1,           -- 1-10 complexity estimate
    priority INTEGER DEFAULT 5,                   -- 1-10 priority level

    -- User Context & Preferences
    user_context TEXT,                             -- JSON of user preferences/constraints
    communication_style TEXT,                      -- formal, casual, technical
    depth_preference TEXT,                         -- overview, detailed, comprehensive

    -- System Learning
    learned_patterns TEXT,                         -- JSON of patterns discovered
    optimization_applied TEXT,                     -- JSON of optimizations used
    conversation_effectiveness REAL DEFAULT 0.0,   -- How well conversation worked

    -- Results & Outcomes
    final_result_summary TEXT,                     -- Human-readable summary
    user_satisfaction INTEGER,                     -- 1-5 rating if provided
    success_criteria_met TEXT,                     -- JSON of which success criteria were met

    -- Timing & Performance
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_date DATETIME,
    total_execution_time_minutes REAL DEFAULT 0.0,
    total_conversation_time_minutes REAL DEFAULT 0.0,

    -- Meta-learning Data
    draft_count INTEGER DEFAULT 0,                -- How many drafts/iterations
    optimization_savings REAL DEFAULT 0.0,         -- Time saved by optimizations
    pattern_confidence REAL DEFAULT 0.0            -- Confidence in applied patterns
);
```

#### 2. Jobs (Individual Tasks)
```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,                   -- Links to idea thread
    parent_job_id INTEGER,                        -- For job sequences and dependencies
    job_sequence INTEGER DEFAULT 1,               -- Which iteration/draft this is
    job_type TEXT NOT NULL,                       -- research, analysis, creation, optimization
    job_subtype TEXT,                             -- More specific task classification
    status TEXT DEFAULT 'pending',                -- pending, queued, running, completed, failed, retrying

    -- Classification & Understanding
    classification_confidence REAL DEFAULT 0.0,   -- How confident we are in classification
    required_clarity_level REAL DEFAULT 0.5,      -- How much clarity needed for this job
    achieved_clarity_level REAL DEFAULT 0.0,      -- How much clarity actually achieved

    -- Execution Details
    prompt_template_used TEXT,                     -- Which prompt template was used
    prompt_variables TEXT,                        -- JSON of variables applied to template
    backend_used TEXT,                             -- Which backend executed this job
    model_used TEXT,                              -- Which model executed this job
    backend_confidence REAL DEFAULT 0.0,          -- How confident we were in backend selection
    model_confidence REAL DEFAULT 0.0,            -- How confident model was in result

    -- Results & Quality
    result_summary TEXT,                          -- Human-readable summary
    full_result TEXT,                             -- Complete model output
    result_quality_score REAL DEFAULT 0.0,         -- System assessment of result quality
    user_feedback INTEGER,                        -- 1-5 user rating if provided
    met_success_criteria TEXT,                    -- JSON of which criteria were met

    -- Performance Metrics
    execution_time_seconds REAL DEFAULT 0.0,
    queue_time_seconds REAL DEFAULT 0.0,
    processing_time_seconds REAL DEFAULT 0.0,
    cost_cents INTEGER DEFAULT 0,

    -- Retry & Error Handling
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 999999,
    retry_reasons TEXT,                           -- JSON of why retries were needed
    error_message TEXT,
    recovery_strategy TEXT,                       -- What we did to fix errors

    -- Dependencies & Scheduling
    dependencies TEXT,                            -- JSON of job dependencies
    priority INTEGER DEFAULT 5,
    scheduled_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_date DATETIME,
    completed_date DATETIME,

    -- Learning Data
    optimization_applied TEXT,                     -- JSON of optimizations used
    pattern_effectiveness REAL DEFAULT 0.0,       -- How well applied patterns worked
    learned_from_job TEXT,                        -- Key insights from this job

    FOREIGN KEY (thread_id) REFERENCES idea_threads (id),
    FOREIGN KEY (parent_job_id) REFERENCES jobs (id)
);
```

#### 3. Conversations (Meta-Learning Data)
```sql
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL,
    job_id INTEGER,                               -- Optional: if conversation is job-specific
    conversation_phase TEXT,                      -- initial, refinement, clarification, completion

    -- Question & Response Data
    question_asked TEXT NOT NULL,                 -- The question asked
    question_type TEXT NOT NULL,                  -- intent, constraint, success, context, scope
    question_template_id INTEGER,                 -- Links to question template
    question_confidence REAL DEFAULT 0.0,         -- How confident we were this was the right question

    user_response TEXT,                           -- User's response
    response_type TEXT,                           -- direct_answer, clarification, preference, correction

    -- Effectiveness Analysis
    clarity_improvement REAL DEFAULT 0.0,         -- How much this improved understanding
    conversation_efficiency REAL DEFAULT 0.0,     -- How efficiently this moved conversation forward
    user_satisfaction INTEGER,                    -- 1-5 rating if provided

    -- Timing & Context
    asked_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    responded_date DATETIME,
    response_time_seconds REAL DEFAULT 0.0,
    conversation_position INTEGER,                 -- Where this was in conversation sequence

    -- Learning Data
    pattern_matched TEXT,                         -- Which historical pattern this matched
    prediction_accuracy REAL DEFAULT 0.0,         -- How well we predicted user's needs
    optimization_suggested TEXT,                  -- What optimizations this enabled

    FOREIGN KEY (thread_id) REFERENCES idea_threads (id),
    FOREIGN KEY (job_id) REFERENCES jobs (id)
);
```

#### 4. Question Templates (Meta-Learning Patterns)
```sql
CREATE TABLE question_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_name TEXT NOT NULL,
    question_category TEXT NOT NULL,               -- intent, constraint, success, context, scope
    question_template TEXT NOT NULL,               -- Template with placeholders
    trigger_patterns TEXT,                        -- JSON of when to use this template

    -- Effectiveness Metrics
    usage_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,                 -- How often this leads to better outcomes
    clarity_improvement_avg REAL DEFAULT 0.0,     -- Average clarity improvement
    user_satisfaction_avg REAL DEFAULT 0.0,       -- Average user satisfaction
    time_saved_avg REAL DEFAULT 0.0,              -- Average time saved by asking this

    -- Context Matching
    applicable_input_types TEXT,                   -- JSON of input types this applies to
    required_confidence_threshold REAL DEFAULT 0.5,
    optimal_timing TEXT,                           -- beginning, middle, end of conversation

    -- Personalization Data
    user_preferences TEXT,                         -- JSON of how to adapt for different users
    style_variations TEXT,                         -- JSON of alternative phrasings

    -- System Management
    is_active BOOLEAN DEFAULT TRUE,
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used DATETIME,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    effectiveness_trend TEXT                       -- improving, stable, declining
);
```

#### 5. Learned Patterns (System Intelligence)
```sql
CREATE TABLE learned_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_name TEXT NOT NULL,
    pattern_category TEXT NOT NULL,                -- conversation, execution, optimization, user_behavior
    pattern_description TEXT,

    -- Pattern Recognition
    trigger_conditions TEXT NOT NULL,              -- JSON of when this pattern applies
    confidence_level REAL DEFAULT 0.0,             -- How confident we are in this pattern
    validation_count INTEGER DEFAULT 0,            -- How many times we've seen this
    success_count INTEGER DEFAULT 0,               -- How many times it led to success

    -- Impact & Effectiveness
    impact_description TEXT,                       -- What this pattern enables
    time_saved_estimate REAL DEFAULT 0.0,          -- Average time saved
    quality_improvement_estimate REAL DEFAULT 0.0, -- Average quality improvement
    user_satisfaction_improvement REAL DEFAULT 0.0,

    -- Application Data
    recommended_actions TEXT,                       -- JSON of what to do when pattern matches
    question_template_ids TEXT,                    -- JSON of related question templates
    optimization_strategies TEXT,                  -- JSON of optimizations to apply

    -- Evolution Tracking
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_applied DATETIME,
    last_validated DATETIME,
    pattern_evolution TEXT,                        -- How pattern has changed over time

    -- Relationships
    parent_pattern_id INTEGER,                     -- For hierarchical patterns
    related_pattern_ids TEXT,                      -- JSON of related patterns
    supersedes_pattern_id INTEGER,                 -- If this replaces an older pattern

    FOREIGN KEY (parent_pattern_id) REFERENCES learned_patterns (id),
    FOREIGN KEY (supersedes_pattern_id) REFERENCES learned_patterns (id)
);
```

#### 6. User Preferences & Context (Personalization)
```sql
CREATE TABLE user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    preference_category TEXT NOT NULL,             -- communication, depth, style, constraints
    preference_key TEXT NOT NULL,                  -- Specific preference
    preference_value TEXT NOT NULL,                -- The actual preference

    -- Preference Strength & Stability
    confidence_score REAL DEFAULT 0.5,            -- How confident we are in this preference
    stability_score REAL DEFAULT 0.5,              -- How stable this preference is over time
    usage_count INTEGER DEFAULT 0,                 -- How often this preference has been applied

    -- Context & Applicability
    applicable_contexts TEXT,                      -- JSON of when this preference applies
    expiration_date DATETIME,                      -- If this preference should expire

    -- Learning Data
    learned_from_interaction_id INTEGER,            -- Which interaction taught us this
    validation_count INTEGER DEFAULT 0,            -- How many times this has been confirmed
    correction_count INTEGER DEFAULT 0,            -- How many times we've had to correct this

    -- Metadata
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_applied DATETIME,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    source TEXT                                    -- explicit_user_feedback, observed_pattern, inference
);
```

#### 7. System Configuration (Environment Variables)
```sql
CREATE TABLE system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    config_type TEXT NOT NULL,                     -- constraint, preference, system_setting, budget
    config_category TEXT,                          -- hermes, talos, communication, learning

    -- Configuration Management
    description TEXT,
    is_user_editable BOOLEAN DEFAULT FALSE,
    requires_restart BOOLEAN DEFAULT FALSE,
    validation_regex TEXT,                         -- For validating input values

    -- Change Tracking
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT,                               -- user, system, deployment

    -- Dependencies & Impact
    depends_on TEXT,                               -- JSON of other config this depends on
    impacts TEXT,                                  -- JSON of what this config affects

    default_value TEXT,                            -- For reset functionality
    min_value TEXT,                                -- For numeric/config ranges
    max_value TEXT                                 -- For numeric/config ranges
);
```

#### 8. Backends (Backend-Agnostic Management)
```sql
CREATE TABLE backends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    backend_type TEXT NOT NULL,                  -- local, remote_api, server_model, custom
    enabled BOOLEAN DEFAULT TRUE,
    is_primary BOOLEAN DEFAULT FALSE,

    -- Configuration
    config TEXT NOT NULL,                        -- JSON of backend-specific config
    capabilities TEXT,                           -- JSON of backend capabilities

    -- Performance Metadata
    quality_score REAL DEFAULT 0.0,             -- 0-1 quality rating
    speed_score REAL DEFAULT 0.0,               -- 0-1 speed rating
    cost_score REAL DEFAULT 0.0,                -- 0-1 cost efficiency (1=free)
    reliability_score REAL DEFAULT 0.0,          -- 0-1 reliability rating

    -- Health & Status
    health_status TEXT DEFAULT 'unknown',        -- healthy, degraded, unhealthy, unknown
    last_health_check DATETIME,
    consecutive_failures INTEGER DEFAULT 0,

    -- Usage Statistics
    total_jobs INTEGER DEFAULT 0,
    successful_jobs INTEGER DEFAULT 0,
    failed_jobs INTEGER DEFAULT 0,
    total_cost_cents INTEGER DEFAULT 0,
    average_response_time REAL DEFAULT 0.0,

    -- Metadata
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used DATETIME,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Relationships
    preferred_for_job_types TEXT,                -- JSON of ideal job types
    fallback_backends TEXT                       -- JSON of fallback options
);
```

#### 9. Backend Performance Tracking
```sql
CREATE TABLE backend_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backend_id INTEGER NOT NULL,
    job_id INTEGER,

    -- Performance Metrics
    response_time_ms REAL,
    quality_score REAL,                          -- User or system-rated quality
    cost_cents INTEGER,
    token_count INTEGER,

    -- Job Context
    job_type TEXT,
    job_complexity INTEGER,
    model_used TEXT,

    -- Outcome
    success BOOLEAN,
    error_message TEXT,
    user_satisfaction INTEGER,                   -- 1-5 rating

    -- Timestamps
    executed_date DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (backend_id) REFERENCES backends (id),
    FOREIGN KEY (job_id) REFERENCES jobs (id)
);
```

#### 10. Backend Selection History
```sql
CREATE TABLE backend_selection_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,

    -- Selection Process
    selection_criteria TEXT,                     -- cost_first, quality_first, etc.
    available_backends TEXT,                     -- JSON of backends considered
    selection_reasoning TEXT,                    -- Why this backend was chosen

    -- Selected Backend
    selected_backend_id INTEGER,
    confidence_score REAL,                       -- How confident we were in selection

    -- Alternative Options
    rejected_backends TEXT,                      -- JSON of backends considered but rejected
    rejection_reasons TEXT,                      -- Why others were rejected

    -- Outcome
    selection_successful BOOLEAN,                -- Did this selection work well?
    fallback_used BOOLEAN,                       -- Did we need to fallback?
    final_backend_id INTEGER,                    -- If fallback was used

    executed_date DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (job_id) REFERENCES jobs (id),
    FOREIGN KEY (selected_backend_id) REFERENCES backends (id),
    FOREIGN KEY (final_backend_id) REFERENCES backends (id)
);
```

#### 11. System Health & Monitoring
```sql
CREATE TABLE system_health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component TEXT NOT NULL,                       -- hermes, talos, backend_name, database
    health_status TEXT NOT NULL,                   -- healthy, degraded, unhealthy, unknown
    response_time_ms REAL DEFAULT 0.0,
    error_rate REAL DEFAULT 0.0,

    -- Health Metrics
    cpu_usage_percent REAL DEFAULT 0.0,
    memory_usage_percent REAL DEFAULT 0.0,
    disk_usage_percent REAL DEFAULT 0.0,
    network_latency_ms REAL DEFAULT 0.0,

    -- Issue Tracking
    active_issues TEXT,                            -- JSON of current problems
    recent_errors TEXT,                            -- JSON of recent error messages
    recovery_actions TEXT,                         -- JSON of what we did to fix issues

    -- Timestamps
    measured_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_healthy_date DATETIME,
    last_issue_date DATETIME
);
```

### Initial Data Seeding

#### System Configuration (Complete Environment Variables)
```sql
INSERT INTO system_config (config_key, config_value, config_type, config_category, description, is_user_editable) VALUES
-- HERMES WEB CONFIG
('hermes.web.port', '5000', 'system_setting', 'hermes', 'Port for Hermes web interface', FALSE),
('hermes.web.session_timeout_hours', '24', 'system_setting', 'hermes', 'How long sessions remain active', TRUE),
('hermes.web.max_input_length', '10000', 'system_setting', 'hermes', 'Maximum input length for ideas', TRUE),
('hermes.web.max_queued_jobs', '100', 'system_setting', 'hermes', 'Maximum jobs in queue', TRUE),

-- TALOS COMMUNICATION
('hermes.talos.tailscale_ip', '100.x.x.x', 'system_setting', 'hermes', 'Tailscale IP for Talos', FALSE),
('hermes.talos.tailscale_port', '8001', 'system_setting', 'hermes', 'Port for Talos agent', FALSE),
('hermes.talos.health_check_interval', '10', 'system_setting', 'hermes', 'Seconds between health checks', TRUE),
('hermes.talos.connection_timeout', '30', 'system_setting', 'hermes', 'Connection timeout to Talos', TRUE),
('hermes.talos.max_retry_duration', '3600', 'system_setting', 'hermes', 'Max seconds to retry Talos', TRUE),

-- DATABASE & STORAGE
('hermes.db.path', '/app/data/hermes.db', 'system_setting', 'hermes', 'Database file path', FALSE),
('hermes.db.backup_schedule', '0 2 * * *', 'system_setting', 'hermes', 'Backup schedule (cron)', TRUE),
('hermes.db.max_size_mb', '1000', 'system_setting', 'hermes', 'Maximum database size', TRUE),
('hermes.logs.cloud_retention_days', '30', 'system_setting', 'hermes', 'Days to keep logs in cloud', TRUE),

-- NOTIFICATIONS
('hermes.notifications.telegram_bot_token', '', 'system_setting', 'hermes', 'Telegram bot token', TRUE),
('hermes.notifications.telegram_chat_id', '', 'system_setting', 'hermes', 'Telegram chat ID', TRUE),
('hermes.notifications.alert_types', 'talos_down,job_failure,queue_full', 'system_setting', 'hermes', 'Types of alerts to send', TRUE),
('hermes.notifications.cooldown_minutes', '30', 'system_setting', 'hermes', 'Minutes between same alerts', TRUE),

-- BUDGET & COST CONTROL
('hermes.budget.openrouter_api_key', '', 'system_setting', 'hermes', 'OpenRouter API key', TRUE),
('hermes.budget.daily_budget_cents', '500', 'budget', 'hermes', 'Daily budget in cents', TRUE),
('hermes.budget.project_budget_cents', '2000', 'budget', 'hermes', 'Project budget in cents', TRUE),
('hermes.budget.cost_tracking_enabled', 'true', 'preference', 'hermes', 'Enable cost tracking', TRUE),
('hermes.budget.budget_alerts', 'true', 'preference', 'hermes', 'Enable budget alerts', TRUE),

-- LOCAL-FIRST POLICY
('hermes.execution.local_first_enabled', 'true', 'preference', 'hermes', 'Prefer local execution', TRUE),
('hermes.execution.local_retry_attempts', '3', 'preference', 'hermes', 'Local retry attempts', TRUE),
('hermes.execution.force_remote_threshold', '0.8', 'preference', 'hermes', 'Remote threshold (success rate)', TRUE),

-- TALOS CONFIG
('talos.models.local_models', 'llama3.1:8b,qwen2.5-coder:7b', 'system_setting', 'talos', 'Available local models', TRUE),
('talos.models.default_model', 'llama3.1:8b', 'system_setting', 'talos', 'Default model', TRUE),
('talos.models.code_model', 'qwen2.5-coder:7b', 'system_setting', 'talos', 'Code generation model', TRUE),
('talos.ollama.host', 'http://localhost:11434', 'system_setting', 'talos', 'Ollama server URL', FALSE),

-- TALOS EXECUTION CONSTRAINTS
('talos.execution.max_concurrent_jobs', '1', 'constraint', 'talos', 'Maximum concurrent jobs', TRUE),
('talos.execution.job_timeout_seconds', '3600', 'constraint', 'talos', 'Job timeout in seconds', TRUE),
('talos.execution.retry_interval', '60', 'system_setting', 'talos', 'Retry interval in seconds', TRUE),
('talos.execution.max_retry_attempts', '999999', 'constraint', 'talos', 'Maximum retry attempts', TRUE),

-- TALOS STORAGE & LOGGING
('talos.logs.base_path', '/Users/khamel83/hermes_data/logs', 'system_setting', 'talos', 'Base path for logs', FALSE),
('talos.logs.retention_days', '365', 'system_setting', 'talos', 'Days to keep logs', TRUE),
('talos.logs.performance_logging', 'true', 'preference', 'talos', 'Enable performance logging', TRUE),
('talos.logs.full_result_storage', 'true', 'preference', 'talos', 'Store full results', TRUE),

-- TALOS SYSTEM CONSTRAINTS
('talos.system.max_memory_usage_percent', '80', 'constraint', 'talos', 'Max memory usage percent', TRUE),
('talos.system.max_cpu_usage_percent', '90', 'constraint', 'talos', 'Max CPU usage percent', TRUE),
('talos.system.available_ram_gb', '16', 'system_setting', 'talos', 'Available RAM in GB', TRUE),
('talos.system.available_storage_tb', '5', 'system_setting', 'talos', 'Available storage in TB', TRUE),

-- META-LEARNING CONFIG
('hermes.learning.enabled', 'true', 'preference', 'hermes', 'Enable meta-learning', TRUE),
('hermes.learning.confidence_threshold', '0.7', 'system_setting', 'hermes', 'Minimum confidence for pattern application', TRUE),
('hermes.learning.max_questions_per_conversation', '5', 'constraint', 'hermes', 'Max questions to ask', TRUE),
('hermes.learning.pattern_validation_threshold', '0.8', 'system_setting', 'hermes', 'Threshold for pattern validation', TRUE),

-- PROJECT & TASK CONFIG
('hermes.projects.default_project_cents', '0', 'budget', 'hermes', 'Default project budget (cents)', TRUE),
('hermes.projects.min_remote_budget_cents', '50', 'budget', 'hermes', 'Minimum budget for remote use', TRUE),
('hermes.execution.consensus_threshold', '0.67', 'system_setting', 'hermes', 'Consensus threshold for validation', TRUE),
('hermes.execution.k_sample_count', '3', 'system_setting', 'hermes', 'Number of samples for consensus', TRUE),

-- TASK CLASSIFICATION
('hermes.classification.enable_llm', 'true', 'preference', 'hermes', 'Enable LLM classification', TRUE),
('hermes.classification.model', 'llama3.1:8b', 'system_setting', 'hermes', 'Model for classification', TRUE),
('hermes.classification.pattern_threshold', '0.7', 'system_setting', 'hermes', 'Threshold for pattern matching', TRUE),

-- WORKFLOW ORCHESTRATION
('hermes.workflow.max_steps', '10', 'constraint', 'hermes', 'Maximum workflow steps', TRUE),
('hermes.workflow.timeout_minutes', '60', 'constraint', 'hermes', 'Workflow timeout in minutes', TRUE),
('hermes.workflow.enable_dependencies', 'true', 'preference', 'hermes', 'Enable dependency resolution', TRUE),

-- BACKEND CONFIGURATION (NEW)
('hermes.backends.enabled', 'talos,remote_api', 'system_setting', 'hermes', 'Enabled backends (comma-separated)', TRUE),
('hermes.backends.primary', 'talos', 'system_setting', 'hermes', 'Primary backend', TRUE),
('hermes.backends.fallback', 'remote_api', 'system_setting', 'hermes', 'Fallback backend', TRUE),
('hermes.backends.load_balancing', 'false', 'preference', 'hermes', 'Enable load balancing', TRUE),
('hermes.backends.auto_failover', 'true', 'preference', 'hermes', 'Enable automatic failover', TRUE),

-- BACKEND SELECTION LOGIC (NEW)
('hermes.selection.criteria', 'cost_first', 'preference', 'hermes', 'Backend selection criteria', TRUE),
('hermes.selection.quality_threshold', '0.8', 'system_setting', 'hermes', 'Minimum quality threshold', TRUE),
('hermes.selection.max_cost_per_job', '100', 'constraint', 'hermes', 'Maximum cost per job (cents)', TRUE),
('hermes.selection.prefer_free', 'true', 'preference', 'hermes', 'Prefer free backends', TRUE),

-- TALOS BACKEND CONFIG (UPDATED)
('backend.talos.enabled', 'true', 'system_setting', 'hermes', 'Enable Talos backend', TRUE),
('backend.talos.type', 'local', 'system_setting', 'hermes', 'Talos backend type', FALSE),
('backend.talos.host', '100.x.x.x', 'system_setting', 'hermes', 'Talos Tailscale IP', FALSE),
('backend.talos.port', '8001', 'system_setting', 'hermes', 'Talos port', FALSE),
('backend.talos.models', 'llama3.1:8b,qwen2.5-coder:7b', 'system_setting', 'hermes', 'Talos available models', TRUE),
('backend.talos.timeout', '300', 'system_setting', 'hermes', 'Talos timeout (seconds)', TRUE),
('backend.talos.health_interval', '30', 'system_setting', 'hermes', 'Talos health check interval', TRUE),

-- REMOTE API BACKEND CONFIG (NEW)
('backend.remote_api.enabled', 'true', 'system_setting', 'hermes', 'Enable remote API backend', TRUE),
('backend.remote_api.type', 'openrouter', 'system_setting', 'hermes', 'Remote API type', TRUE),
('backend.remote_api.key', '', 'system_setting', 'hermes', 'Remote API key', TRUE),
('backend.remote_api.models', 'anthropic/claude-3-sonnet,openai/gpt-4-turbo', 'system_setting', 'hermes', 'Remote API models', TRUE),
('backend.remote_api.timeout', '120', 'system_setting', 'hermes', 'Remote API timeout (seconds)', TRUE),
('backend.remote_api.rate_limit', '60', 'system_setting', 'hermes', 'Remote API rate limit (per minute)', TRUE),

-- SERVER MODELS BACKEND CONFIG (NEW)
('backend.server_models.enabled', 'false', 'system_setting', 'hermes', 'Enable server models backend', TRUE),
('backend.server_models.type', 'custom', 'system_setting', 'hermes', 'Server models type', TRUE),
('backend.server_models.host', '', 'system_setting', 'hermes', 'Server models host', TRUE),
('backend.server_models.port', '8080', 'system_setting', 'hermes', 'Server models port', TRUE),
('backend.server_models.key', '', 'system_setting', 'hermes', 'Server models API key', TRUE),
('backend.server_models.models', 'llama3.2:70b,qwen2.5:72b', 'system_setting', 'hermes', 'Server models available', TRUE),

-- GPT-5 BACKEND CONFIG (FUTURE)
('backend.gpt5.enabled', 'false', 'system_setting', 'hermes', 'Enable GPT-5 backend', TRUE),
('backend.gpt5.type', 'openai', 'system_setting', 'hermes', 'GPT-5 backend type', TRUE),
('backend.gpt5.key', '', 'system_setting', 'hermes', 'GPT-5 API key', TRUE),
('backend.gpt5.model', 'gpt-5', 'system_setting', 'hermes', 'GPT-5 model', TRUE),
('backend.gpt5.timeout', '90', 'system_setting', 'hermes', 'GPT-5 timeout (seconds)', TRUE),

-- DEBUG & DEVELOPMENT
('hermes.debug.mode', 'false', 'system_setting', 'hermes', 'Debug mode', FALSE),
('hermes.debug.verbose_logging', 'false', 'system_setting', 'hermes', 'Verbose logging', FALSE),
('hermes.debug.performance_monitoring', 'true', 'preference', 'hermes', 'Performance monitoring', TRUE),
('hermes.debug.api_rate_limiting', 'true', 'system_setting', 'hermes', 'API rate limiting', TRUE);
```

---

## API Specification

### Core API Endpoints

#### 1. Web Interface Endpoints (Hermes)

##### Job Submission & Management
```python
@app.route('/api/submit', methods=['POST'])
def submit_idea():
    """
    Submit new idea for processing
    Returns: thread_id, initial_status, estimated_time
    """

@app.route('/api/threads/<thread_id>/status', methods=['GET'])
def get_thread_status(thread_id):
    """
    Get current status of idea thread
    Returns: progress, current_job, completed_jobs, results
    """

@app.route('/api/threads/<thread_id>/jobs/<job_id>/result', methods=['GET'])
def get_job_result(thread_id, job_id):
    """
    Get specific job result
    Returns: result_summary, full_result, download_urls
    """

@app.route('/api/threads/<thread_id>/continue', methods=['POST'])
def continue_conversation(thread_id):
    """
    Continue conversation with additional information
    Returns: updated_understanding, next_steps
    """
```

##### Meta-Learning Endpoints
```python
@app.route('/api/threads/<thread_id>/optimize', methods=['POST'])
def optimize_thread(thread_id):
    """
    Apply meta-learning optimizations to thread
    Returns: optimization_applied, expected_improvements
    """

@app.route('/api/learn/patterns', methods=['GET'])
def get_learned_patterns():
    """
    Get system's learned patterns
    Returns: patterns, confidence_levels, success_rates
    """

@app.route('/api/learn/feedback', methods=['POST'])
def submit_feedback():
    """
    Submit user feedback for learning
    Returns: feedback_recorded, learning_updated
    """
```

##### System Management
```python
@app.route('/api/system/health', methods=['GET'])
def system_health():
    """
    Get system health status
    Returns: overall_status, component_status, active_jobs
    """

@app.route('/api/system/config', methods=['GET', 'PUT'])
def system_config():
    """
    Get/update system configuration
    Returns: current_config or update_status
    """
```

#### 2. Agent Endpoints (Talos)

##### Job Execution
```python
@app.route('/agent/execute', methods=['POST'])
def execute_job():
    """
    Execute job on Talos
    Input: job_data, prompt, model_config
    Returns: job_id, estimated_time, status
    """

@app.route('/agent/status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """
    Get status of executing job
    Returns: status, progress, eta, errors
    """

@app.route('/agent/cancel/<job_id>', methods=['POST'])
def cancel_job(job_id):
    """
    Cancel running job
    Returns: cancellation_status, cleanup_actions
    """
```

##### Health & Monitoring
```python
@app.route('/agent/health', methods=['GET'])
def agent_health():
    """
    Get Talos agent health status
    Returns: status, resource_usage, model_availability
    """

@app.route('/agent/models', methods=['GET'])
def available_models():
    """
    Get list of available models
    Returns: models, capabilities, resource_requirements
    """
```

#### 3. External Integration Endpoints

##### External Service Integration
```python
@app.route('/api/external/submit', methods=['POST'])
def external_submit():
    """
    Submit job from external service
    Input: idea, callback_url, source_app
    Returns: thread_id, status_url
    """

@app.route('/api/external/callback/<thread_id>', methods=['POST'])
def external_callback(thread_id):
    """
    Receive callback for external job completion
    Input: results, status, metadata
    Returns: callback_received, processing_status
    """
```

### API Response Formats

#### Standard Success Response
```json
{
    "status": "success",
    "data": {
        "thread_id": "uuid-string",
        "status": "processing",
        "estimated_time_minutes": 15,
        "next_steps": [
            "Initial research phase",
            "Analysis of findings",
            "Result optimization"
        ]
    },
    "meta": {
        "timestamp": "2025-10-24T14:30:15Z",
        "request_id": "req-uuid",
        "processing_time_ms": 123
    }
}
```

#### Error Response
```json
{
    "status": "error",
    "error": {
        "code": "TALOS_UNAVAILABLE",
        "message": "Talos agent is not responding",
        "details": "Connection timeout after 30 seconds",
        "retry_after": 60,
        "user_action": "Please check if Talos is running"
    },
    "meta": {
        "timestamp": "2025-10-24T14:30:15Z",
        "request_id": "req-uuid"
    }
}
```

---

## Meta-Learning Implementation Details

### "Always Keep Moving" Philosophy

#### Immediate Execution Flow
```python
class AlwaysMovingExecutor:
    def execute_idea_with_immediacy(self, user_input):
        """Execute immediately, then refine with questions"""

        # Step 1: Quick Analysis (under 5 seconds)
        initial_understanding = self.quick_analyze(user_input)

        # Step 2: Immediate Execution (Draft 1)
        draft_1_job = self.create_draft_job(user_input, initial_understanding)
        draft_1_result = self.execute_immediately(draft_1_job)

        # Step 3: Present Draft 1 to User
        self.present_draft_result(draft_1_result)

        # Step 4: Meta-Learning Questions (fast as constraints allow)
        optimization_questions = self.generate_optimization_questions(
            user_input,
            initial_understanding,
            draft_1_result
        )

        # Step 5: Refine & Execute (Draft 2)
        if optimization_questions:
            refined_understanding = self.apply_question_insights(
                optimization_questions
            )
            draft_2_result = self.execute_optimized(
                refined_understanding,
                draft_1_result
            )
            return draft_2_result
        else:
            return draft_1_result
```

#### Front-Loaded Question Generation
```python
class SmartQuestionGenerator:
    def generate_optimization_questions(self, user_input, understanding, draft_result):
        """Generate questions that will most improve the result"""

        questions = []

        # Analyze draft result quality
        quality_issues = self.analyze_result_quality(draft_result)

        # Generate targeted questions for each issue
        for issue in quality_issues:
            if issue['type'] == 'unclear_intent':
                questions.append(self.generate_intent_question(user_input))
            elif issue['type'] == 'missing_constraints':
                questions.append(self.generate_constraint_question())
            elif issue['type'] == 'unclear_success':
                questions.append(self.generate_success_question())
            elif issue['type'] == 'insufficient_context':
                questions.append(self.generate_context_question(user_input))

        # Prioritize questions by impact
        return self.prioritize_questions(questions, draft_result)

    def prioritize_questions(self, questions, current_result):
        """Prioritize questions that will have the most impact"""

        for question in questions:
            # Estimate improvement potential
            question['estimated_improvement'] = self.estimate_improvement(
                question, current_result
            )
            question['time_cost'] = self.estimate_question_time_cost(question)
            question['value_score'] = (
                question['estimated_improvement'] / question['time_cost']
            )

        # Sort by value score
        return sorted(questions, key=lambda x: x['value_score'], reverse=True)
```

#### Pattern Recognition for Question Effectiveness
```python
class QuestionEffectivenessAnalyzer:
    def analyze_question_effectiveness(self, thread_id, question_id):
        """Analyze how effective a question was in improving outcomes"""

        # Get before/after data
        before_state = self.get_state_before_question(thread_id, question_id)
        after_state = self.get_state_after_question(thread_id, question_id)

        # Calculate improvement metrics
        clarity_improvement = after_state['clarity'] - before_state['clarity']
        quality_improvement = after_state['quality'] - before_state['quality']
        satisfaction_improvement = after_state['satisfaction'] - before_state['satisfaction']

        # Calculate efficiency
        question_time_cost = before_state['response_time']
        total_process_improvement = (
            clarity_improvement + quality_improvement + satisfaction_improvement
        )
        efficiency_score = total_process_improvement / question_time_cost

        return {
            'clarity_improvement': clarity_improvement,
            'quality_improvement': quality_improvement,
            'satisfaction_improvement': satisfaction_improvement,
            'efficiency_score': efficiency_score,
            'total_improvement': total_process_improvement
        }
```

### Adaptive Conversation Management

#### Conversation State Tracking
```python
class ConversationStateManager:
    def __init__(self):
        self.conversation_states = {}

    def track_conversation_state(self, thread_id, interaction):
        """Track conversation state and transitions"""

        if thread_id not in self.conversation_states:
            self.conversation_states[thread_id] = {
                'phase': 'initial',
                'clarity_score': 0.0,
                'questions_asked': [],
                'user_responses': [],
                'understanding_evolution': [],
                'optimization_opportunities': []
            }

        state = self.conversation_states[thread_id]

        # Update state based on interaction
        state['questions_asked'].append(interaction['question'])
        state['user_responses'].append(interaction['response'])
        state['clarity_score'] = self.calculate_clarity_score(state)
        state['phase'] = self.determine_conversation_phase(state)

        # Identify optimization opportunities
        state['optimization_opportunities'] = self.identify_opportunities(state)

        return state

    def should_continue_conversation(self, thread_id):
        """Determine if more questions would be beneficial"""

        state = self.conversation_states[thread_id]

        # Stop conditions
        if state['clarity_score'] >= 0.9:
            return False, "High clarity achieved"

        if len(state['questions_asked']) >= self.max_questions_per_conversation:
            return False, "Maximum questions reached"

        if not state['optimization_opportunities']:
            return False, "No clear optimization opportunities"

        # Continue conditions
        if state['clarity_score'] < 0.7:
            return True, "Clarity still insufficient"

        if state['optimization_opportunities'] and state['clarity_score'] < 0.85:
            return True, "Significant optimization opportunities exist"

        return False, "Adequate clarity achieved"
```

---

## Implementation Task List

### Phase 1: Foundation (Week 1)

#### Day 1: Core Infrastructure
- [ ] Set up Flask application structure for Hermes
- [ ] Create basic web interface with input form
- [ ] Implement SQLite database initialization
- [ ] Set up basic logging system
- [ ] Create Tailscale communication module

#### Day 2: Job Management
- [ ] Implement job queue system
- [ ] Create job submission API endpoint
- [ ] Build job status tracking
- [ ] Add basic retry logic
- [ ] Implement health monitoring

#### Day 3: Talos Agent
- [ ] Create simple agent program for Mac Mini
- [ ] Implement FrugalOS CLI integration
- [ ] Add local model selection logic
- [ ] Build result transmission back to Hermes
- [ ] Add agent health endpoint

#### Day 4: Communication & Testing
- [ ] Implement Hermes ↔ Talos communication
- [ ] Add error handling and recovery
- [ ] Create basic web interface for job submission
- [ ] Test end-to-end job flow
- [ ] Add Telegram notification system

#### Day 5: Integration & Polish
- [ ] Implement session management
- [ ] Add results display and download
- [ ] Create basic system status page
- [ ] Test failure scenarios
- [ ] Deploy to OCI VM for testing

### Phase 2: Intelligence (Week 2)

#### Day 6-7: Meta-Learning Foundation
- [ ] Implement meta-learning database schema
- [ ] Create conversation tracking system
- [ ] Build front-loaded question generation
- [ ] Add pattern recognition engine
- [ ] Implement learning from completed jobs

#### Day 8-9: Smart Optimization
- [ ] Implement "always keep moving" execution flow
- [ ] Add adaptive conversation management
- [ ] Create question effectiveness analysis
- [ ] Build pattern learning system
- [ ] Add user preference tracking

#### Day 10: Testing & Refinement
- [ ] Test meta-learning with sample conversations
- [ ] Validate pattern recognition accuracy
- [ ] Optimize question selection algorithms
- [ ] Test learning from user feedback
- [ ] Refine conversation flow based on testing

### Phase 3: Deployment & Automation (Week 3)

#### Day 11-12: Deployment Automation
- [ ] Create GitHub Actions for automatic deployment
- [ ] Build setup script for Talos agent
- [ ] Implement configuration management
- [ ] Add backup and recovery systems
- [ ] Create monitoring and alerting

#### Day 13-14: Documentation & Final Testing
- [ ] Write comprehensive documentation
- [ ] Create user guides and setup instructions
- [ ] Test complete system end-to-end
- [ ] Validate all failure scenarios
- [ ] Performance testing and optimization

#### Day 15: Launch Preparation
- [ ] Final system integration testing
- [ ] Security review and hardening
- [ ] Backup and disaster recovery testing
- [ ] User acceptance testing
- [ ] Production deployment

---

## Success Metrics & Validation

### Phase 1 Success Criteria
- [ ] Can submit ideas and receive draft results within 2 minutes
- [ ] System handles Talos downtime gracefully with queuing
- [ ] All jobs are logged with complete execution traces
- [ ] Web interface is accessible from anywhere via Tailscale
- [ ] Basic error handling and recovery works reliably

### Phase 2 Success Criteria
- [ ] Meta-learning questions improve result quality by measurable amount
- [ ] System learns user preferences and adapts accordingly
- [ ] Pattern recognition becomes more accurate over time
- [ ] "Always keep moving" philosophy reduces time to first result
- [ ] User satisfaction with conversation flow improves

### Phase 3 Success Criteria
- [ ] System can be deployed and updated automatically
- [ ] Documentation is comprehensive enough for non-technical users
- [ ] System handles edge cases and failure scenarios gracefully
- [ ] Performance meets or exceeds user expectations
- [ ] System is ready for production use

### Long-term Success Metrics
- **Usage Frequency**: How often user chooses Hermes over alternatives
- **Learning Velocity**: How quickly system improves with use
- **Conversation Efficiency**: Reduction in time needed to understand user intent
- **Result Quality**: Improvement in outcomes due to meta-learning optimization
- **User Satisfaction**: Overall satisfaction with system intelligence and helpfulness

---

## Security & Privacy Considerations

### Data Protection
- **Local-First Storage**: All sensitive data stored on local machine
- **Encrypted Communication**: All traffic via Tailscale encryption
- **User Control**: User can delete, modify, or export any data
- **Transparent Logging**: User can see all data collection and usage

### System Security
- **Input Validation**: All inputs sanitized and validated
- **Access Control**: User mode vs Guest mode with appropriate permissions
- **Rate Limiting**: Prevent abuse and resource exhaustion
- **Monitoring**: System health and security event monitoring

### Privacy by Design
- **Minimal Data Collection**: Only collect what's necessary for functionality
- **Purpose Limitation**: Use data only for stated purposes
- **Data Minimization**: Retain data only as long as necessary
- **User Rights**: Easy data access, correction, and deletion

---

## Evolution Roadmap

### Short-term (1-3 months)
- Enhanced pattern recognition capabilities
- Improved conversation flow optimization
- Better user preference learning
- Expanded external service integrations

### Medium-term (3-6 months)
- Multi-modal input support (images, documents)
- Advanced workflow orchestration
- Cross-domain knowledge synthesis
- Collaborative features (if desired)

### Long-term (6+ months)
- Proactive assistance and suggestions
- Autonomous research and exploration
- Complex dependency management
- Advanced natural language understanding

---

## Conclusion

This complete specification provides everything needed to build Hermes + Talos with meta-learning capabilities:

✅ **Complete Architecture**: All components, interfaces, and data flows specified
✅ **Database Design**: Comprehensive schema for all functionality
✅ **API Specification**: All endpoints and response formats defined
✅ **Meta-Learning System**: Complete conversation optimization framework
✅ **Implementation Plan**: Detailed task breakdown with success criteria
✅ **Security & Privacy**: Comprehensive protection measures
✅ **Evolution Path**: Clear roadmap for future enhancements

The "always keep moving" philosophy ensures users see immediate progress while the meta-learning system continuously optimizes future interactions. This creates a virtuous cycle of improvement that makes Hermes exponentially more effective over time.

**Ready to begin implementation following this detailed specification?**