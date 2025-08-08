from datetime import datetime
from multiprocessing import Lock
import logging
import os
import csv

class CSVLogger():
    def __init__(self, name="log", log_dir="logs", headers=None):
        self.lock = Lock()
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now()
        self.filepath = os.path.join(log_dir, f"{timestamp.strftime('%Y%m%d%H%M%S')} {name}.csv")
        self.headers = headers

        with self.lock:
            if not os.path.exists(self.filepath):
                with open(self.filepath, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self.headers)
                    writer.writeheader()

    def log(self, data: dict):
        with self.lock:
            with open(self.filepath, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.headers)
                writer.writerow(data)

def create_logger(name: str, log_dir: str = "logs", metadata=False) -> logging.Logger:
    """
    Creates a logger.

    Args:
        name (str): the name of the logger, appended to the end of the filename
        timestamp (datetime): placed at the head of the filename
        log_dir (str): directory of the log
    """

    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now()
    log_filename = os.path.join(log_dir, f"{timestamp.strftime('%Y%m%d%H%M%S')} chat.txt")
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:  # Avoid duplicate handlers on reload
        file_handler = logging.FileHandler(log_filename)
        if metadata:
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        else:
            formatter = logging.Formatter('%(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
