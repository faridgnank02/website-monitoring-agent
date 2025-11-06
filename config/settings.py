"""
Configuration centralisée pour Monitor Agent
Charge toutes les variables d'environnement et expose les settings
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Déterminer le chemin racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent

# Charger les variables d'environnement
env_path = BASE_DIR / 'config' / '.env'
if not env_path.exists():
    env_path = BASE_DIR / '.env'
    
load_dotenv(dotenv_path=env_path)

# ========================================
# GROQ API SETTINGS
# ========================================
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'mixtral-8x7b-32768')

# ========================================
# FIRECRAWL API SETTINGS
# ========================================
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY', '')

# ========================================
# GOOGLE APIS SETTINGS
# ========================================
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID', '')
GOOGLE_SHEET_LOG_TAB = os.getenv('GOOGLE_SHEET_LOG_TAB', 'Log')
GOOGLE_SHEET_COMPARISON_TAB = os.getenv('GOOGLE_SHEET_COMPARISON_TAB', 'Comparison')

# Gmail
GMAIL_SENDER_EMAIL = os.getenv('GMAIL_SENDER_EMAIL', '')
GMAIL_RECIPIENT_EMAIL = os.getenv('GMAIL_RECIPIENT_EMAIL', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')

# ========================================
# APPLICATION SETTINGS
# ========================================
ENV = os.getenv('ENV', 'development')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
DEFAULT_CHANGE_THRESHOLD = float(os.getenv('DEFAULT_CHANGE_THRESHOLD', '1.0'))

# Retry settings
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))

# ========================================
# SCHEDULING SETTINGS
# ========================================
DEFAULT_SCHEDULE = os.getenv('DEFAULT_SCHEDULE', 'daily 10:00')
TIMEZONE = os.getenv('TIMEZONE', 'UTC')

# ========================================
# n8n SETTINGS
# ========================================
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'http://localhost:5678/webhook/monitor')
N8N_API_KEY = os.getenv('N8N_API_KEY', '')

# ========================================
# PATHS
# ========================================
CONFIG_DIR = BASE_DIR / 'config'
DATA_DIR = BASE_DIR / 'data'
LOGS_DIR = DATA_DIR / 'logs'
SITES_CONFIG_FILE = CONFIG_DIR / 'sites.yaml'

# Créer les dossiers s'ils n'existent pas
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ========================================
# VALIDATION
# ========================================
def validate_config():
    """Valide que les configurations critiques sont présentes"""
    errors = []
    
    if not GROQ_API_KEY:
        errors.append("GROQ_API_KEY n'est pas définie")
    
    if not FIRECRAWL_API_KEY:
        errors.append("FIRECRAWL_API_KEY n'est pas définie")
    
    if not GOOGLE_SHEET_ID:
        errors.append("GOOGLE_SHEET_ID n'est pas définie")
    
    if not GMAIL_SENDER_EMAIL or not GMAIL_RECIPIENT_EMAIL:
        errors.append("GMAIL_SENDER_EMAIL et GMAIL_RECIPIENT_EMAIL doivent être définis")
    
    if errors:
        error_msg = "\n".join([f"  - {error}" for error in errors])
        raise ValueError(
            f"Configuration invalide :\n{error_msg}\n"
            f"Assurez-vous d'avoir créé un fichier .env basé sur .env.example"
        )
    
    return True

# ========================================
# EXPORT
# ========================================
__all__ = [
    'GROQ_API_KEY',
    'GROQ_MODEL',
    'FIRECRAWL_API_KEY',
    'GOOGLE_CREDENTIALS_FILE',
    'GOOGLE_SHEET_ID',
    'GOOGLE_SHEET_LOG_TAB',
    'GOOGLE_SHEET_COMPARISON_TAB',
    'GMAIL_SENDER_EMAIL',
    'GMAIL_RECIPIENT_EMAIL',
    'GMAIL_APP_PASSWORD',
    'ENV',
    'LOG_LEVEL',
    'DEFAULT_CHANGE_THRESHOLD',
    'MAX_RETRIES',
    'RETRY_DELAY',
    'DEFAULT_SCHEDULE',
    'TIMEZONE',
    'N8N_WEBHOOK_URL',
    'N8N_API_KEY',
    'BASE_DIR',
    'CONFIG_DIR',
    'DATA_DIR',
    'LOGS_DIR',
    'SITES_CONFIG_FILE',
    'validate_config',
]
