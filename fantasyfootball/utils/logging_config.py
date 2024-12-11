import json
import logging.config
import sys

def setup_logging(path=r'config\logger.json', default_level=logging.INFO):
    """Setup logging configuration from a JSON file."""
    try:
        with open(path, 'rt', encoding='utf-8') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    except Exception as e:
        print(f"Error in loading logging configuration: {e}")
        logging.basicConfig(level=default_level)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Fallback for older Python versions without `reconfigure`
        pass

    # Logging carveouts
    logging.getLogger('snowflake.connector').setLevel(logging.WARNING)

if __name__ == '__main__':
    setup_logging()

    # Now you can use logging in your application
    logger = logging.getLogger(__name__)

    logger.info("This is an info message with Unicode: 🌟")
    logger.debug("This is a debug message")
