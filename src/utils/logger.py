import logging
from typing import Optional

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Create a logger with the given name and level"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:  # Only add handler if none exists
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    if level is not None:
        logger.setLevel(level)
    elif not logger.level:  # Only set default level if none is set
        logger.setLevel(logging.INFO)
    
    return logger