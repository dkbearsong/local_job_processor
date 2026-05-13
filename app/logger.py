import logging
import sys

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