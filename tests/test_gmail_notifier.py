"""
Test du module Gmail Notifier
"""

from datetime import datetime
from src.modules.gmail_notifier import (
    GmailNotifier,
    ChangeNotification
)
from src.utils.logger import log_section, setup_logger

logger = setup_logger(__name__)


def test_gmail_notifier():
    """Test complet du GmailNotifier"""
    
    log_section(logger, "Test Gmail Notifier")
    
    # 1. Initialiser le notifier
    logger.info("1️⃣ Initialisation du GmailNotifier")
    notifier = GmailNotifier()
    
    # 2. Créer une notification de test
    logger.info("2️⃣ Création d'une notification de test")
    
    notification = ChangeNotification(
        url="https://www.zalando.fr/accueil-homme/",
        instruction="surveille les prix sur Zalando homme",
        change_score=14.29,
        threshold=1.0,
        added_lines=2,
        removed_lines=1,
        modified_lines=3,
        diff_summary="""Changements détectés:
+ Prix: 129€/mois (nouveau)
- Prix: 99€/mois (ancien)
~ Description mise à jour
~ Image de produit modifiée
+ Nouveau badge "PROMO"
        """,
        timestamp=datetime.now().strftime("%d/%m/%Y à %H:%M:%S"),
        elements_watched=["prix", "promotions", "disponibilité"]
    )
    
    logger.info("✅ Notification créée!")
    logger.info(f"   URL: {notification.url}")
    logger.info(f"   Score: {notification.change_score}%")
    logger.info(f"   Éléments: {', '.join(notification.elements_watched)}")
    
    # 3. Test de génération HTML
    logger.info("3️⃣ Test de génération du template HTML")
    html = notifier._create_html_template(notification)
    logger.info(f"✅ Template HTML généré: {len(html)} caractères")
    
    # 4. Test de génération texte
    logger.info("4️⃣ Test de génération du texte (fallback)")
    text = notifier._create_text_fallback(notification)
    logger.info(f"✅ Texte généré: {len(text)} caractères")
    
    # 5. Test d'envoi (mode simulation sans App Password)
    logger.info("5️⃣ Test d'envoi (mode simulation)")
    logger.warning("⚠️ Mode simulation: Aucun email ne sera réellement envoyé")
    logger.warning("⚠️ Pour envoyer un vrai email, fournissez un App Password Gmail")
    
    success = notifier.send_notification(notification)
    
    if success:
        logger.info("✅ Email préparé avec succès!")
        logger.info("")
        logger.info("📧 Pour envoyer un VRAI email:")
        logger.info("   1. Créer un App Password Gmail:")
        logger.info("      https://myaccount.google.com/apppasswords")
        logger.info("   2. Utiliser:")
        logger.info("      notifier.send_notification(notification, app_password='votre_app_password')")
    else:
        logger.error("❌ Échec de préparation de l'email")
    
    # 6. Afficher un exemple de l'email
    logger.info("")
    log_section(logger, "Aperçu de l'email (texte)")
    print("\n" + text + "\n")
    
    log_section(logger, "Test terminé")
    logger.info("✅ Tous les tests ont été exécutés!")
    logger.info("")
    logger.info("💡 Note: Le module est fonctionnel mais nécessite un App Password")
    logger.info("   pour envoyer des emails réels via Gmail")


if __name__ == "__main__":
    test_gmail_notifier()
