"""
Utilitaires pour la validation des données
"""

import re
from typing import Optional
from urllib.parse import urlparse


def is_valid_url(url: str) -> bool:
    """
    Valide qu'une chaîne est une URL valide
    
    Args:
        url: URL à valider
        
    Returns:
        True si l'URL est valide, False sinon
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """
    Normalise une URL (ajoute http:// si nécessaire, retire trailing slash)
    
    Args:
        url: URL à normaliser
        
    Returns:
        URL normalisée
    """
    url = url.strip()
    
    # Ajouter http:// si pas de schéma
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Retirer le trailing slash
    url = url.rstrip('/')
    
    return url


def is_valid_email(email: str) -> bool:
    """
    Valide qu'une chaîne est une adresse email valide
    
    Args:
        email: Email à valider
        
    Returns:
        True si l'email est valide, False sinon
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_threshold(threshold: float) -> bool:
    """
    Valide qu'un seuil est dans une plage acceptable (0-100%)
    
    Args:
        threshold: Seuil à valider (en %)
        
    Returns:
        True si le seuil est valide, False sinon
    """
    return 0 <= threshold <= 100


def sanitize_filename(filename: str) -> str:
    """
    Nettoie un nom de fichier pour le rendre sûr
    
    Args:
        filename: Nom de fichier à nettoyer
        
    Returns:
        Nom de fichier nettoyé
    """
    # Remplacer les caractères dangereux
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limiter la longueur
    filename = filename[:200]
    return filename


def extract_domain(url: str) -> Optional[str]:
    """
    Extrait le domaine d'une URL
    
    Args:
        url: URL dont extraire le domaine
        
    Returns:
        Domaine ou None si invalide
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return None


__all__ = [
    'is_valid_url',
    'normalize_url',
    'is_valid_email',
    'validate_threshold',
    'sanitize_filename',
    'extract_domain',
]
