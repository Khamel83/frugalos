# 🚀 MVP Specification - Local-First AI Router
## Build Now vs Build Later

**Version**: 1.0 MVP
**Philosophy**: Ship working system fast, add fancy features later

---

## 🎯 Core Principle

**Try local first. If not good enough, show upgrade cost. Track sessions so we don't lose context.**

That's it. Everything else is optional.

---

## 📦 Phase 1: MVP (Build This Now)

### What We're Building

```python
# User sends prompt
prompt = "Design a microservices architecture"

# 1. Try local models
local_result = try_local_models(prompt)
# Result: llama3.2:3b scored 7.2/10

# 2. Check if good enough
if local_result.quality >= 9.0:
    return local_result  # Done!

# 3. Show upgrade cost
print(f"""
Local: {local_result.quality}/10 - FREE
Upgrade to Claude 3.5: 9.5/10 - $0.0006
Upgrade? (y/n):
""")

# 4. Track session if they upgrade
if user_upgrades:
    session.start_cloud_session()  # Remember we're in cloud now
    return cloud_result
```

### Core Components (MVP)

1. **Local Model Runner** (`hermes/local_runner.py`)
   - Connect to Ollama
   - Run prompt through 4 local models
   - Pick best result
   - Score quality (simple heuristic: response length, coherence)

2. **Cloud Model Runner** (`hermes/cloud_runner.py`)
   - OpenRouter API integration
   - Simple cost calculation (count tokens × price)
   - Run Claude 3.5 Sonnet

3. **Session Manager** (`hermes/session.py`)
   - Track if we're in local or cloud session
   - Store conversation history
   - Calculate session costs
   - Warn about session switching costs

4. **Simple Router** (`hermes/router.py`)
   - Try local first
   - Show upgrade option
   - Handle user choice
   - Track session state

### Database (Simple SQLite)

```sql
-- Just track sessions and costs
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    session_id TEXT UNIQUE,
    model_tier TEXT,  -- 'local' or 'cloud'
    total_cost REAL,
    task_count INTEGER,
    started_at DATETIME,
    ended_at DATETIME
);

CREATE TABLE tasks (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    prompt TEXT,
    local_quality REAL,
    cloud_quality REAL,
    model_used TEXT,
    cost REAL,
    timestamp DATETIME
);
```

### File Structure (Minimal)

```
hermes/
├── app.py                 # FastAPI app (basic endpoints)
├── router.py              # Main routing logic
├── local_runner.py        # Ollama integration
├── cloud_runner.py        # OpenRouter integration
├── session.py             # Session tracking
├── database.py            # SQLite setup
├── config.py              # Model costs, settings
└── requirements.txt       # Dependencies
```

### API Endpoints (Minimal)

```python
POST /api/process          # Main endpoint - process prompt
GET  /api/session/status   # Check current session state
POST /api/session/upgrade  # User approves cloud upgrade
GET  /api/session/cost     # Show current session cost
```

---

## 🎯 MVP User Experience

### Example 1: Local Works Fine
```
> "Write a Python function to reverse a string"

🏠 LOCAL RESULT
Model: llama3.2:3b
Quality: 9.2/10 ✅
Cost: FREE
Time: 1.3s

[Shows result]
```

### Example 2: Need Cloud Upgrade
```
> "Design a microservices architecture for e-commerce"

🏠 LOCAL RESULT
Model: qwen2.5-coder:7b
Quality: 7.1/10 ❌
Cost: FREE

☁️ CLOUD UPGRADE AVAILABLE
Model: Claude 3.5 Sonnet
Quality: ~9.5/10
Cost: $0.0006 (this task)

⚠️  SESSION IMPACT:
If you upgrade, we'll stay in cloud session for related tasks.
Average session: 25 tasks ≈ $0.21 total

Upgrade? [y/n]:
```

### Example 3: Already in Cloud Session
```
> "Add authentication to that architecture"

☁️ CLOUD SESSION ACTIVE
Model: Claude 3.5 Sonnet
Quality: ~9.5/10
Cost: $0.0006 (task 3/25 in session)
Session cost so far: $0.0018

[Shows result]
```

---

## 🔧 Implementation Details

### 1. Quality Scoring (Simple for MVP)

```python
def score_quality(response: str, prompt: str) -> float:
    """Simple quality scoring - good enough for MVP"""

    score = 5.0  # Start at 5/10

    # Length check (not too short, not too long)
    if 100 < len(response) < 2000:
        score += 1.0

    # Contains code if prompt asks for code
    if "code" in prompt.lower() or "function" in prompt.lower():
        if "```" in response or "def " in response:
            score += 1.5

    # Structured response (has paragraphs or bullets)
    if "\n\n" in response or "- " in response:
        score += 1.0

    # Specific keywords from prompt appear in response
    prompt_words = set(prompt.lower().split())
    response_words = set(response.lower().split())
    overlap = len(prompt_words & response_words) / len(prompt_words)
    score += overlap * 1.5

    return min(10.0, score)
