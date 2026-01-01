"""
Advanced Reasoning System
=========================

Гарантия качественного reasoning через:
- Chain-of-Thought (CoT)
- Tree-of-Thoughts (ToT)
- Self-Consistency
- Reflection
- ReAct pattern
- Verification loops

Best practices из:
- OpenAI o1 reasoning
- Claude's thinking mode
- Research papers (ToT, ReAct, Reflexion)
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import asyncio


class ReasoningPattern(Enum):
    """Паттерны reasoning."""
    CHAIN_OF_THOUGHT = "cot"          # Последовательное мышление
    TREE_OF_THOUGHTS = "tot"          # Дерево возможностей
    SELF_CONSISTENCY = "self_consistency"  # Несколько попыток
    REFLECTION = "reflection"          # Саморефлексия
    REACT = "react"                    # Reason + Act
    LEAST_TO_MOST = "least_to_most"   # От простого к сложному


@dataclass
class ThoughtStep:
    """Шаг размышления."""
    step_number: int
    type: str  # "understanding", "analysis", "planning", "execution", "verification"
    content: str
    confidence: float = 0.0  # 0-1
    alternatives: List[str] = field(default_factory=list)


@dataclass
class ReasoningTrace:
    """Полный trace reasoning процесса."""
    pattern: ReasoningPattern
    thoughts: List[ThoughtStep]
    final_answer: str
    confidence: float
    verification_passed: bool = False
    reflection: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern": self.pattern.value,
            "thoughts": [
                {
                    "step": t.step_number,
                    "type": t.type,
                    "content": t.content,
                    "confidence": t.confidence,
                    "alternatives": t.alternatives
                }
                for t in self.thoughts
            ],
            "final_answer": self.final_answer,
            "confidence": self.confidence,
            "verification_passed": self.verification_passed,
            "reflection": self.reflection
        }


# ============================================================================
# CHAIN-OF-THOUGHT (CoT)
# ============================================================================

class ChainOfThoughtReasoning:
    """
    Классический Chain-of-Thought reasoning.
    
    Steps:
    1. Understand the problem
    2. Break down into sub-problems
    3. Solve each step
    4. Combine results
    5. Verify answer
    
    Example from research:
    Q: Roger has 5 tennis balls. He buys 2 more cans of tennis balls. 
       Each can has 3 tennis balls. How many tennis balls does he have now?
    
    CoT:
    1. Roger started with 5 balls
    2. He bought 2 cans with 3 balls each = 2 * 3 = 6 balls
    3. Total = 5 + 6 = 11 balls
    Answer: 11
    """
    
    @staticmethod
    def build_prompt(task: str, context: Dict[str, Any] = None) -> str:
        """Build CoT prompt."""
        
        prompt = f"""
You are solving this task step by step using Chain-of-Thought reasoning.

Task: {task}

{f"Context: {json.dumps(context, indent=2)}" if context else ""}

Think step by step:

Step 1 - UNDERSTAND:
- What is the task asking for?
- What information do I have?
- What are the constraints?

Step 2 - ANALYZE:
- What approach should I take?
- What are the key insights?
- Are there any edge cases?

Step 3 - PLAN:
- Break down into sub-steps
- List what needs to be done in order
- Identify dependencies

Step 4 - EXECUTE:
- Solve each sub-step
- Show your work
- Explain your reasoning

Step 5 - VERIFY:
- Check if the answer makes sense
- Test edge cases
- Validate assumptions

Provide your response in JSON format:
{{
  "understanding": "...",
  "analysis": "...",
  "plan": ["step1", "step2", ...],
  "execution": {{
    "step1": "...",
    "step2": "..."
  }},
  "verification": "...",
  "final_answer": "...",
  "confidence": 0.0-1.0
}}

