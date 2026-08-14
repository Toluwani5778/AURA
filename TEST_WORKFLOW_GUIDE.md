# AURA Test Workflow Guide 🧪

## Overview

The **AURA Test Workflow** allows you to safely test the entire system **without any real system consequences**. All external dependencies (Ollama, Kokoro, PyAudio, system commands) are mocked, allowing you to verify functionality in isolation.

## Why Test?

Before running AURA with real services, you can:

- ✅ Verify all imports and dependencies work
- ✅ Test configuration settings
- ✅ Validate session management and memory
- ✅ Test the skills framework
- ✅ Simulate complete conversations
- ✅ Check task classification logic
- ✅ Ensure no system modifications occur

## Quick Start

```bash
cd /home/tolukanni/Documents/Projects/AURA
source myenv/bin/activate
python test_workflow.py
```

## What Gets Tested

### 1. **Import Test**

- Verifies all core modules can be imported
- Checks for missing dependencies
- Validates Python environment

### 2. **Configuration Test**

- Verifies all settings are properly configured
- Checks wakeword configuration
- Validates timeouts and thresholds
- Ensures LLM and TTS settings are present

### 3. **SessionManager Test**

- Tests conversation history tracking
- Verifies context generation
- Checks idle time calculation
- Validates timeout counting

### 4. **Skills Framework Test**

- Confirms skill registration
- Tests each default skill:
  - Greeting skill
  - Time skill
  - Joke skill
  - Capabilities skill
- Verifies skill execution pipeline

### 5. **TaskExecutor Test**

- Validates task classification:
  - PC control detection
  - App control detection
  - Information queries
  - General conversation
- Tests classification accuracy

### 6. **Workflow Simulation**

- Simulates a complete conversation
- Tests user → skill → response flow
- Verifies session logging
- Validates context persistence

## Understanding the Output

### Success Output

```
✅ Configuration test passed
🧪 Tests: 6
📊 Results: 6/6 tests passed

🎉 All tests passed! AURA is ready to run.
```

### What's Mocked (No Real Consequences!)

| Component       | Real             | Test             | Notes                  |
| --------------- | ---------------- | ---------------- | ---------------------- |
| PyAudio         | Real microphone  | Mock streams     | No audio recorded      |
| Speech-to-Text  | Whisper (GPU)    | Mock transcriber | Predefined test inputs |
| Text-to-Speech  | Kokoro API       | Mock speech      | No audio generated     |
| Ollama LLM      | HTTP requests    | Mocked           | No API calls made      |
| System Commands | subprocess.run   | Logged only      | No commands executed   |
| App Launching   | subprocess.Popen | Logged only      | No apps launched       |

## Test Workflow Example

```
🧪 Testing Workflow Simulation...

Simulating conversation:
------------------------------------------------------------

User: Hello AURA
AURA (Greeting): Hey there! I'm AURA, your personal AI assistant...

User: Tell me a joke
AURA (Joke): Why did the programmer quit his job?...

User: What time is it
AURA (Time): It's 14:45 on Thursday, August 13, 2026.

User: Goodbye
AURA (Greeting): Goodbye! It was nice talking to you...

Session complete:
  - Duration: 0.1s
  - Messages: 8
  - Context size: 487 chars

✅ Workflow simulation completed successfully
```

## Command Logging

After tests complete, you'll see:

```
📋 System Commands That Would Execute:
============================================================
1. [Popen] Firefox
2. [Run] ['amixer', 'set', 'Master', '5%+']
3. [Popen] konsole -e 'sudo systemctl poweroff'
============================================================

✅ No actual system modifications were made.
```

## Testing Your Own Skills

To test a custom skill in the workflow:

1. Create your skill in `core/skills.py`:

```python
class MyTestSkill(AuraSkill):
    name = "My Test Skill"
    keywords = ["test", "my skill"]

    def can_handle(self, user_input: str) -> bool:
        return any(kw in user_input.lower() for kw in self.keywords)

    def execute(self, user_input: str) -> Tuple[bool, str]:
        return True, "Test skill response"
```

2. Register it in `initialize_default_skills()`:

```python
def initialize_default_skills():
    global_skill_registry.register(MyTestSkill())
    # ... other skills
```

3. The test will automatically include it in the Skills Framework test

## Test Configuration

Edit the test by modifying `TestConfig` in `test_workflow.py`:

```python
class TestConfig:
    VERBOSE = True                    # Show detailed output
    SAVE_TEST_LOGS = True             # Save logs to file
    TEST_LOG_DIR = Path("data/test_logs")
```

## Interpreting Test Failures

### ❌ Import Test Failed

**Cause**: Missing dependency
**Fix**: `pip install -r requirements.txt`

### ❌ Configuration Test Failed

**Cause**: Missing or invalid configuration
**Fix**: Check `core/config.py` has all required settings

### ❌ SessionManager Test Failed

**Cause**: Session tracking broken
**Fix**: Review `core/memory.py` implementation

### ❌ Skills Framework Test Failed

**Cause**: Skill registration or execution issue
**Fix**: Verify `core/skills.py` syntax and skill definitions

### ❌ TaskExecutor Test Failed

**Cause**: Task classification logic broken
**Fix**: Check `core/task_executor.py` keyword matching

### ❌ Workflow Simulation Failed

**Cause**: End-to-end integration issue
**Fix**: Review stack trace and check component interactions

## Test Reports

Test reports are automatically saved to `data/test_logs/`:

```
data/test_logs/
├── test_report_20260813_142530.json
├── test_report_20260813_150045.json
└── ...
```

Each report contains:

- Timestamp
- Individual test results
- Summary statistics
- Pass/fail status

### View a Report

```bash
cat data/test_logs/test_report_20260813_142530.json
```

## Workflow: Test → Configure → Run

1. **Run Tests** (verify everything works):

   ```bash
   python test_workflow.py
   ```

2. **Configure Settings** (if needed):

   ```bash
   vim core/config.py  # Adjust settings
   ```

3. **Run Tests Again** (verify changes):

   ```bash
   python test_workflow.py
   ```

4. **Start Real AURA** (run with actual services):
   ```bash
   python main.py
   ```

## Safe Testing Practices

### ✅ DO:

- Run tests before updating dependencies
- Run tests after making changes to core modules
- Use tests to verify new skills work
- Run tests to validate configuration changes
- Keep test reports for debugging

### ❌ DON'T:

- Rely on tests as substitute for manual testing
- Ignore test failures
- Skip tests before running with real services
- Modify test mocks unless you know what you're doing

## Advanced: Customizing Test Inputs

To test specific conversation flows, edit the `MockTranscriber` class:

```python
class MockTranscriber:
    test_inputs = [
        "What time is it",           # Change these
        "Tell me a joke",
        "Open Firefox",
        "Good night AURA",
    ]
```

The workflow will cycle through these test inputs during simulation.

## Troubleshooting

### Tests run but all fail

```bash
# Verify imports
python -c "from core.config import *"
python -c "from core.memory import *"
python -c "from core.skills import *"
```

### Test hangs or doesn't complete

- Check for infinite loops in custom skills
- Verify no real network calls being made
- Check system resources (disk space, memory)

### Unclear test failure

- Increase verbosity in test output
- Check `data/test_logs/` for detailed reports
- Run individual tests manually

## Full Test Checklist

Before running real AURA, ensure:

- [ ] Run `python test_workflow.py` successfully
- [ ] All 6 tests pass
- [ ] No import errors
- [ ] Configuration validates
- [ ] Skills framework working
- [ ] Workflow simulation completes
- [ ] Test report saved
- [ ] System commands logged (preview of what would run)

## Next Steps

Once tests pass with flying colors:

1. ✅ Verify external services are running:

   ```bash
   curl http://localhost:11434/api/tags  # Ollama
   curl http://localhost:8880/docs      # Kokoro
   ```

2. ✅ Run setup verification:

   ```bash
   python setup.py
   ```

3. ✅ Start AURA:

   ```bash
   python main.py
   ```

4. 🎤 Wake her up:
   ```
   Say: "Hey Mycroft"
   ```

---

**Happy Testing! 🧪**

The test workflow ensures AURA is ready before real deployment.