```

### 2. Cost Calculation (Simple)

```python
MODEL_COSTS = {
    "claude_35_sonnet": {
        "input_per_million": 3.0,
        "output_per_million": 15.0
    }
}

def estimate_cost(prompt: str) -> float:
    """Rough cost estimate - good enough for MVP"""

    # Simple token estimation: words * 1.3
    input_tokens = len(prompt.split()) * 1.3
    output_tokens = input_tokens * 2  # Educated guess

    model = MODEL_COSTS["claude_35_sonnet"]
    cost = (input_tokens / 1_000_000) * model["input_per_million"]
    cost += (output_tokens / 1_000_000) * model["output_per_million"]

    return cost
```

### 3. Session Management

```python
class Session:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.tier = "local"  # Start local always
        self.messages = []
        self.total_cost = 0.0
        self.task_count = 0

    def upgrade_to_cloud(self):
        """Switch to cloud session"""
        self.tier = "cloud"
        # Add context transfer cost
        self.total_cost += 0.006

    def add_task(self, prompt: str, response: str, cost: float):
        """Track task in session"""
        self.messages.append({"prompt": prompt, "response": response})
        self.total_cost += cost
        self.task_count += 1

    def should_warn_about_session(self) -> bool:
        """Warn if switching to cloud"""
        return self.tier == "local"  # Only warn on first upgrade
```

---

## 🚫 NOT Building in MVP (Build Later)

### Phase 2: Learning System (Optional)
- Token estimation that learns from real usage
- Prediction accuracy tracking
- Confidence scores
- **Why later?** Simple estimates work fine for now

### Phase 3: Advanced Monitoring (Optional)
- Cost dashboard
- Usage analytics
- Detailed reports
- **Why later?** Database has the data, build UI when needed

### Phase 4: Smart Routing (Optional)
- Automatic task categorization
- Model selection based on task type
- Quality prediction before running
- **Why later?** Manual choice works for MVP

### Phase 5: Context Transfer (Optional)
- Smart context pruning
- Cross-model context translation
- Session continuation optimization
- **Why later?** Simple context passing works fine

---

## ✅ Success Criteria for MVP

1. **Local models run successfully** - Can process prompts through Ollama
2. **Quality scoring works** - Can distinguish good/bad responses
3. **Cost calculation accurate** - Within 50% of actual cost (good enough)
4. **Session tracking works** - Knows if we're local or cloud
5. **User can make informed decision** - Shows costs clearly
6. **No surprise costs** - Session costs tracked and displayed

---

## 🚀 Implementation Timeline (Realistic)

### Day 1-2: Basic Infrastructure
- FastAPI app setup
- Ollama integration
- OpenRouter integration
- Simple database

### Day 3-4: Routing Logic
- Local-first router
- Quality scoring
- Cost calculation
- User prompts

### Day 5-6: Session Management
- Session tracking
- Cost accumulation
- Session warnings
- Database persistence

### Day 7: Testing & Polish
- Test with real prompts
- Fix edge cases
- Improve user experience
- Documentation

**Total: 1 week to working MVP**

---

## 🎯 After MVP: Evaluate and Decide

Once MVP is working, ask:

1. **Is quality scoring accurate enough?** If not, add learning system
2. **Do we need better cost estimates?** If not, keep it simple
3. **Is session management working?** If yes, keep simple approach
4. **Do users want dashboard?** If yes, build it (data is already there)

**Build what you need, when you need it.**

---

## 📝 Key Decisions

### Architecture Choices

1. **Simple quality scoring** - Not ML-based, just heuristics
   - Pro: Fast to implement, no training needed
   - Con: Less accurate than learning system
   - **Decision**: Good enough for MVP, can improve later

2. **Rough cost estimates** - Basic token counting
   - Pro: Simple, transparent
   - Con: Not super accurate
   - **Decision**: Within 50% is fine for MVP

3. **Basic session tracking** - Just local/cloud state
   - Pro: Simple to implement and understand
   - Con: No fancy context management
   - **Decision**: Solves the session cost problem

4. **SQLite database** - Simple, local, no setup
   - Pro: Zero config, works everywhere
   - Con: Not scalable (don't care for MVP)
   - **Decision**: Perfect for MVP

---

## 🔑 Core Value Proposition

**"Try free local models first. If not good enough, see exactly what it costs to upgrade. Never lose context or get surprise bills."**

That's it. That's the product. Everything else is optional.