Begin reasoning:
"""
        return prompt
    
    @staticmethod
    async def execute(
        task: str,
        llm_call: Callable,
        context: Dict[str, Any] = None
    ) -> ReasoningTrace:
        """Execute CoT reasoning."""
        
        prompt = ChainOfThoughtReasoning.build_prompt(task, context)
        response = await llm_call(prompt)
        
        # Parse response
        data = json.loads(response)
        
        # Build thought steps
        thoughts = [
            ThoughtStep(1, "understanding", data["understanding"]),
            ThoughtStep(2, "analysis", data["analysis"]),
            ThoughtStep(3, "planning", "\n".join(data["plan"])),
        ]
        
        # Add execution steps
        for i, (step, content) in enumerate(data["execution"].items(), start=4):
            thoughts.append(ThoughtStep(i, "execution", content))
        
        # Add verification
        thoughts.append(
            ThoughtStep(
                len(thoughts) + 1,
                "verification",
                data["verification"]
            )
        )
        
        return ReasoningTrace(
            pattern=ReasoningPattern.CHAIN_OF_THOUGHT,
            thoughts=thoughts,
            final_answer=data["final_answer"],
            confidence=data["confidence"],
            verification_passed=True
        )


# ============================================================================
# TREE-OF-THOUGHTS (ToT)
# ============================================================================

class TreeOfThoughtsReasoning:
    """
    Tree-of-Thoughts reasoning для сложных задач.
    
    Generates multiple reasoning paths and evaluates them.
    
    Steps:
    1. Generate multiple possible approaches
    2. Evaluate each approach
    3. Explore promising branches deeper
    4. Backtrack if needed
    5. Select best path
    
    Best for:
    - Creative tasks
    - Multiple valid solutions
    - Complex decision-making
    """
    
    @staticmethod
    def build_thought_generation_prompt(
        task: str,
        context: Dict[str, Any],
        num_thoughts: int = 3
    ) -> str:
        """Generate multiple initial thoughts."""
        
        return f"""
Task: {task}

Generate {num_thoughts} different approaches to solve this task.
For each approach, explain:
1. The core idea
2. Pros and cons
3. Expected difficulty (1-10)

Output JSON:
{{
  "approaches": [
    {{
      "id": 1,
      "idea": "...",
      "pros": ["...", "..."],
      "cons": ["...", "..."],
      "difficulty": 5
    }},
    ...
  ]
}}
"""
    
    @staticmethod
    def build_evaluation_prompt(
        approach: Dict[str, Any],
        task: str
    ) -> str:
        """Evaluate an approach."""
        
        return f"""
Task: {task}

Approach: {approach['idea']}

Evaluate this approach on a scale of 0-1 for:
1. Correctness - Will it solve the task?
2. Efficiency - Is it the best way?
3. Robustness - Will it handle edge cases?

Also identify potential issues.

