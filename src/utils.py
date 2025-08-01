from datetime import datetime
import logging
import os

def create_logger(name: str, log_dir: str = "logs") -> logging.Logger:
    """
    Creates a logger.

    Args:
        name (str): the name of the logger, appended to the end of the filename
        timestamp (datetime): placed at the head of the filename
        log_dir (str): directory of the log
    """

    timestamp = datetime.now()

    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"{timestamp.strftime('%Y-%m-%d %H%M%S')} {name}.txt")
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:  # Avoid duplicate handlers on reload
        file_handler = logging.FileHandler(log_filename)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger