# FrugalOS Web Agent - Project Specification

## Executive Summary

**Goal:** Create a "free agent" that maximizes local AI processing on M4 Mac mini (16GB RAM) while providing web-based access from anywhere.

**Vision:** Test the limits of what's possible with local open-source AI vs when remote models are necessary.

**Architecture:** Cloud frontend (frugalos.khamel.com) ↔ Local agent (Mac mini) via Tailscale

---

## System Architecture

### Components

1. **Cloud Frontend** (frugalos.khamel.com)
   - Simple Flask web application
   - Text input interface
   - Progress bars and result display
   - File upload capability
   - Forwards requests to local agent via HTTP

2. **Local Agent** (Mac mini @ Tailscale IP)
   - Flask application + orchestrator brain
   - FrugalOS CLI integration
   - Ollama model management
   - SQLite database for logging/memory
   - Job execution engine

3. **Orchestrator Brain**
   - Request classification and task decomposition
   - Local-first decision making
   - Job queue management
   - Progress tracking

### Communication Flow

```
User Request → Cloud Frontend → HTTP POST → Local Agent → Orchestrator → FrugalOS CLI → Results → Cloud Frontend → User
```

---

## Detailed Feature Requirements

### 1. Request Processing Pipeline

#### 1.1 Input Handling
- **Text Input:** Unstructured natural language requests
- **File Uploads:** Context files (documents, images, data files)
- **Session Management:** Request tracking and user sessions

#### 1.2 Request Classification
**Categories:**
- **Research:** Information gathering, fact-finding
- **Analysis:** Break down concepts, compare options, reasoning
- **Extraction:** Process documents, extract structured data
- **Creation:** Generate content, write code, create artifacts

#### 1.3 Task Decomposition
**Research-Based Approach (Updated):**

**Phase 1: Select-Then-Decompose Strategy**
- **Selection:** Classify request intent and select appropriate pattern
- **Decomposition:** Break into structured subtasks using templates
- **Execution:** Run subtasks with verification after each step
- **Constraint-Based:** Apply budget/local-first constraints from ACONIC framework

**Phase 2: Enhanced Intelligence** (Future)
- **Hierarchical Breakdown:** Multi-level decomposition using TRUST framework patterns
- **Reusable Patterns:** Build LEGOMem-style library of successful task patterns
- **Dynamic Adaptation:** WebDART-style navigation/extraction/execution loops
- **Learning Integration:** MOSAIC-style stepwise refinement based on results

#### 1.4 Decision Making Logic
**Local-First Hierarchy:**
1. Always attempt local execution first
2. Track success/failure per task type
3. Retry with optimized prompts if local fails
4. Escalate to remote only if proven impossible locally

### 2. FrugalOS Integration

#### 2.1 CLI Interface
- Execute `frugal run` commands with generated parameters
- Capture receipts and job results
- Monitor execution status and progress

#### 2.2 Context Management
- Generate appropriate schemas per task type
- Handle file uploads and context preparation
- Prompt optimization for local models

#### 2.3 Progress Tracking
- Real-time job status updates
- Progress bars for multi-job workflows
- Error handling and retry logic

### 3. Data Persistence

#### 3.1 Database Schema
```sql
-- Jobs table
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    input_request TEXT,
    task_category TEXT,
    selection_confidence REAL,
    decomposition_strategy TEXT,
    execution_path TEXT,
    success_rate REAL,
    local_vs_remote TEXT,
    cost_cents INTEGER,
    duration_seconds REAL,
    timestamp DATETIME,
    final_result TEXT,
    constraints_applied TEXT
);

-- Job steps table (enhanced for research-based decomposition)
CREATE TABLE job_steps (
    id INTEGER PRIMARY KEY,
    job_id INTEGER,
    step_order INTEGER,
    step_type TEXT, -- selection, decomposition, execution, verification
    step_subtype TEXT, -- navigation, extraction, analysis, etc.
    prompt TEXT,
    model_used TEXT,
    success BOOLEAN,
    result TEXT,
    cost_cents INTEGER,
    duration_seconds REAL,
    error_message TEXT,
    verification_result TEXT,
    pattern_used TEXT
);

-- Learning analytics table
CREATE TABLE task_analytics (
    id INTEGER PRIMARY KEY,
    task_category TEXT,
    model_name TEXT,
    success_count INTEGER,
    failure_count INTEGER,
    avg_cost_cents REAL,
    avg_duration_seconds REAL,
    last_updated DATETIME
);
```

#### 3.2 File Storage
- **Uploaded Files:** Organized by session/job
- **Job Outputs:** Store all FrugalOS receipts
- **Log Files:** Complete execution traces

### 4. Web Interface Specifications

#### 4.1 Cloud Frontend (frugalos.khamel.com)
**Pages:**
- **Main Interface:** Text input, file upload, progress display
- **Job History:** Previous requests and results
- **Analytics Dashboard:** Success rates, costs, performance metrics
- **Settings:** Budget controls, model preferences

**Features:**
- Responsive design for mobile/desktop
- Real-time progress updates (Server-Sent Events)
- Session persistence
- File drag-and-drop support

