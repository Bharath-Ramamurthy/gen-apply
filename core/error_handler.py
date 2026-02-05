# core/error_handler.py

import inspect
from typing import Optional, Callable
import os

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from app.connectors.diagnostic_tools import LANGCHAIN_TOOLS
from core.logger import get_logger
from .prompt_loader import PROMPTS

logger = get_logger(__name__)

# -----------------------------
# Initialize Diagnostic Agent (Runnable-based)
# -----------------------------

try:
    llm = ChatOpenAI(
        temperature=0,
        openai_api_base=os.getenv("DIAGNOSTIC_TOOL_CON_URL"),
        model=os.getenv("DIAGNOSTIC_TOOL_CON_MODEL"),
        openai_api_key=os.getenv("DIAGNOSTIC_TOOL_CON_API_TOKEN"),
    )

    if "error_handler" not in PROMPTS:
        raise ValueError("Prompt 'error_handler' not found in PROMPTS")

    diagnostic_prompt = ChatPromptTemplate.from_template(
        PROMPTS["error_handler"].template
    )

    # Runnable diagnostic agent
    diagnostic_agent = (
        {
            "connector_type": lambda x: x["connector_type"],
            "error": lambda x: x["error"],
        }
        | diagnostic_prompt
        | llm
    )

except Exception as init_error:
    logger.critical(
        f"Failed to initialize diagnostic agent: {init_error}",
        exc_info=True,
    )
    diagnostic_agent = None


# -----------------------------
# Tool Function Mapping
# -----------------------------
TOOL_FUNC_MAP = {
    "switch connector": "FailoverSwitchConnector",
    "switch config": "FailoverSwitchConfig",
    "switch model": "FailoverSwitchModel",
    "switch token": "FailoverSwitchToken",
    "switch url": "FailoverSwitchUrl",
    "retry after delay": "RetryAfterDelay",
}


# -----------------------------
# Core Error Handler
# -----------------------------
def handle_error(
    error: Exception,
    task: str,
    retry_callback: Optional[Callable[..., dict]] = None,
) -> dict:
    """
    Centralized error handler that uses a LangChain diagnostic agent
    (Runnable-based) to diagnose and fix connector issues.
    """

    if not diagnostic_agent:
        logger.error("Diagnostic agent not initialized — skipping recovery.")
        return {"status": "fail", "error_message": str(error)}

    try:
        logger.info(
            f"Running diagnostic agent for task='{task}', error='{error}'"
        )

        # 1️⃣ Invoke diagnostic agent
        response = diagnostic_agent.invoke(
            {
                "connector_type": task.lower(),
                "error": str(error),
            }
        )

        action = response.content.strip().lower()
        logger.info(f"Diagnostic agent action: {action}")

        # 2️⃣ Match action to tool
        selected_tool_name = TOOL_FUNC_MAP.get(action)
        if not selected_tool_name:
            logger.warning(f"No matching tool for response '{action}'")
            return {
                "status": "fail",
                "error_message": f"No diagnostic action found for '{action}'",
            }

        # 3️⃣ Locate tool
        tool = next(
            (t for t in LANGCHAIN_TOOLS if t.name == selected_tool_name),
            None,
        )
        if not tool:
            logger.error(f"Tool '{selected_tool_name}' not registered")
            return {
                "status": "fail",
                "error_message": f"Tool '{selected_tool_name}' not registered",
            }

        # 4️⃣ Execute tool
        logger.info(
            f"Executing recovery tool '{selected_tool_name}' for task '{task}'"
        )
        sig = inspect.signature(tool.func)
        accepted_args = {
            k: v
            for k, v in {"task": task}.items()
            if k in sig.parameters
        }
        tool.func(**accepted_args)

        # 5️⃣ Retry original operation
        if retry_callback:
            logger.info(f"Retrying task '{task}' after recovery")
            agent_instance = retry_callback()
            return agent_instance.run()

        return {
            "status": "success",
            "message": f"Tool '{selected_tool_name}' executed successfully",
        }

    except Exception as e:
        logger.critical(
            f"Diagnostic handler execution failed: {e}",
            exc_info=True,
        )
        return {"status": "fail", "error_message": str(e)}
