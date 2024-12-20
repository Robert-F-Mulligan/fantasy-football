from pathlib import Path
import pkgutil
import importlib

# Determine the directory containing this __init__.py file
directory = Path(__file__).parent

# Iterate over all modules in the directory and import them
for _, module_name, _ in pkgutil.iter_modules([str(directory)]):
    # Import the module, which will execute its top-level code including class registrations
    importlib.import_module(f'.{module_name}', __name__)