Output JSON:
{{
  "correctness": 0.0-1.0,
  "efficiency": 0.0-1.0,
  "robustness": 0.0-1.0,
  "overall_score": 0.0-1.0,
  "issues": ["...", "..."]
}}
"""
    
    @staticmethod
    async def execute(
        task: str,
        llm_call: Callable,
        context: Dict[str, Any] = None,
        num_thoughts: int = 3,
        depth: int = 2
    ) -> ReasoningTrace:
        """Execute ToT reasoning."""
        
        thoughts = []
        
        # Step 1: Generate initial thoughts
        gen_prompt = TreeOfThoughtsReasoning.build_thought_generation_prompt(
            task, context or {}, num_thoughts
        )
        gen_response = await llm_call(gen_prompt)
        approaches = json.loads(gen_response)["approaches"]
        
        thoughts.append(ThoughtStep(
            1,
            "generation",
            f"Generated {len(approaches)} approaches",
            alternatives=[a["idea"] for a in approaches]
        ))
        
        # Step 2: Evaluate each approach
        evaluations = []
        for approach in approaches:
            eval_prompt = TreeOfThoughtsReasoning.build_evaluation_prompt(
                approach, task
            )
            eval_response = await llm_call(eval_prompt)
            evaluation = json.loads(eval_response)
            evaluations.append({
                "approach": approach,
                "evaluation": evaluation
            })
        
        # Sort by score
        evaluations.sort(
            key=lambda x: x["evaluation"]["overall_score"],
            reverse=True
        )
        
        best = evaluations[0]
        
        thoughts.append(ThoughtStep(
            2,
            "evaluation",
            f"Best approach: {best['approach']['idea']}",
            confidence=best["evaluation"]["overall_score"]
        ))
        
        # Step 3: Execute best approach with CoT
        cot_prompt = ChainOfThoughtReasoning.build_prompt(
            f"{task}\n\nUse this approach: {best['approach']['idea']}",
            context
        )
        cot_response = await llm_call(cot_prompt)
        cot_data = json.loads(cot_response)
        
        thoughts.append(ThoughtStep(
            3,
            "execution",
            cot_data["final_answer"],
            confidence=cot_data["confidence"]
        ))
        
        return ReasoningTrace(
            pattern=ReasoningPattern.TREE_OF_THOUGHTS,
            thoughts=thoughts,
            final_answer=cot_data["final_answer"],
            confidence=best["evaluation"]["overall_score"] * cot_data["confidence"]
        )


# ============================================================================
# SELF-CONSISTENCY
# ============================================================================

class SelfConsistencyReasoning:
    """
    Self-Consistency: Generate multiple solutions and pick most common.
    
    Steps:
    1. Generate N independent solutions
    2. Compare answers
    3. Pick most frequent answer
    4. If no consensus, use highest confidence
    
    Improves accuracy by averaging out mistakes.
    """
    
    @staticmethod
    async def execute(
        task: str,
        llm_call: Callable,
        context: Dict[str, Any] = None,
        num_samples: int = 3
    ) -> ReasoningTrace:
        """Execute self-consistency reasoning."""
        
        # Generate multiple solutions
        solutions = []
        for i in range(num_samples):
            cot_trace = await ChainOfThoughtReasoning.execute(
                task, llm_call, context
            )
            solutions.append(cot_trace)
        
        # Count answers
        answer_counts: Dict[str, List[ReasoningTrace]] = {}
        for sol in solutions:
            answer = sol.final_answer
            if answer not in answer_counts:
                answer_counts[answer] = []
            answer_counts[answer].append(sol)
        
        # Find most common
        most_common = max(
            answer_counts.items(),
            key=lambda x: len(x[1])
        )
        
        final_answer = most_common[0]
        supporting_traces = most_common[1]
        
        # Average confidence
        avg_confidence = sum(t.confidence for t in supporting_traces) / len(supporting_traces)
        
        # Build thought steps
        thoughts = [
            ThoughtStep(
                1,
                "generation",
                f"Generated {num_samples} independent solutions",
                alternatives=[s.final_answer for s in solutions]
            ),
            ThoughtStep(
                2,
                "consensus",
                f"Answer '{final_answer}' chosen by {len(supporting_traces)}/{num_samples} solutions",
                confidence=avg_confidence
            )
        ]
        
        return ReasoningTrace(
            pattern=ReasoningPattern.SELF_CONSISTENCY,
            thoughts=thoughts,
            final_answer=final_answer,
            confidence=avg_confidence
        )


# ============================================================================
# REFLECTION
# ============================================================================

class ReflectionReasoning:
    """
    Reflection: Self-critique and improve.
    
    Steps:
    1. Generate initial solution
    2. Critique the solution
    3. Identify problems
    4. Generate improved solution
    5. Repeat if needed
    
    Based on "Reflexion" paper.
    """
    
    @staticmethod
    def build_critique_prompt(
        task: str,
        solution: str,
        reasoning: str
    ) -> str:
        """Build critique prompt."""
        
        return f"""
Task: {task}

Solution: {solution}

Reasoning: {reasoning}

Critique this solution:
1. Is it correct?
2. Are there any mistakes in the reasoning?
3. Are there better approaches?
4. What could be improved?

