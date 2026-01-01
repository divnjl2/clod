# 🎯 Практическое руководство: Красивый и вкусный Reasoning

## 🧠 Что делает reasoning "красивым и вкусным"?

### 1. **Структурированность** - Чёткая структура
### 2. **Прозрачность** - Видны все шаги
### 3. **Проверяемость** - Можно верифицировать
### 4. **Улучшаемость** - Может итеративно расти
### 5. **Читаемость** - Понятно человеку

---

## 📋 Паттерны из Production систем

### Pattern 1: OpenAI o1 Style - Extended Thinking

**Как работает o1:**
```
User prompt → Model thinks PRIVATELY for 30+ seconds → Final answer

Internal thinking process:
- Generate multiple approaches
- Evaluate each approach
- Backtrack if needed
- Refine solution
- Verify answer
```

**Реализация:**

```python
class O1StyleReasoning:
    """
    O1-style extended thinking.
    
    Key features:
    - Long private reasoning
    - Multiple attempts
    - Self-correction
    """
    
    @staticmethod
    def build_prompt(task: str) -> str:
        return f"""
You have unlimited thinking time. Think deeply before answering.

Task: {task}

<internal_reasoning>
Think step by step. Generate multiple approaches. Test them mentally.
Backtrack if something doesn't work. Refine your solution.

You can use as much reasoning as needed. Quality over speed.

Structure your reasoning:
1. Initial Analysis (understand the problem deeply)
2. Approach Generation (brainstorm 3-5 different approaches)
3. Approach Evaluation (critically analyze each)
4. Solution Development (implement best approach)
5. Verification (test edge cases, check correctness)
6. Refinement (improve based on verification)
</internal_reasoning>

<final_answer>
Only after thorough reasoning, provide your final answer.
</final_answer>
"""

# Example usage:
async def o1_style_solve(task: str, llm_call) -> str:
    """Solve with o1-style extended thinking."""
    
    prompt = O1StyleReasoning.build_prompt(task)
    
    # Call with high max_tokens to allow extended reasoning
    response = await llm_call(
        prompt,
        max_tokens=8000,  # Allow long reasoning
        temperature=1.0    # o1 uses temp=1
    )
    
    # Extract final answer
    final = extract_between(response, "<final_answer>", "</final_answer>")
    reasoning = extract_between(response, "<internal_reasoning>", "</internal_reasoning>")
    
    return {
        "answer": final,
        "reasoning": reasoning,
        "confidence": calculate_confidence(reasoning)
    }
```

---

### Pattern 2: Claude's Thinking Tags - Visible Reasoning

**Как работает Claude's thinking mode:**
```
<thinking>
Let me think through this step by step...
1. First, I need to...
2. Then, I should consider...
3. Wait, that won't work because...
4. Better approach: ...
</thinking>

Here's my answer: ...
```

**Реализация:**

```python
class ClaudeStyleThinking:
    """
    Claude-style visible thinking process.
    
    Key features:
    - Thinking visible in tags
    - Step-by-step breakdown
    - Self-correction visible
    """
    
    @staticmethod
    def build_prompt(task: str) -> str:
        return f"""
Task: {task}

Use <thinking> tags to show your reasoning process.

<thinking>
Step 1: Understand the task
[Your understanding]

Step 2: Identify key challenges
[Challenges]

Step 3: Plan approach
[Your plan]

Step 4: Work through the solution
[Implementation]

Step 5: Verify correctness
[Verification]
</thinking>

Final answer: [Your answer]
"""

# Example:
async def claude_style_solve(task: str, llm_call) -> dict:
    """Solve with visible thinking process."""
    
    prompt = ClaudeStyleThinking.build_prompt(task)
    response = await llm_call(prompt)
    
    # Parse thinking and answer
    thinking = extract_between(response, "<thinking>", "</thinking>")
    answer = response.split("</thinking>")[-1].strip()
    
    # Extract steps
    steps = []
    for i, step_text in enumerate(thinking.split("Step ")[1:], 1):
        steps.append({
            "number": i,
            "content": step_text.strip(),
            "type": detect_step_type(step_text)
        })
    
    return {
        "thinking_steps": steps,
        "final_answer": answer,
        "reasoning_quality": evaluate_reasoning_quality(steps)
    }
```

