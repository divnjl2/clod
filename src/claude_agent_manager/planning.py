"""
Agent Planning & Reasoning System
==================================

Система планирования задач с:
- Разбиение глобальной задачи на подзадачи
- Todo листы для каждого агента
- Chain-of-thought reasoning
- Иерархия моделей по сложности
"""

from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import json


class TaskComplexity(Enum):
    """Сложность задачи."""
    TRIVIAL = 1      # Простейшие операции (read file, format code)
    SIMPLE = 2       # Простые задачи (write test, add endpoint)
    MEDIUM = 3       # Средние задачи (implement feature, refactor)
    COMPLEX = 4      # Сложные задачи (design architecture, debug issue)
    EXPERT = 5       # Экспертные задачи (system design, optimization)


class ModelTier(Enum):
    """Уровень модели."""
    FAST = "fast"           # haiku, gpt-3.5-turbo
    BALANCED = "balanced"   # sonnet, gpt-4o
    SMART = "smart"         # opus, gpt-4, o1
    CUSTOM = "custom"       # OpenRouter custom models
    LOCAL = "local"         # Local models (ollama, etc)


@dataclass
class ModelConfig:
    """Конфигурация модели."""
    tier: ModelTier
    model_name: str
    api_provider: str  # "anthropic", "openai", "openrouter", "local"
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # For OpenRouter or local
    max_tokens: int = 4096
    temperature: float = 0.7
    
    # Стоимость (для оптимизации)
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0


# Предустановленные конфигурации моделей
PREDEFINED_MODELS = {
    # Anthropic
    "claude-haiku-4": ModelConfig(
        tier=ModelTier.FAST,
        model_name="claude-haiku-4-20250514",
        api_provider="anthropic",
        max_tokens=4096,
        temperature=0.7,
        cost_per_1k_input=0.0008,
        cost_per_1k_output=0.004
    ),
    
    "claude-sonnet-4": ModelConfig(
        tier=ModelTier.BALANCED,
        model_name="claude-sonnet-4-20250514",
        api_provider="anthropic",
        max_tokens=8192,
        temperature=0.7,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015
    ),
    
    "claude-opus-4": ModelConfig(
        tier=ModelTier.SMART,
        model_name="claude-opus-4-20250514",
        api_provider="anthropic",
        max_tokens=8192,
        temperature=0.7,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075
    ),
    
    # OpenAI
    "gpt-4o-mini": ModelConfig(
        tier=ModelTier.FAST,
        model_name="gpt-4o-mini",
        api_provider="openai",
        max_tokens=4096,
        temperature=0.7,
        cost_per_1k_input=0.00015,
        cost_per_1k_output=0.0006
    ),
    
    "gpt-4o": ModelConfig(
        tier=ModelTier.BALANCED,
        model_name="gpt-4o",
        api_provider="openai",
        max_tokens=4096,
        temperature=0.7,
        cost_per_1k_input=0.005,
        cost_per_1k_output=0.015
    ),
    
    "o1": ModelConfig(
        tier=ModelTier.SMART,
        model_name="o1-preview",
        api_provider="openai",
        max_tokens=8192,
        temperature=1.0,  # o1 doesn't support temperature
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.06
    ),
    
    # Local (Ollama)
    "llama3-70b": ModelConfig(
        tier=ModelTier.BALANCED,
        model_name="llama3:70b",
        api_provider="local",
        base_url="http://localhost:11434",
        max_tokens=4096,
        temperature=0.7,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0
    ),
    
    "deepseek-coder": ModelConfig(
        tier=ModelTier.FAST,
        model_name="deepseek-coder:33b",
        api_provider="local",
        base_url="http://localhost:11434",
        max_tokens=4096,
        temperature=0.7,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0
    )
}


@dataclass
class SubTask:
    """Подзадача в плане агента."""
    id: str
    description: str
    complexity: TaskComplexity
    estimated_time: int  # minutes
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, done, failed
    reasoning: Optional[str] = None
    result: Optional[str] = None
    model_used: Optional[str] = None
    actual_time: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "complexity": self.complexity.name,
            "estimated_time": self.estimated_time,
            "dependencies": self.dependencies,
            "status": self.status,
            "reasoning": self.reasoning,
            "result": self.result,
            "model_used": self.model_used,
            "actual_time": self.actual_time
        }


