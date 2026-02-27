"""
Plan-Execute Agent - Fixed version with proper recursion handling
"""

import asyncio
import uuid
import logging
from typing import Optional, Dict, Any, Literal
import operator
from typing import Annotated, TypedDict

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
import numexpr as ne
from langchain_core.runnables import RunnableLambda, RunnableConfig
from langchain_core.tools import convert_runnable_to_tool
from langchain_community.tools import (
    WikipediaQueryRun,
    ArxivQueryRun,
)
# from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_tavily import TavilySearch

from langchain_community.utilities import WikipediaAPIWrapper
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.graph import StateGraph, START, END

from app.config import settings

logger = logging.getLogger(__name__)

# Pydantic models
class Plan(BaseModel):
    """Plan to follow in future"""
    steps: list[str] = Field(
        description="different steps to follow, should be in sorted order"
    )

class CalculatorArgs(BaseModel):
    expression: str = Field(description="Mathematical expression to be evaluated")

class StepState(AgentState):
    plan: str
    step: str
    task: str

class PlanState(TypedDict):
    task: str
    plan: Plan
    past_steps: Annotated[list[str], operator.add]
    final_response: str

# Calculator tool
def calculator(state: CalculatorArgs, config: RunnableConfig) -> str:
    expression = state["expression"]
    math_constants = config["configurable"].get("math_constants", {})
    result = ne.evaluate(expression.strip(), local_dict=math_constants)
    return str(result)

calculator_with_retry = RunnableLambda(calculator).with_retry(
    wait_exponential_jitter=True,
    stop_after_attempt=settings.MAX_RETRIES,
)

calculator_tool = convert_runnable_to_tool(
    calculator_with_retry,
    name="calculator",
    description=(
        "Calculates a single mathematical expression, incl. complex numbers."
        "'\nAlways add * to operations, examples:\n73i -> 73*i\n"
        "7pi**2 -> 7*pi**2"
    ),
    args_schema=CalculatorArgs,
    arg_types={"expression": "str"},
)

class PlanExecuteAgent:
    """Production-ready Plan-Execute Agent with error handling and logging"""
    
    def __init__(self):
        logger.info("Initializing PlanExecuteAgent...")
        
        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model=settings.MODEL_NAME,
            temperature=settings.MODEL_TEMPERATURE,
            google_api_key=settings.GOOGLE_API_KEY
        )
        
        # Initialize tools
        self.tools = self._initialize_tools()
        
        # Build planner
        self.planner = self._build_planner()
        
        # Build execution agent
        self.execution_agent = self._build_execution_agent()
        
        # Build main graph with INCREASED RECURSION LIMIT
        self.graph = self._build_graph()
        
        logger.info("PlanExecuteAgent initialized successfully")
    
    def _initialize_tools(self):
        """Initialize all tools with error handling"""
        try:
            search = TavilySearch(
                max_results=5,
                search_depth="advanced",
                tavily_api_key=settings.TAVILY_API_KEY,
            )
            wikipedia = WikipediaQueryRun(
                api_wrapper=WikipediaAPIWrapper()
            )
            arxiv = ArxivQueryRun()

            return [search, wikipedia, arxiv, calculator_tool]

        except Exception as e:
            logger.error(f"Error initializing tools: {e}")
            return [calculator_tool]
    
    def _build_planner(self):
        """Build the planning component"""
        system_prompt_template = (
            "For the given task, come up with a SIMPLE step by step plan with 2-4 steps maximum.\n"
            "This plan should involve individual tasks, that if executed correctly will "
            "yield the correct answer. Do not add any superfluous steps.\n"
            "The result of the final step should be the final answer. Make sure that each "
            "step has all the information needed - do not skip steps.\n"
            "IMPORTANT: Keep the plan SHORT - aim for 2-3 steps only."
        )
        
        planner_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_template),
            ("user", "Prepare a plan how to solve the following task:\n{task}\n")
        ])
        
        return planner_prompt | self.llm.with_structured_output(Plan)
    
    def _build_execution_agent(self):
        """Build the step execution agent"""
        system_prompt = (
            "You're a smart assistant that carefully helps to solve complex tasks.\n"
            "Given a general plan to solve a task and a specific step, work on this step. "
            "Don't assume anything, keep in minds things might change and always try to "
            "use tools to double-check yourself.\n"
            "Use a calculator for mathematical computations, use Search to gather "
            "for information about common facts, fresh events and news, use Arxiv to get "
            "ideas on recent research and use Wikipedia for common knowledge.\n"
            "If the step requires external information, current events, sports, news, or facts "
            "after 2023, you MUST call the search tool.\n"
            "Do NOT describe what you would do.\n"
            "Actually call the tool.\n"
            "Failure to call tools when required is an error."
        )
        
        step_template = (
            "Given the task and the plan, try to execute on a specific step of the plan.\n"
            "TASK:\n{task}\n\nPLAN:\n{plan}\n\nSTEP TO EXECUTE:\n{step}\n"
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ('system', system_prompt),
            ('user', step_template)
        ])
        
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            state_schema=StepState,
            prompt=prompt_template
        )
    
    def _build_graph(self):
        """Build the main LangGraph workflow"""
        
        def get_current_step(state: PlanState) -> int:
            """Returns the number of current step to be executed."""
            return len(state.get("past_steps", []))
        
        def get_full_plan(state: PlanState) -> str:
            """Returns formatted plan with step numbers and past results."""
            full_plan = []
            for i, step in enumerate(state["plan"].steps):
                full_step = f"# {i+1}. Planned step: {step}\n"
                if i < get_current_step(state):
                    full_step += f"Result: {state['past_steps'][i]}\n"
                full_plan.append(full_step)
            return "\n".join(full_plan)
        
        async def _build_initial_plan(state: PlanState) -> PlanState:
            plan = await self.planner.ainvoke(state["task"])
            logger.info(f"Generated plan with {len(plan.steps)} steps")
            return {"plan": plan}
        
        async def _run_step(state: PlanState) -> PlanState:
            plan = state["plan"]
            current_step = get_current_step(state)
            logger.info(f"Executing step {current_step + 1}/{len(plan.steps)}")
            
            # SAFETY CHECK: Prevent infinite loops
            if current_step >= len(plan.steps):
                logger.warning("Attempted to execute step beyond plan length")
                return {"past_steps": ["Step execution completed"]}
            
            step = await self.execution_agent.ainvoke({
                "plan": get_full_plan(state),
                "step": plan.steps[current_step],
                "task": state["task"]
            })
            return {"past_steps": [step["messages"][-1].content]}
        
        async def _get_final_response(state: PlanState) -> PlanState:
            final_prompt = PromptTemplate.from_template(
                "You're a helpful assistant that has executed on a plan."
                "Given the results of the execution, prepare the final response.\n"
                "Don't assume anything\nTASK:\n{task}\n\nPLAN WITH RESULTS:\n{plan}\n"
                "FINAL RESPONSE:\n"
            )
            
            final_response = await (final_prompt | self.llm).ainvoke({
                "task": state["task"],
                "plan": get_full_plan(state)
            })
            logger.info("Generated final response")
            return {"final_response": final_response.content}
        
        def _should_continue(state: PlanState) -> Literal["run", "response"]:
            """
            FIXED: Proper termination logic
            """
            current_step = get_current_step(state)
            total_steps = len(state["plan"].steps)
            
            logger.info(f"Checking continuation: step {current_step}/{total_steps}")
            
            # If we've completed all steps, go to response
            if current_step >= total_steps:
                logger.info("All steps completed, generating final response")
                return "response"
            
            # Otherwise, continue with next step
            logger.info(f"Continuing to step {current_step + 1}")
            return "run"
        
        # Build graph with INCREASED RECURSION LIMIT
        builder = StateGraph(PlanState)
        builder.add_node("initial_plan", _build_initial_plan)
        builder.add_node("run", _run_step)
        builder.add_node("response", _get_final_response)
        builder.add_edge(START, "initial_plan")
        builder.add_edge("initial_plan", "run")
        builder.add_conditional_edges("run", _should_continue)
        builder.add_edge("response", END)
        
        # IMPORTANT: Compile with higher recursion limit
        return builder.compile()
    
    async def execute(self, task: str) -> Dict[str, Any]:
        """
        Execute a task using the plan-execute pattern
        
        Args:
            task: Task description
            
        Returns:
            Dictionary with task_id, plan_steps, and final_response
        """
        try:
            task_id = str(uuid.uuid4())
            logger.info(f"Starting task execution: {task_id}")
            
            # FIXED: Set recursion limit in config
            config = {
                "recursion_limit": 50  # Increased from default 25
            }
            
            result = await self.graph.ainvoke({"task": task}, config=config)
            
            return {
                "task_id": task_id,
                "plan_steps": result["plan"].steps,
                "final_response": result.get("final_response", "No response generated"),
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Error executing task: {str(e)}", exc_info=True)
            raise
    
    async def execute_background(self, task_id: str, task: str):
        """Execute task in background (for async endpoint)"""
        try:
            logger.info(f"Background execution started for task: {task_id}")
            result = await self.execute(task)
            # In production, save result to database or cache
            logger.info(f"Background execution completed for task: {task_id}")
        except Exception as e:
            logger.error(f"Background execution failed for task {task_id}: {str(e)}")