---

### Pattern 3: ReAct - Reasoning + Acting

**Из paper "ReAct: Synergizing Reasoning and Acting":**

```
Thought 1: I need to find information about X
Action 1: search("X")
Observation 1: [search results]

Thought 2: The search shows Y, now I need Z
Action 2: lookup("Z")
Observation 2: [lookup results]

Thought 3: Based on observations, the answer is...
Answer: [final answer]
```

**Production Implementation:**

```python
class ReActAgent:
    """
    ReAct pattern from research paper.
    
    Interleaves reasoning with tool use.
    """
    
    def __init__(self, tools: dict):
        self.tools = tools
        self.history = []
    
    async def solve(self, task: str, llm_call, max_steps: int = 10):
        """Solve using ReAct pattern."""
        
        for step in range(max_steps):
            # Get next thought + action
            prompt = self._build_react_prompt(task)
            response = await llm_call(prompt)
            
            # Parse response
            thought = extract_field(response, "Thought")
            action = extract_field(response, "Action")
            
            if "FINISH" in action:
                final_answer = extract_field(response, "Answer")
                return {
                    "answer": final_answer,
                    "steps": self.history,
                    "num_steps": step + 1
                }
            
            # Execute action
            observation = await self._execute_action(action)
            
            # Add to history
            self.history.append({
                "step": step + 1,
                "thought": thought,
                "action": action,
                "observation": observation
            })
        
        return {"error": "Max steps reached"}
    
    def _build_react_prompt(self, task: str) -> str:
        """Build ReAct-style prompt."""
        
        history_str = "\n\n".join([
            f"Thought {h['step']}: {h['thought']}\n"
            f"Action {h['step']}: {h['action']}\n"
            f"Observation {h['step']}: {h['observation']}"
            for h in self.history
        ])
        
        return f"""
Solve this task using reasoning and actions.

Task: {task}

Available actions:
{self._format_tools()}

{history_str}

Next step:
Thought {len(self.history) + 1}: [Your reasoning about what to do next]
Action {len(self.history) + 1}: [action_name(args)] OR FINISH[final answer]

Provide your response:
"""
    
    async def _execute_action(self, action: str) -> str:
        """Execute tool action."""
        
        # Parse action
        if "(" in action:
            tool_name = action.split("(")[0]
            args = action.split("(")[1].split(")")[0]
            
            if tool_name in self.tools:
                return await self.tools[tool_name](args)
        
        return "Error: Unknown action"
```

---

### Pattern 4: Tree-of-Thoughts - Explore Multiple Paths

**Из paper "Tree of Thoughts":**

```
          Root (problem)
         /      |      \
    Approach1 Approach2 Approach3
    (eval: 0.8) (0.9)  (0.6)
       |         |
    Solution1 Solution2  ← Pick best
```

**Implementation:**