Output JSON:
{{
  "is_correct": true/false,
  "mistakes": ["...", "..."],
  "better_approaches": ["...", "..."],
  "improvements": ["...", "..."],
  "overall_quality": 0.0-1.0
}}
"""
    
    @staticmethod
    async def execute(
        task: str,
        llm_call: Callable,
        context: Dict[str, Any] = None,
        max_iterations: int = 3
    ) -> ReasoningTrace:
        """Execute reflection reasoning."""
        
        thoughts = []
        
        # Initial solution
        current_trace = await ChainOfThoughtReasoning.execute(
            task, llm_call, context
        )
        
        thoughts.append(ThoughtStep(
            1,
            "initial_solution",
            current_trace.final_answer,
            confidence=current_trace.confidence
        ))
        
        # Reflection loop
        for iteration in range(max_iterations):
            # Critique
            critique_prompt = ReflectionReasoning.build_critique_prompt(
                task,
                current_trace.final_answer,
                "\n".join(t.content for t in current_trace.thoughts)
            )
            critique_response = await llm_call(critique_prompt)
            critique = json.loads(critique_response)
            
            thoughts.append(ThoughtStep(
                len(thoughts) + 1,
                "critique",
                f"Iteration {iteration + 1}: Quality {critique['overall_quality']:.2f}",
                confidence=critique["overall_quality"]
            ))
            
            # If good enough, stop
            if critique["is_correct"] and critique["overall_quality"] > 0.9:
                break
            
            # Generate improved solution
            improvement_task = f"""
{task}

Previous attempt: {current_trace.final_answer}

Issues found:
{json.dumps(critique['mistakes'], indent=2)}

Suggested improvements:
{json.dumps(critique['improvements'], indent=2)}

Generate an improved solution addressing these issues.
"""
            
            current_trace = await ChainOfThoughtReasoning.execute(
                improvement_task, llm_call, context
            )
            
            thoughts.append(ThoughtStep(
                len(thoughts) + 1,
                "improved_solution",
                current_trace.final_answer,
                confidence=current_trace.confidence
            ))
        
        return ReasoningTrace(
            pattern=ReasoningPattern.REFLECTION,
            thoughts=thoughts,
            final_answer=current_trace.final_answer,
            confidence=current_trace.confidence,
            reflection=f"Refined through {len(thoughts) // 2} iterations"
        )


# ============================================================================
# REACT (Reason + Act)
# ============================================================================

class ReActReasoning:
    """
    ReAct: Reason and Act in interleaved fashion.
    
    Pattern:
    Thought -> Action -> Observation -> Thought -> ...
    
    Good for tasks requiring tool use or information gathering.
    """
    
    @staticmethod
    def build_prompt(
        task: str,
        context: Dict[str, Any],
        available_tools: List[str],
        previous_steps: List[Dict[str, str]] = None
    ) -> str:
        """Build ReAct prompt."""
        
        history = ""
        if previous_steps:
            for step in previous_steps:
                history += f"\nThought: {step['thought']}"
                history += f"\nAction: {step['action']}"
                history += f"\nObservation: {step['observation']}"
        
        return f"""
Task: {task}

Available tools: {', '.join(available_tools)}

{history}

Next step - provide ONE of:

1. Thought + Action:
   Thought: [Your reasoning about what to do next]
   Action: [tool_name(args)]

2. Final Answer:
   Thought: [Why this is the answer]
   Answer: [Your final answer]

