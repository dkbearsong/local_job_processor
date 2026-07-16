import logging
import sys
import os
import json
from datetime import datetime
from typing import Any

# Check for debug flag to log full prompts and responses
DEBUG_PROMPTS = os.getenv("DEBUG_PROMPTS", "").lower() in ("1", "true", "yes")

def setup_logging(log_file="app_errors.log"):
    """
    Configures the logging system.
    - Console output: Shows INFO level and above (useful for debugging).
    - File output: Records ERROR level and above (captures crashes).
    """
    # Create a root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 1. File Handler: Saves errors to the specified file
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(formatter)

    # 2. Console Handler: Prints info/errors to your terminal
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Add handlers to the root logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

def exception_handler(exc_type, exc_value, exc_traceback):
    """
    A global hook that catches any unhandled exceptions and logs them 
    before the program exits.
    """
    # Allow KeyboardInterrupt (Ctrl+C) to exit normally without being logged as an error
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Log the unhandled exception with full traceback details
    logging.error("Uncaught Exception:", exc_info=(exc_type, exc_value, exc_traceback))

def log_debug_prompt(step_name: str, rendered_prompt: str, response: Any):
    """
    Log the full rendered prompt and response for a step to a debug log file.
    Only active when DEBUG_PROMPTS env var is set to true/1/yes.
    """
    if not DEBUG_PROMPTS:
        return

    os.makedirs("output", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"output/debug_prompts_{timestamp}.log"

    with open(log_filename, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"STEP: {step_name}\n")
        f.write(f"TIMESTAMP: {datetime.now().isoformat()}\n")
        f.write(f"{'='*80}\n")
        f.write("\n--- FULL PROMPT SENT TO LLM ---\n")
        f.write(rendered_prompt)
        f.write("\n\n--- FULL RESPONSE FROM LLM ---\n")
        if isinstance(response, dict):
            f.write(json.dumps(response, indent=2, default=str))
        else:
            f.write(str(response))
        f.write(f"\n{'='*80}\n\n")

    logging.info(f"Debug prompt/response logged to {log_filename}")