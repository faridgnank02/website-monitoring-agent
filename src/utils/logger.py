"""
Logger personnalisé avec couleurs et formatage
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
import colorlog

from config import settings


def setup_logger(name: str = "monitor_agent", level: str = None) -> logging.Logger:
    """
    Configure et retourne un logger avec formatage coloré
    
    Args:
        name: Nom du logger
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR). Si None, utilise settings.LOG_LEVEL
        
    Returns:
        Logger configuré
    """
    # Utiliser le niveau de config par défaut si non spécifié
    if level is None:
        level = settings.LOG_LEVEL
    
    # Créer le logger
    logger = colorlog.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Éviter les doublons de handlers
    if logger.handlers:
        return logger
    
    # Format pour console (avec couleurs)
    console_format = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s | %(levelname)-8s | %(name)s | %(message)s%(reset)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    # Handler console
    console_handler = colorlog.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # Format pour fichier (sans couleurs)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Handler fichier (log quotidien)
    log_file = settings.LOGS_DIR / f"monitor_agent_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    return logger


def log_separator(logger: logging.Logger, char: str = "=", length: int = 80):
    """Affiche une ligne de séparation dans les logs"""
    logger.info(char * length)


def log_section(logger: logging.Logger, title: str, char: str = "=", length: int = 80):
    """Affiche un titre de section dans les logs"""
    padding = (length - len(title) - 2) // 2
    logger.info(f"{char * padding} {title} {char * padding}")


# Logger par défaut pour l'application
default_logger = setup_logger()


# Fonctions de commodité
def debug(msg: str, **kwargs):
    """Log un message de debug"""
    default_logger.debug(msg, **kwargs)


def info(msg: str, **kwargs):
    """Log un message d'info"""
    default_logger.info(msg, **kwargs)


def warning(msg: str, **kwargs):
    """Log un avertissement"""
    default_logger.warning(msg, **kwargs)


def error(msg: str, **kwargs):
    """Log une erreur"""
    default_logger.error(msg, **kwargs)


def critical(msg: str, **kwargs):
    """Log une erreur critique"""
    default_logger.critical(msg, **kwargs)


__all__ = [
    'setup_logger',
    'log_separator',
    'log_section',
    'default_logger',
    'debug',
    'info',
    'warning',
    'error',
    'critical',
]