```python
class TreeOfThoughts:
    """
    Tree-of-Thoughts reasoning.
    
    Explores multiple reasoning paths.
    """
    
    async def solve(
        self,
        task: str,
        llm_call,
        breadth: int = 3,
        depth: int = 2
    ):
        """Solve using ToT."""
        
        # Step 1: Generate initial thoughts
        thoughts = await self._generate_thoughts(task, llm_call, breadth)
        
        # Step 2: Evaluate each thought
        evaluated = []
        for thought in thoughts:
            score = await self._evaluate_thought(task, thought, llm_call)
            evaluated.append({
                "thought": thought,
                "score": score
            })
        
        # Step 3: Sort by score
        evaluated.sort(key=lambda x: x["score"], reverse=True)
        
        # Step 4: Explore best thoughts deeper
        best_solution = None
        best_score = 0
        
        for eval_thought in evaluated[:breadth // 2]:  # Explore top half
            solution = await self._develop_solution(
                task,
                eval_thought["thought"],
                llm_call
            )
            
            solution_score = await self._evaluate_solution(
                task,
                solution,
                llm_call
            )
            
            if solution_score > best_score:
                best_score = solution_score
                best_solution = solution
        
        return {
            "solution": best_solution,
            "score": best_score,
            "explored_thoughts": evaluated
        }
    
    async def _generate_thoughts(
        self,
        task: str,
        llm_call,
        num: int
    ) -> list:
        """Generate multiple initial thoughts."""
        
        prompt = f"""
Generate {num} different approaches to solve this task.

Task: {task}

For each approach, explain:
1. The core idea
2. Why it might work
3. Potential challenges

Output JSON:
{{
  "approaches": [
    {{"id": 1, "idea": "...", "reasoning": "..."}},
    {{"id": 2, "idea": "...", "reasoning": "..."}},
    ...
  ]
}}
"""
        
        response = await llm_call(prompt)
        data = json.loads(response)
        return [a["idea"] for a in data["approaches"]]
    
    async def _evaluate_thought(
        self,
        task: str,
        thought: str,
        llm_call
    ) -> float:
        """Evaluate a thought (0-1)."""
        
        prompt = f"""
Task: {task}
Approach: {thought}

Evaluate this approach on a scale of 0-1 for:
1. Correctness: Will it solve the task correctly?
2. Efficiency: Is it a good way to solve it?
3. Robustness: Will it handle edge cases?

Output JSON:
{{
  "correctness": 0.0-1.0,
  "efficiency": 0.0-1.0,
  "robustness": 0.0-1.0,
  "overall": 0.0-1.0
}}
"""
        
        response = await llm_call(prompt)
        data = json.loads(response)
        return data["overall"]
```

---

### Pattern 5: Self-Consistency - Multiple Samples

**Из paper "Self-Consistency Improves Chain of Thought":**

```
Sample 1: [reasoning 1] → Answer A
Sample 2: [reasoning 2] → Answer A
Sample 3: [reasoning 3] → Answer B
Sample 4: [reasoning 4] → Answer A
Sample 5: [reasoning 5] → Answer A

Majority vote: Answer A (4/5) ✅
```

**Implementation:**

```python
class SelfConsistency:
    """
    Self-Consistency reasoning.
    
    Generates multiple solutions and picks consensus.
    """
    
    async def solve(
        self,
        task: str,
        llm_call,
        num_samples: int = 5,
        temperature: float = 0.7
    ):
        """Solve with self-consistency."""
        
        # Generate multiple independent solutions
        solutions = []
        for i in range(num_samples):
            solution = await self._generate_solution(
                task,
                llm_call,
                temperature=temperature
            )
            solutions.append(solution)
        
        # Count answers
        answer_counts = {}
        for sol in solutions:
            answer = sol["answer"]
            if answer not in answer_counts:
                answer_counts[answer] = []
            answer_counts[answer].append(sol)
        
        # Find majority
        majority_answer = max(
            answer_counts.items(),
            key=lambda x: len(x[1])
        )
        
        consensus = majority_answer[0]
        supporting = majority_answer[1]
        confidence = len(supporting) / num_samples
        
        return {
            "answer": consensus,
            "confidence": confidence,
            "num_samples": num_samples,
            "num_supporting": len(supporting),
            "all_solutions": solutions
        }
    
    async def _generate_solution(
        self,
        task: str,
        llm_call,
        temperature: float
    ) -> dict:
        """Generate one solution."""
        
        prompt = f"""
Task: {task}

Think step by step and provide your answer.

Reasoning:
[Your step-by-step reasoning]

Answer:
[Your final answer]
"""
        
        response = await llm_call(prompt, temperature=temperature)
        
        # Parse
        parts = response.split("Answer:")
        reasoning = parts[0].replace("Reasoning:", "").strip()
        answer = parts[1].strip() if len(parts) > 1 else ""
        
        return {
            "reasoning": reasoning,
            "answer": answer
        }
```

---

