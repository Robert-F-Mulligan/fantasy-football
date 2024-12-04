import json
import logging.config

def setup_logging(path=r'config\logger.json', default_level=logging.INFO):
    """Setup logging configuration from a JSON file."""
    try:
        with open(path, 'rt') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    except Exception as e:
        print(f"Error in loading logging configuration: {e}")
        logging.basicConfig(level=default_level)

    # logging carveouts
    logging.getLogger('snowflake.connector').setLevel(logging.WARNING)

if __name__ == '__main__':
    setup_logging()

    # Now you can use logging in your application
    logger = logging.getLogger(__name__)

    logger.info("This is an info message")
    logger.debug("This is a debug message")