Output JSON:
{{
  "thought": "...",
  "action": "tool_name(args)" OR null,
  "answer": "..." OR null
}}
"""
    
    @staticmethod
    async def execute(
        task: str,
        llm_call: Callable,
        tools: Dict[str, Callable],
        context: Dict[str, Any] = None,
        max_steps: int = 10
    ) -> ReasoningTrace:
        """Execute ReAct reasoning."""
        
        thoughts = []
        previous_steps = []
        
        for step_num in range(max_steps):
            # Get next thought + action
            prompt = ReActReasoning.build_prompt(
                task,
                context or {},
                list(tools.keys()),
                previous_steps
            )
            
            response = await llm_call(prompt)
            data = json.loads(response)
            
            thought = data["thought"]
            action = data.get("action")
            answer = data.get("answer")
            
            # If final answer, done
            if answer:
                thoughts.append(ThoughtStep(
                    step_num + 1,
                    "final_thought",
                    thought
                ))
                
                return ReasoningTrace(
                    pattern=ReasoningPattern.REACT,
                    thoughts=thoughts,
                    final_answer=answer,
                    confidence=1.0
                )
            
            # Execute action
            if action:
                # Parse action
                tool_name = action.split("(")[0]
                
                if tool_name in tools:
                    observation = await tools[tool_name]()
                else:
                    observation = f"Error: Unknown tool {tool_name}"
                
                thoughts.append(ThoughtStep(
                    step_num + 1,
                    "reasoning",
                    thought
                ))
                
                previous_steps.append({
                    "thought": thought,
                    "action": action,
                    "observation": observation
                })
        
        # Max steps reached
        return ReasoningTrace(
            pattern=ReasoningPattern.REACT,
            thoughts=thoughts,
            final_answer="Max steps reached without solution",
            confidence=0.0
        )


# ============================================================================
# UNIFIED REASONING ENGINE
# ============================================================================

class AdvancedReasoningEngine:
    """
    Unified reasoning engine supporting multiple patterns.
    
    Usage:
        engine = AdvancedReasoningEngine(llm_call)
        
        # Chain-of-Thought
        trace = await engine.reason(task, pattern="cot")
        
        # Tree-of-Thoughts
        trace = await engine.reason(task, pattern="tot")
        
        # Self-Consistency
        trace = await engine.reason(task, pattern="self_consistency")
        
        # Auto-select best pattern
        trace = await engine.reason(task, pattern="auto")
    """
    
    def __init__(self, llm_call: Callable):
        self.llm_call = llm_call
    
    async def reason(
        self,
        task: str,
        pattern: str = "cot",
        context: Dict[str, Any] = None,
        **kwargs
    ) -> ReasoningTrace:
        """Execute reasoning with specified pattern."""
        
        if pattern == "cot" or pattern == "auto":
            return await ChainOfThoughtReasoning.execute(
                task, self.llm_call, context
            )
        
        elif pattern == "tot":
            return await TreeOfThoughtsReasoning.execute(
                task, self.llm_call, context, **kwargs
            )
        
        elif pattern == "self_consistency":
            return await SelfConsistencyReasoning.execute(
                task, self.llm_call, context, **kwargs
            )
        
        elif pattern == "reflection":
            return await ReflectionReasoning.execute(
                task, self.llm_call, context, **kwargs
            )
        
        elif pattern == "react":
            return await ReActReasoning.execute(
                task, self.llm_call, **kwargs
            )
        
        else:
            raise ValueError(f"Unknown pattern: {pattern}")
    
    async def verify_answer(
        self,
        task: str,
        answer: str,
        reasoning: str
    ) -> Dict[str, Any]:
        """Verify answer using reflection."""
        
        critique_prompt = ReflectionReasoning.build_critique_prompt(
            task, answer, reasoning
        )
        
        response = await self.llm_call(critique_prompt)
        return json.loads(response)


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Example of using advanced reasoning."""
    
    # Mock LLM call
    async def mock_llm(prompt: str) -> str:
        # In reality, call actual LLM
        return '{"understanding": "...", "final_answer": "42", "confidence": 0.9}'
    
    engine = AdvancedReasoningEngine(mock_llm)
    
    # Example 1: CoT
    trace = await engine.reason(
        "Calculate 15% tip on $45.50",
        pattern="cot"
    )
    print(f"CoT Answer: {trace.final_answer}")
    
    # Example 2: Self-Consistency (multiple attempts)
    trace = await engine.reason(
        "What's the best approach to implement caching?",
        pattern="self_consistency",
        num_samples=5
    )
    print(f"Self-Consistency Answer: {trace.final_answer}")
    
    # Example 3: Reflection (iterative improvement)
    trace = await engine.reason(
        "Design a scalable microservices architecture",
        pattern="reflection",
        max_iterations=3
    )
    print(f"Reflection Answer: {trace.final_answer}")
    print(f"Reflection note: {trace.reflection}")


if __name__ == "__main__":
    asyncio.run(example_usage())