## 🎨 Визуальные Примеры

### Пример 1: Debugging Bug

**Task:** "Fix payment API bug - users charged twice"

**O1 Style Reasoning:**
```
<internal_reasoning>
Step 1: Understanding the problem
- Users are being charged twice
- This is a payment API issue
- Need to identify root cause

Step 2: Hypothesis generation
Hypothesis 1: Race condition in payment processing
Hypothesis 2: Retry logic without idempotency
Hypothesis 3: Webhook duplication
Hypothesis 4: Frontend double-submit

Step 3: Evidence gathering
- Check logs for duplicate transactions
- Review payment processing code
- Examine webhook handlers
- Analyze frontend submission logic

Step 4: Root cause analysis
Found: No idempotency keys in payment creation
When user clicks twice → two separate payments created
No check for duplicate requests within time window

Step 5: Solution design
Implement idempotency:
1. Add idempotency_key to requests
2. Store processed keys in Redis (TTL: 24h)
3. Return existing result if key seen before
4. Add rate limiting per user

Step 6: Verification
Test cases:
- Rapid double-click → Only one charge ✅
- Network retry → Same charge ID ✅
- Legitimate second payment → New charge ✅

Step 7: Edge cases
- Expired idempotency key → Create new
- Key collision → Use user_id prefix
- Redis unavailable → Fallback to DB check
</internal_reasoning>

<final_answer>
Root cause: Missing idempotency handling.

Solution:
1. Add idempotency_key to payment requests
2. Cache processed keys in Redis (24h TTL)
3. Return cached result for duplicate keys
4. Add rate limiting (1 req/5sec per user)

This prevents duplicate charges while allowing
legitimate subsequent payments.
</final_answer>
```

**Quality Score: 98%**
- ✅ Systematic hypothesis generation
- ✅ Evidence-based analysis
- ✅ Edge case consideration
- ✅ Verification plan

---

### Пример 2: System Design

**Task:** "Design scalable notification system"

**Tree-of-Thoughts:**
```
Root: Design notification system
│
├─ Approach 1: Push-based (score: 0.85)
│  └─ WebSockets + Redis Pub/Sub
│     - Real-time delivery
│     - High connection overhead
│     - Complex scaling
│
├─ Approach 2: Pull-based (score: 0.70)
│  └─ Polling + Database
│     - Simple implementation
│     - High database load
│     - Latency issues
│
└─ Approach 3: Hybrid (score: 0.95) ← BEST
   └─ Push for active + Pull for others
      - Best of both worlds
      - Scalable architecture
      - Complex but manageable

Selected: Hybrid Approach

Detailed Design:
┌─────────────────────────────────────────┐
│         Load Balancer                   │
└─────────────────────────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
┌────────┐   ┌────────┐
│ WS     │   │ REST   │
│ Server │   │ API    │
└────────┘   └────────┘
    │             │
    └──────┬──────┘
           ▼
    ┌────────────┐
    │   Redis    │
    │  Pub/Sub   │
    └────────────┘
           │
           ▼
    ┌────────────┐
    │  Workers   │
    └────────────┘
           │
           ▼
    ┌────────────┐
    │ PostgreSQL │
    └────────────┘

Quality: 95%
- ✅ Multiple approaches considered
- ✅ Trade-offs analyzed
- ✅ Best approach selected
- ✅ Detailed architecture
```

---

### Пример 3: Code Review

**Task:** "Review this authentication code"

