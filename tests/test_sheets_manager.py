"""
Test du module Sheets Manager
"""

from datetime import datetime
from src.modules.sheets_manager import (
    SheetsManager,
    ScrapingLog,
    ComparisonLog
)
from src.utils.logger import log_section, setup_logger

logger = setup_logger(__name__)


def test_sheets_manager():
    """Test complet du SheetsManager"""
    
    log_section(logger, "Test Sheets Manager")
    
    # 1. Initialiser le manager
    logger.info("1️⃣ Initialisation du SheetsManager")
    manager = SheetsManager()
    
    # 2. Authentification
    logger.info("2️⃣ Authentification avec Google Sheets API")
    if not manager.authenticate():
        logger.error("❌ Échec de l'authentification")
        logger.warning("⚠️ Vérifiez que credentials.json existe et est valide")
        logger.warning("⚠️ Vérifiez que GOOGLE_SHEET_ID est défini dans .env")
        return
    
    logger.info("✅ Authentification réussie!")
    
    # 3. Initialiser les onglets
    logger.info("3️⃣ Initialisation des onglets (Log et Comparison)")
    if not manager.initialize_sheets():
        logger.error("❌ Échec de l'initialisation des onglets")
        return
    
    logger.info("✅ Onglets initialisés!")
    
    # 4. Test log scraping
    logger.info("4️⃣ Test d'enregistrement d'un scraping")
    
    scraping_log = ScrapingLog(
        timestamp=datetime.now().isoformat(),
        url="https://www.zalando.fr/accueil-homme/",
        instruction="surveille les prix sur Zalando homme",
        status="success",
        content_hash="2f53f309ba1d1bdccca02d0d2cf85d20",
        content_length=112003,
        metadata={"source": "test", "user": "test_user"}
    )
    
    if manager.log_scraping(scraping_log):
        logger.info("✅ Log de scraping enregistré!")
    else:
        logger.error("❌ Échec enregistrement scraping")
    
    # 5. Test log comparison
    logger.info("5️⃣ Test d'enregistrement d'une comparaison")
    
    comparison_log = ComparisonLog(
        timestamp=datetime.now().isoformat(),
        url="https://www.zalando.fr/accueil-homme/",
        instruction="surveille les prix sur Zalando homme",
        has_changes=True,
        change_score=14.29,
        added_lines=2,
        removed_lines=1,
        modified_lines=3,
        threshold=1.0,
        diff_summary="Prix modifié: 99€ → 129€",
        old_hash="abc123",
        new_hash="def456"
    )
    
    if manager.log_comparison(comparison_log):
        logger.info("✅ Log de comparaison enregistré!")
    else:
        logger.error("❌ Échec enregistrement comparaison")
    
    # 6. Test récupération dernier scraping
    logger.info("6️⃣ Test récupération du dernier scraping")
    
    last_scraping = manager.get_last_scraping("https://www.zalando.fr/accueil-homme/")
    if last_scraping:
        logger.info(f"✅ Dernier scraping récupéré!")
        logger.info(f"   - Timestamp: {last_scraping['timestamp']}")
        logger.info(f"   - Hash: {last_scraping['content_hash']}")
        logger.info(f"   - Taille: {last_scraping['content_length']} caractères")
    else:
        logger.warning("⚠️ Aucun scraping précédent trouvé")
    
    # 7. Test récupération historique
    logger.info("7️⃣ Test récupération de l'historique")
    
    history = manager.get_scraping_history("https://www.zalando.fr/accueil-homme/", limit=5)
    logger.info(f"📜 Historique: {len(history)} scrapings trouvés")
    
    for i, entry in enumerate(history, 1):
        logger.info(f"   {i}. {entry['timestamp']} - {entry['status']}")
    
    # 8. Test récupération historique comparaisons
    logger.info("8️⃣ Test récupération historique des comparaisons")
    
    comp_history = manager.get_comparison_history("https://www.zalando.fr/accueil-homme/", limit=5)
    logger.info(f"📊 Historique comparaisons: {len(comp_history)} entrées")
    
    for i, entry in enumerate(comp_history, 1):
        changes = "✓ Changements" if entry['has_changes'] else "✗ Aucun changement"
        logger.info(f"   {i}. {entry['timestamp']} - {changes} ({entry['change_score']})")
    
    log_section(logger, "Test terminé")
    logger.info("✅ Tous les tests ont été exécutés!")
    logger.info(f"📊 Consultez votre Google Sheet pour voir les données")


if __name__ == "__main__":
    test_sheets_manager()