#### 4.2 Local Agent (Port 8000 on Tailscale)
**API Endpoints:**
```
POST /api/job           # Submit new job
GET  /api/job/{id}      # Get job status
GET  /api/jobs          # List all jobs
GET  /api/analytics     # Get performance analytics
POST /api/upload        # File upload
GET  /api/health        # System health check
```

### 5. Technical Stack

#### 5.1 Frontend (Cloud)
- **Framework:** Flask (Python)
- **Styling:** Bootstrap or Tailwind CSS
- **Real-time:** Server-Sent Events
- **Deployment:** Simple web server (nginx + gunicorn)

#### 5.2 Backend (Local Agent)
- **Framework:** Flask (Python)
- **Database:** SQLite with sqlite-utils
- **Process Management:** subprocess for FrugalOS CLI
- **Virtual Environment:** Integrated with existing venv

#### 5.3 Dependencies
- **Existing:** FrugalOS, Ollama, Python 3.11+
- **New:** Flask, requests, sqlite-utils, watchdog (for file monitoring)

---

## Implementation Phases

### Phase 1: MVP (Minimum Viable Product)
**Timeline:** 1-2 weeks

**Features:**
- Basic web interface (text input only)
- Simple template-based task decomposition
- Local-only execution (no remote fallback)
- Basic progress tracking
- Job history and results display

**Out of Scope:**
- File uploads
- Remote model integration
- Advanced analytics
- Complex multi-step workflows

### Phase 2: Enhanced Capabilities
**Timeline:** Additional 1-2 weeks

**Features:**
- File upload support
- Remote model fallback with budget controls
- Basic analytics dashboard
- Session management
- Improved task decomposition

### Phase 3: Intelligence Layer
**Timeline:** Future development

**Features:**
- LLM-powered request classification
- Learning from job history
- Dynamic prompt optimization
- Advanced multi-step workflows

---

## Success Metrics

### Technical Metrics
- **Local Success Rate:** % of jobs completed locally vs remote
- **Response Time:** Average job completion time
- **Cost Tracking:** Actual vs expected costs
- **System Reliability:** Uptime, error rates

### Capability Metrics
- **Task Coverage:** What types of requests can be handled
- **Accuracy Rate:** Quality of results per task category
- **Local Model Limits:** What tasks consistently require remote models

### Learning Metrics
- **Pattern Recognition:** Success rate improvements over time
- **Optimization Impact:** How prompt optimization affects local success
- **Model Performance:** Which tasks work best with which local models

---

## Security & Privacy Considerations

### Data Privacy
- **Local Processing:** All sensitive data stays on local machine
- **Cloud Minimalism:** Frontend only handles UI, no data processing
- **Session Isolation:** User data separated by session

### Network Security
- **Tailscale Network:** Private, encrypted communication
- **No Public Exposure:** Local agent never exposed to internet
- **API Authentication:** Simple token-based auth between components

### Cost Controls
- **Budget Enforcement:** Hard limits on remote model usage
- **Cost Visibility:** Real-time cost tracking and alerts
- **Local First Policy:** Automatic preference for free local execution

---

## Deployment Plan

### Local Agent Setup
1. Install Flask dependencies in existing venv
2. Set up Tailscale with static IP
3. Configure autostart on Mac mini boot
4. Test FrugalOS integration

### Cloud Frontend Setup
1. Basic web server configuration
2. Domain setup (frugalos.khamel.com)
3. SSL certificate
4. Simple deployment pipeline

### Testing Strategy
1. **Unit Tests:** Individual component testing
2. **Integration Tests:** End-to-end job flows
3. **Load Tests:** Multiple concurrent jobs
4. **Failure Tests:** Network issues, model failures

---

## Future Roadmap

### Short-term (3 months)
- Expand task categories and templates
- Improve decomposition algorithms
- Add more local model options
- Enhanced analytics and reporting

### Medium-term (6 months)
- Multi-modal capabilities (image processing)
- Voice input/output
- Advanced workflow automation
- Integration with external services

### Long-term (1 year)
- Self-learning optimization
- Custom model fine-tuning
- Distributed processing (multiple local agents)
- Plugin architecture for specialized tasks

---

## Risks & Mitigations

### Technical Risks
- **Local Model Limitations:** Mitigate with smart fallback strategies
- **Network Connectivity:** Use Tailscale for reliable connection
- **Resource Constraints:** Monitor memory/CPU usage on Mac mini

### Project Risks
- **Scope Creep:** Strict phase-based approach
- **Complexity:** Prioritize simplicity over features
- **Maintenance:** Build for reliability and minimal upkeep

---

## Conclusion

This project creates a powerful "free agent" that pushes the boundaries of local AI processing while maintaining the flexibility to leverage remote models when necessary. The phased approach ensures rapid delivery of value while building toward increasingly sophisticated capabilities.

The focus on comprehensive data logging ensures that every interaction provides learning opportunities for future optimization, creating a system that continuously improves its understanding of local vs remote model capabilities.