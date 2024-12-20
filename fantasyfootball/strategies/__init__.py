from pathlib import Path
import pkgutil
import importlib
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Directory containing this __init__.py file
directory = Path(__file__).parent

# Dynamically import all modules
for _, module_name, _ in pkgutil.iter_modules([str(directory)]):
    try:
        logger.info(f"Importing module: {module_name}")
        importlib.import_module(f'.{module_name}', __name__)
    except Exception as e:
        logger.error(f"Failed to import {module_name}: {e}")