@dataclass
class AgentPlan:
    """План работы агента."""
    agent_id: str
    agent_role: str
    global_task: str
    subtasks: List[SubTask]
    created_at: datetime = field(default_factory=datetime.now)
    
    # Model selection strategy
    auto_select_model: bool = True  # Автоматически выбирать модель по сложности
    default_model: str = "claude-sonnet-4"
    model_mapping: Dict[str, str] = field(default_factory=dict)  # complexity -> model
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "global_task": self.global_task,
            "subtasks": [t.to_dict() for t in self.subtasks],
            "created_at": self.created_at.isoformat(),
            "auto_select_model": self.auto_select_model,
            "default_model": self.default_model,
            "model_mapping": self.model_mapping
        }


class TaskPlanner:
    """
    Планировщик задач для агента.
    
    Разбивает глобальную задачу на подзадачи с учетом:
    - Сложности каждой подзадачи
    - Зависимостей между подзадачами
    - Оценки времени
    """
    
    def __init__(self, model_config: ModelConfig = None):
        self.model_config = model_config or PREDEFINED_MODELS["claude-sonnet-4"]
    
    async def create_plan(
        self,
        agent_role: str,
        global_task: str,
        context: Dict[str, Any] = None
    ) -> AgentPlan:
        """
        Создать план для агента.
        
        Args:
            agent_role: Роль агента (backend, frontend, etc)
            global_task: Глобальная задача
            context: Контекст от других агентов
        
        Returns:
            AgentPlan с подзадачами
        """
        
        # Prompt для планирования
        planning_prompt = f"""
You are a {agent_role} planning your work.

Global Task:
{global_task}

Context from other agents:
{json.dumps(context or {}, indent=2)}

Create a detailed plan by breaking down the task into subtasks.
For each subtask, provide:
1. Clear description
2. Complexity (TRIVIAL, SIMPLE, MEDIUM, COMPLEX, EXPERT)
3. Estimated time in minutes
4. Dependencies on other subtasks
5. Reasoning why this subtask is needed

Output JSON format:
{{
  "subtasks": [
    {{
      "id": "task_1",
      "description": "...",
      "complexity": "MEDIUM",
      "estimated_time": 30,
      "dependencies": [],
      "reasoning": "..."
    }},
    ...
  ]
}}

Think step by step. Consider:
- What needs to be done first?
- What depends on what?
- What's the most efficient order?
- What can be parallelized?

Generate the plan:
"""
        
        # Call LLM для планирования
        result = await self._call_llm(planning_prompt)
        
        # Parse JSON
        plan_data = json.loads(result)
        
        # Create subtasks
        subtasks = []
        for i, task_data in enumerate(plan_data["subtasks"]):
            subtask = SubTask(
                id=task_data["id"],
                description=task_data["description"],
                complexity=TaskComplexity[task_data["complexity"]],
                estimated_time=task_data["estimated_time"],
                dependencies=task_data.get("dependencies", []),
                reasoning=task_data.get("reasoning")
            )
            subtasks.append(subtask)
        
        # Create plan
        plan = AgentPlan(
            agent_id=f"agent_{agent_role}",
            agent_role=agent_role,
            global_task=global_task,
            subtasks=subtasks
        )
        
        return plan
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM для генерации плана."""
        # TODO: Реальный вызов LLM через Anthropic SDK
        # Пока заглушка
        return """
{
  "subtasks": [
    {
      "id": "task_1",
      "description": "Read architecture from memory",
      "complexity": "SIMPLE",
      "estimated_time": 5,
      "dependencies": [],
      "reasoning": "Need to understand the system design before implementing"
    },
    {
      "id": "task_2",
      "description": "Design payment API endpoints",
      "complexity": "MEDIUM",
      "estimated_time": 20,
      "dependencies": ["task_1"],
      "reasoning": "Define the API contract based on architecture"
    },
    {
      "id": "task_3",
      "description": "Write tests for /pay endpoint",
      "complexity": "SIMPLE",
      "estimated_time": 15,
      "dependencies": ["task_2"],
      "reasoning": "TDD approach - tests first"
    },
    {
      "id": "task_4",
      "description": "Implement /pay endpoint",
      "complexity": "MEDIUM",
      "estimated_time": 30,
      "dependencies": ["task_3"],
      "reasoning": "Implement the actual endpoint logic"
    },
    {
      "id": "task_5",
      "description": "Add error handling",
      "complexity": "SIMPLE",
      "estimated_time": 10,
      "dependencies": ["task_4"],
      "reasoning": "Ensure robust error handling"
    }
  ]
}
"""


class ModelSelector:
    """
    Выбирает модель для задачи на основе сложности.
    
    Стратегия:
    - TRIVIAL/SIMPLE → Fast model (haiku, gpt-4o-mini)
    - MEDIUM → Balanced model (sonnet, gpt-4o)
    - COMPLEX/EXPERT → Smart model (opus, o1)
    """
    
    def __init__(self, available_models: Dict[str, ModelConfig] = None):
        self.available_models = available_models or PREDEFINED_MODELS
    
    def select_model(
        self,
        complexity: TaskComplexity,
        custom_mapping: Dict[str, str] = None,
        default_model: str = None
    ) -> ModelConfig:
        """
        Выбрать модель для задачи.
        
        Args:
            complexity: Сложность задачи
            custom_mapping: Кастомный mapping сложность -> модель
            default_model: Модель по умолчанию
        
        Returns:
            ModelConfig для использования
        """
        
        # Custom mapping имеет приоритет
        if custom_mapping and complexity.name in custom_mapping:
            model_name = custom_mapping[complexity.name]
            return self.available_models[model_name]
        
        # Default automatic selection
        if complexity in [TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE]:
            # Fast models for simple tasks
            return self.available_models["claude-haiku-4"]
        
        elif complexity == TaskComplexity.MEDIUM:
            # Balanced models for medium tasks
            return self.available_models["claude-sonnet-4"]
        
        else:  # COMPLEX or EXPERT
            # Smart models for complex tasks
            return self.available_models["claude-opus-4"]
    
    def estimate_cost(
        self,
        subtasks: List[SubTask],
        avg_input_tokens: int = 2000,
        avg_output_tokens: int = 1000
    ) -> Dict[str, float]:
        """
        Оценить стоимость выполнения плана.
        
        Returns:
            Dict с разбивкой стоимости по моделям
        """
        
        costs = {}
        
        for task in subtasks:
            model = self.select_model(task.complexity)
            
            input_cost = (avg_input_tokens / 1000) * model.cost_per_1k_input
            output_cost = (avg_output_tokens / 1000) * model.cost_per_1k_output
            total_cost = input_cost + output_cost
            
            if model.model_name not in costs:
                costs[model.model_name] = {
                    "count": 0,
                    "total_cost": 0.0
                }
            
            costs[model.model_name]["count"] += 1
            costs[model.model_name]["total_cost"] += total_cost
        
        return costs


class ReasoningEngine:
    """
    Reasoning engine для выполнения задач с CoT.
    
    Chain-of-Thought reasoning для улучшения качества:
    1. Понять задачу
    2. Разбить на шаги
    3. Выполнить каждый шаг
    4. Проверить результат
    """
    
    def __init__(self, model_config: ModelConfig):
        self.model_config = model_config
    
    async def execute_with_reasoning(
        self,
        subtask: SubTask,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Выполнить подзадачу с reasoning.
        
        Returns:
            Dict с reasoning steps и результатом
        """
        
        # Chain-of-Thought prompt
        reasoning_prompt = f"""
Task: {subtask.description}

Context:
{json.dumps(context, indent=2)}

Think step by step:

1. UNDERSTAND: What exactly needs to be done?
   [Your analysis here]

2. PLAN: What are the steps?
   [List specific steps]

3. EXECUTE: Implement each step
   [Implementation]

4. VERIFY: Is the result correct?
   [Verification]

Provide your response in JSON format:
{{
  "understanding": "...",
  "steps": ["step 1", "step 2", ...],
  "implementation": "...",
  "verification": "...",
  "result": "..."
}}
"""
        
        start_time = datetime.now()
        
        # Call LLM
        response = await self._call_llm(reasoning_prompt)
        
        end_time = datetime.now()
        actual_time = (end_time - start_time).seconds // 60
        
        # Parse response
        reasoning_data = json.loads(response)
        
        return {
            "reasoning_steps": [
                f"Understanding: {reasoning_data['understanding']}",
                f"Steps: {', '.join(reasoning_data['steps'])}",
                f"Implementation: {reasoning_data['implementation']}",
                f"Verification: {reasoning_data['verification']}"
            ],
            "result": reasoning_data["result"],
            "actual_time": actual_time,
            "model_used": self.model_config.model_name
        }
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM."""
        # TODO: Реальный вызов
        return """
{
  "understanding": "Need to implement /pay endpoint that integrates with CryptoBot API",
  "steps": [
    "Define endpoint signature",
    "Validate input parameters",
    "Call CryptoBot API",
    "Handle response",
    "Return payment URL"
  ],
  "implementation": "async def create_payment(amount: float): ...",
  "verification": "Tested with sample payment, URL generated correctly",
  "result": "Payment endpoint implemented successfully"
}
"""


class TodoManager:
    """
    Управление todo листом агента.
    
    Отслеживает:
    - Какие задачи выполнены
    - Какие в процессе
    - Какие заблокированы
    - Progress агента
    """
    
    def __init__(self, plan: AgentPlan):
        self.plan = plan
        self.current_task: Optional[SubTask] = None
    
    def get_next_task(self) -> Optional[SubTask]:
        """Получить следующую доступную задачу."""
        
        for task in self.plan.subtasks:
            if task.status != "pending":
                continue
            
            # Check dependencies
            deps_done = all(
                self._find_task(dep_id).status == "done"
                for dep_id in task.dependencies
            )
            
            if deps_done:
                return task
        
        return None
    
    def start_task(self, task_id: str):
        """Начать выполнение задачи."""
        task = self._find_task(task_id)
        task.status = "in_progress"
        self.current_task = task
    
    def complete_task(
        self,
        task_id: str,
        result: str,
        reasoning: str = None,
        model_used: str = None,
        actual_time: int = None
    ):
        """Завершить задачу."""
        task = self._find_task(task_id)
        task.status = "done"
        task.result = result
        task.reasoning = reasoning
        task.model_used = model_used
        task.actual_time = actual_time
        
        if self.current_task and self.current_task.id == task_id:
            self.current_task = None
    
    def fail_task(self, task_id: str, error: str):
        """Отметить задачу как failed."""
        task = self._find_task(task_id)
        task.status = "failed"
        task.result = f"Failed: {error}"
    
    def get_progress(self) -> float:
        """Получить прогресс (0-100)."""
        done = sum(1 for t in self.plan.subtasks if t.status == "done")
        total = len(self.plan.subtasks)
        return (done / total * 100) if total > 0 else 0
    
    def get_todo_list(self) -> Dict[str, List[SubTask]]:
        """Получить todo лист."""
        return {
            "pending": [t for t in self.plan.subtasks if t.status == "pending"],
            "in_progress": [t for t in self.plan.subtasks if t.status == "in_progress"],
            "done": [t for t in self.plan.subtasks if t.status == "done"],
            "failed": [t for t in self.plan.subtasks if t.status == "failed"]
        }
    
    def _find_task(self, task_id: str) -> SubTask:
        """Найти задачу по ID."""
        for task in self.plan.subtasks:
            if task.id == task_id:
                return task
        raise ValueError(f"Task {task_id} not found")


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def example_usage():
    """Пример использования planning системы."""
    
    # 1. Create planner
    planner = TaskPlanner()
    
    # 2. Create plan for agent
    plan = await planner.create_plan(
        agent_role="backend",
        global_task="Implement payment integration with CryptoBot",
        context={"api_contracts": "..."}
    )
    
    print("📋 Plan created:")
    print(f"  Total subtasks: {len(plan.subtasks)}")
    print(f"  Estimated time: {sum(t.estimated_time for t in plan.subtasks)} min")
    
    # 3. Setup model selector
    selector = ModelSelector()
    
    # 4. Configure custom model mapping
    plan.model_mapping = {
        "TRIVIAL": "claude-haiku-4",
        "SIMPLE": "claude-haiku-4",
        "MEDIUM": "claude-sonnet-4",
        "COMPLEX": "claude-opus-4",
        "EXPERT": "o1"
    }
    
    # 5. Estimate cost
    costs = selector.estimate_cost(plan.subtasks)
    print("\n💰 Estimated costs:")
    for model, data in costs.items():
        print(f"  {model}: ${data['total_cost']:.4f} ({data['count']} tasks)")
    
    # 6. Create todo manager
    todo = TodoManager(plan)
    
    # 7. Execute tasks
    while True:
        next_task = todo.get_next_task()
        if not next_task:
            break
        
        print(f"\n📌 Starting: {next_task.description}")
        print(f"   Complexity: {next_task.complexity.name}")
        
        # Select model
        model = selector.select_model(
            next_task.complexity,
            custom_mapping=plan.model_mapping
        )
        print(f"   Model: {model.model_name}")
        
        # Start task
        todo.start_task(next_task.id)
        
        # Execute with reasoning
        reasoning_engine = ReasoningEngine(model)
        result = await reasoning_engine.execute_with_reasoning(
            next_task,
            context={}
        )
        
        # Complete task
        todo.complete_task(
            next_task.id,
            result=result["result"],
            reasoning="\n".join(result["reasoning_steps"]),
            model_used=result["model_used"],
            actual_time=result["actual_time"]
        )
        
        print(f"   ✅ Done!")
        print(f"   Progress: {todo.get_progress():.1f}%")
    
    print("\n🎉 All tasks completed!")
    
    # 8. Show final todo list
    todo_list = todo.get_todo_list()
    print(f"\n📊 Summary:")
    print(f"  Done: {len(todo_list['done'])}")
    print(f"  Failed: {len(todo_list['failed'])}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
