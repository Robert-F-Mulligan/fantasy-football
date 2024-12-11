import logging
import logging.config
import io
import sys
import json

def setup_logging(path=r'config\logger.json', default_level=logging.INFO):
    """Setup logging configuration from a JSON file."""
    try:
        with open(path, 'rt', encoding='utf-8') as f:
            config = json.load(f)

        # Modify StreamHandler to ensure UTF-8 encoding for console output
        for handler in config.get('handlers', {}).values():
            if handler.get('class') == 'logging.StreamHandler':
                handler['stream'] = io.TextIOWrapper(
                    sys.stdout.buffer,
                    encoding='utf-8',
                    errors='replace'  # Replace unencodable characters
                )
        
        logging.config.dictConfig(config)
    except Exception as e:
        print(f"Error in loading logging configuration: {e}")
        logging.basicConfig(level=default_level)

    # Logging carveouts
    logging.getLogger('snowflake.connector').setLevel(logging.WARNING)

if __name__ == '__main__':
    setup_logging()

    # Now you can use logging in your application
    logger = logging.getLogger(__name__)

    logger.info("This is an info message with Unicode: 🌟")
    logger.debug("This is a debug message with a special character: \uf101")