**ReAct Pattern:**
```
Thought 1: Need to review authentication code for security
Action 1: read_file("auth.py")
Observation 1: 
def login(username, password):
    user = db.query(f"SELECT * FROM users WHERE name='{username}'")
    if user and user.password == password:
        return generate_token(user)

Thought 2: CRITICAL ISSUE - SQL injection vulnerability!
Action 2: check_for_sql_injection()
Observation 2: Confirmed - direct string interpolation in SQL query

Thought 3: Also password comparison without hashing
Action 3: check_password_handling()
Observation 3: Passwords stored in plain text, compared directly

Thought 4: Need to check token generation
Action 4: analyze("generate_token")
Observation 4: Token generation uses random() - not cryptographically secure

Thought 5: Compile security issues
Action 5: FINISH

Answer: CRITICAL SECURITY ISSUES FOUND:

1. SQL Injection (CRITICAL)
   - Line 2: Direct string interpolation
   - Fix: Use parameterized queries
   
2. Plain Text Passwords (CRITICAL)
   - Line 3: No password hashing
   - Fix: Use bcrypt/argon2
   
3. Weak Token Generation (HIGH)
   - generate_token uses random()
   - Fix: Use secrets.token_urlsafe()

RECOMMENDED FIXES:

def login(username, password):
    # Fix SQL injection
    user = db.query(
        "SELECT * FROM users WHERE name=?",
        (username,)
    )
    
    # Fix password handling
    if user and bcrypt.verify(password, user.password_hash):
        # Fix token generation
        token = secrets.token_urlsafe(32)
        return token
    
    return None

Quality: 95%
- ✅ Systematic code review
- ✅ Security issues identified
- ✅ Concrete fixes provided
- ✅ Step-by-step reasoning
```

---

## 📊 MCP Paradigms для Reasoning

### MCP Pattern 1: Memory для Learning

```json
{
  "mcpServers": {
    "reasoning-memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"],
      "env": {
        "MEMORY_NAMESPACE": "reasoning_patterns"
      }
    }
  }
}
```

**Usage:**
```python
# Save successful reasoning
await mcp.remember(
    "payment_bug_fix_reasoning",
    {
        "task": "Fix double charge bug",
        "pattern": "o1_style",
        "quality": 0.98,
        "approach": "idempotency keys",
        "lessons": [
            "Always use idempotency for payments",
            "Cache keys in Redis for 24h",
            "Test with rapid clicks"
        ]
    }
)

# Learn from past
past_lessons = await mcp.recall("*_bug_fix_reasoning")
improved_reasoning = await reason(
    new_bug,
    context={"past_lessons": past_lessons}
)
```

### MCP Pattern 2: Filesystem для Documentation

```python
# Save reasoning trace
await mcp.write_file(
    "docs/reasoning/payment_bug_analysis.md",
    format_reasoning_as_markdown(trace)
)

# Create reasoning library
await mcp.write_file(
    "docs/reasoning/patterns/o1_style_examples.md",
    compile_examples(all_o1_traces)
)
```

### MCP Pattern 3: Custom Validator

```python
@mcp_server.tool()
async def validate_reasoning_quality(
    reasoning_steps: list,
    task: str
) -> dict:
    """Validate reasoning quality."""
    
    scores = {
        "systematic": check_systematic(reasoning_steps),
        "evidence_based": check_evidence(reasoning_steps),
        "edge_cases": check_edge_cases(reasoning_steps),
        "verification": check_verification(reasoning_steps)
    }
    
    overall = sum(scores.values()) / len(scores)
    
    return {
        "scores": scores,
        "overall": overall,
        "grade": "A" if overall > 0.9 else "B" if overall > 0.8 else "C",
        "suggestions": generate_improvement_suggestions(scores)
    }
```

---

## ✅ Production Checklist

### Quality Gates:

```python
async def production_reasoning(task: str) -> dict:
    """Production-grade reasoning with quality gates."""
    
    # Gate 1: Pattern selection
    pattern = select_best_pattern(task)
    
    # Gate 2: Execute with pattern
    trace = await execute_reasoning(task, pattern)
    
    # Gate 3: Quality check
    quality = await validate_quality(trace)
    if quality < 0.8:
        # Retry with better pattern
        trace = await execute_reasoning(task, "reflection")
    
    # Gate 4: Verification
    verified = await verify_correctness(trace)
    if not verified:
        # Self-correct
        trace = await self_correct(trace)
    
    # Gate 5: Save for learning
    await save_reasoning(trace)
    
    return trace
```

---

**ГОТОВО! Полный практический гайд по качественному reasoning! 🧠✨**
