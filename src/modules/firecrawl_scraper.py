"""
Module de scraping avec Firecrawl
Gère l'extraction de contenu de sites web, y compris JavaScript-heavy
"""

import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from firecrawl import FirecrawlApp

from config import settings
from src.utils import setup_logger, normalize_url, is_valid_url


logger = setup_logger(__name__)


@dataclass
class ScrapedContent:
    """Représente le contenu scrapé d'une page"""
    url: str
    markdown: str
    html: str
    metadata: Dict[str, Any]
    timestamp: float
    success: bool
    error: Optional[str] = None


class FirecrawlScraper:
    """
    Scraper utilisant Firecrawl pour extraire le contenu de sites web
    Supporte les sites JavaScript lourds et retourne du contenu propre
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialise le scraper Firecrawl
        
        Args:
            api_key: Clé API Firecrawl (utilise settings si non fourni)
        """
        self.api_key = api_key or settings.FIRECRAWL_API_KEY
        
        if not self.api_key:
            raise ValueError("Firecrawl API key manquante. Configurez FIRECRAWL_API_KEY dans .env")
        
        self.client = FirecrawlApp(api_key=self.api_key)
        logger.info("FirecrawlScraper initialisé")
    
    def scrape(
        self, 
        url: str, 
        retry: bool = True,
        formats: list = None
    ) -> ScrapedContent:
        """
        Scrape une URL et retourne le contenu
        
        Args:
            url: URL à scraper
            retry: Réessayer en cas d'échec
            formats: Liste des formats à extraire (défaut: ['markdown', 'html'])
            
        Returns:
            ScrapedContent avec le contenu extrait
        """
        # Normaliser et valider l'URL
        url = normalize_url(url)
        if not is_valid_url(url):
            logger.error(f"URL invalide: {url}")
            return ScrapedContent(
                url=url,
                markdown="",
                html="",
                metadata={},
                timestamp=time.time(),
                success=False,
                error="URL invalide"
            )
        
        logger.info(f"Scraping de: {url}")
        
        # Formats par défaut
        if formats is None:
            formats = ['markdown', 'html']
        
        # Tenter le scraping avec retry
        max_attempts = settings.MAX_RETRIES if retry else 1
        
        for attempt in range(1, max_attempts + 1):
            try:
                # Appel à l'API Firecrawl (v4.x syntax)
                result = self.client.scrape(
                    url=url,
                    formats=formats,
                    only_main_content=True,  # Ne garder que le contenu principal
                    wait_for=2000,  # Attendre 2s pour le JavaScript
                )
                
                # Extraire le contenu (v4.x retourne un objet Document)
                # Gérer à la fois dict et objet
                if hasattr(result, 'markdown'):
                    markdown_content = result.markdown or ''
                    html_content = result.html or ''
                    metadata = result.metadata if hasattr(result, 'metadata') else {}
                else:
                    markdown_content = result.get('markdown', '')
                    html_content = result.get('html', '')
                    metadata = result.get('metadata', {})
                
                logger.info(f"✓ Scraping réussi: {len(markdown_content)} caractères extraits")
                
                return ScrapedContent(
                    url=url,
                    markdown=markdown_content,
                    html=html_content,
                    metadata=metadata,
                    timestamp=time.time(),
                    success=True
                )
                
            except Exception as e:
                logger.warning(f"Tentative {attempt}/{max_attempts} échouée: {str(e)}")
                
                if attempt < max_attempts:
                    wait_time = settings.RETRY_DELAY * attempt
                    logger.info(f"Nouvelle tentative dans {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"✗ Échec du scraping après {max_attempts} tentatives")
                    return ScrapedContent(
                        url=url,
                        markdown="",
                        html="",
                        metadata={},
                        timestamp=time.time(),
                        success=False,
                        error=str(e)
                    )
    
    def scrape_multiple(self, urls: list) -> list[ScrapedContent]:
        """
        Scrape plusieurs URLs séquentiellement
        
        Args:
            urls: Liste d'URLs à scraper
            
        Returns:
            Liste de ScrapedContent
        """
        logger.info(f"Scraping de {len(urls)} URLs...")
        results = []
        
        for i, url in enumerate(urls, 1):
            logger.info(f"[{i}/{len(urls)}] Processing: {url}")
            result = self.scrape(url)
            results.append(result)
            
            # Pause entre les requêtes pour éviter le rate limiting
            if i < len(urls):
                time.sleep(1)
        
        successful = sum(1 for r in results if r.success)
        logger.info(f"Scraping terminé: {successful}/{len(urls)} réussis")
        
        return results
    
    def get_content_hash(self, content: ScrapedContent) -> str:
        """
        Génère un hash du contenu pour détection rapide de changements
        
        Args:
            content: Contenu scrapé
            
        Returns:
            Hash MD5 du contenu markdown
        """
        import hashlib
        return hashlib.md5(content.markdown.encode()).hexdigest()


# Fonction de commodité pour usage rapide
def scrape_url(url: str) -> ScrapedContent:
    """
    Fonction utilitaire pour scraper une URL rapidement
    
    Args:
        url: URL à scraper
        
    Returns:
        ScrapedContent
    """
    scraper = FirecrawlScraper()
    return scraper.scrape(url)


__all__ = [
    'FirecrawlScraper',
    'ScrapedContent',
    'scrape_url',
]
