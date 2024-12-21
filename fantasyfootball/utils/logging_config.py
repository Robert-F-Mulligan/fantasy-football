import logging
import logging.config
import sys
import json
import atexit

def setup_logging(path=r'config\logger.json', default_level=logging.INFO):
    """Setup logging configuration from a JSON file."""
    try:
        with open(path, 'rt', encoding='utf-8') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    except Exception as e:
        print(f"Error in loading logging configuration: {e}")
        if not logging.getLogger().hasHandlers():
            logging.basicConfig(level=default_level)

    # Logging carveouts
    logging.getLogger('snowflake.connector').setLevel(logging.WARNING)

    # Cleanup on exit
    atexit.register(logging.shutdown)

if __name__ == '__main__':
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
