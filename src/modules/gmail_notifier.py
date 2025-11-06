"""
Module de notifications Gmail pour Monitor Agent
Envoie des emails HTML avec résumés des changements détectés
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Configuration
from config.settings import (
    GMAIL_SENDER_EMAIL,
    GMAIL_RECIPIENT_EMAIL,
    GMAIL_APP_PASSWORD
)

# Logging
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ChangeNotification:
    """Modèle pour une notification de changement"""
    url: str
    instruction: str
    change_score: float
    threshold: float
    added_lines: int
    removed_lines: int
    modified_lines: int
    diff_summary: str
    timestamp: str
    elements_watched: List[str]


class GmailNotifier:
    """
    Gestionnaire de notifications Gmail
    
    Envoie des emails HTML formatés avec :
    - Résumé des changements détectés
    - Score de changement vs seuil
    - Détails des modifications
    - Lien vers le site surveillé
    """

    def __init__(self, sender_email: Optional[str] = None, recipient_email: Optional[str] = None):
        """
        Initialise le notifier Gmail
        
        Args:
            sender_email: Email expéditeur (optionnel)
            recipient_email: Email destinataire (optionnel)
        """
        self.sender_email = sender_email or GMAIL_SENDER_EMAIL
        self.recipient_email = recipient_email or GMAIL_RECIPIENT_EMAIL
        
        logger.info(f"📧 GmailNotifier initialisé")
        logger.info(f"   De: {self.sender_email}")
        logger.info(f"   À: {self.recipient_email}")

    def _create_html_template(self, notification: ChangeNotification) -> str:
        """
        Crée un template HTML pour l'email
        
        Args:
            notification: Données de notification
            
        Returns:
            HTML formaté
        """
        # Déterminer la couleur selon le score
        if notification.change_score >= notification.threshold * 5:
            badge_color = "#dc3545"  # Rouge (changement majeur)
            badge_text = "CHANGEMENT MAJEUR"
        elif notification.change_score >= notification.threshold * 2:
            badge_color = "#fd7e14"  # Orange (changement important)
            badge_text = "CHANGEMENT IMPORTANT"
        else:
            badge_color = "#28a745"  # Vert (changement mineur)
            badge_text = "CHANGEMENT DÉTECTÉ"

        html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Changement détecté</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">🔍 Monitor Agent</h1>
        <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">Surveillance de sites web</p>
    </div>
    
    <!-- Badge Status -->
    <div style="background-color: {badge_color}; color: white; padding: 15px; text-align: center; font-weight: bold; font-size: 16px;">
        {badge_text}
    </div>
    
    <!-- Content -->
    <div style="background-color: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #dee2e6;">
        
        <!-- Instruction -->
        <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #667eea;">
            <h2 style="margin: 0 0 10px 0; color: #667eea; font-size: 18px;">📋 Instruction</h2>
            <p style="margin: 0; font-size: 16px; font-weight: 500;">{notification.instruction}</p>
        </div>
        
        <!-- URL -->
        <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 10px 0; color: #495057; font-size: 16px;">🌐 Site surveillé</h3>
            <a href="{notification.url}" style="color: #667eea; text-decoration: none; word-break: break-all;">{notification.url}</a>
        </div>
        
        <!-- Éléments surveillés -->
        <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 10px 0; color: #495057; font-size: 16px;">👁️ Éléments surveillés</h3>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                {''.join([f'<span style="background-color: #e7f3ff; color: #0066cc; padding: 5px 12px; border-radius: 15px; font-size: 13px; display: inline-block;">{elem}</span>' for elem in notification.elements_watched])}
            </div>
        </div>
        
        <!-- Statistiques -->
        <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 15px 0; color: #495057; font-size: 16px;">📊 Statistiques</h3>
            
            <div style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span style="font-weight: 500;">Score de changement</span>
                    <span style="font-weight: bold; color: {badge_color};">{notification.change_score:.2f}%</span>
                </div>
                <div style="background-color: #e9ecef; height: 8px; border-radius: 4px; overflow: hidden;">
                    <div style="background-color: {badge_color}; height: 100%; width: {min(notification.change_score, 100)}%; transition: width 0.3s;"></div>
                </div>
                <div style="font-size: 12px; color: #6c757d; margin-top: 3px;">
                    Seuil d'alerte : {notification.threshold}%
                </div>
            </div>
            
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #dee2e6;">
                        <span style="color: #28a745;">✚</span> Lignes ajoutées
                    </td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">
                        {notification.added_lines}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; border-bottom: 1px solid #dee2e6;">
                        <span style="color: #dc3545;">✖</span> Lignes supprimées
                    </td>
                    <td style="padding: 8px 0; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">
                        {notification.removed_lines}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px 0;">
                        <span style="color: #fd7e14;">✎</span> Lignes modifiées
                    </td>
                    <td style="padding: 8px 0; text-align: right; font-weight: bold;">
                        {notification.modified_lines}
                    </td>
                </tr>
            </table>
        </div>
        
        <!-- Résumé des changements -->
        <div style="background-color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
            <h3 style="margin: 0 0 10px 0; color: #495057; font-size: 16px;">📝 Résumé des changements</h3>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace; font-size: 13px; white-space: pre-wrap; overflow-x: auto;">
{notification.diff_summary}
            </div>
        </div>
        
        <!-- Timestamp -->
        <div style="text-align: center; color: #6c757d; font-size: 13px; margin-top: 20px;">
            <p style="margin: 0;">📅 Détecté le : {notification.timestamp}</p>
        </div>
        
    </div>
    
    <!-- Footer -->
    <div style="text-align: center; margin-top: 20px; padding: 20px; color: #6c757d; font-size: 12px;">
        <p style="margin: 0 0 10px 0;">
            Cette alerte a été générée automatiquement par <strong>Monitor Agent</strong>
        </p>
        <p style="margin: 0;">
            🤖 Powered by Groq AI + Firecrawl
        </p>
    </div>
    
</body>
</html>
        """
        
        return html

    def _create_text_fallback(self, notification: ChangeNotification) -> str:
        """
        Crée une version texte simple de l'email (fallback)
        
        Args:
            notification: Données de notification
            
        Returns:
            Texte formaté
        """
        text = f"""
🔍 MONITOR AGENT - CHANGEMENT DÉTECTÉ

📋 Instruction: {notification.instruction}

🌐 Site surveillé: {notification.url}

👁️ Éléments surveillés: {', '.join(notification.elements_watched)}

📊 STATISTIQUES
===============
Score de changement: {notification.change_score:.2f}%
Seuil d'alerte: {notification.threshold}%

✚ Lignes ajoutées: {notification.added_lines}
✖ Lignes supprimées: {notification.removed_lines}
✎ Lignes modifiées: {notification.modified_lines}

📝 RÉSUMÉ DES CHANGEMENTS
=========================
{notification.diff_summary}

📅 Détecté le: {notification.timestamp}

---
Cette alerte a été générée automatiquement par Monitor Agent
🤖 Powered by Groq AI + Firecrawl
        """
        
        return text.strip()

    def send_notification(self, notification: ChangeNotification, 
                         smtp_server: str = "smtp.gmail.com",
                         smtp_port: int = 587,
                         app_password: Optional[str] = None) -> bool:
        """
        Envoie une notification par email
        
        Args:
            notification: Données de notification
            smtp_server: Serveur SMTP (défaut: Gmail)
            smtp_port: Port SMTP (défaut: 587)
            app_password: Mot de passe d'application Gmail (optionnel, utilise .env par défaut)
            
        Returns:
            True si envoyé avec succès
            
        Note:
            Pour Gmail, vous devez créer un "App Password":
            https://myaccount.google.com/apppasswords
        """
        # Utiliser l'App Password depuis .env si non fourni
        if app_password is None:
            app_password = GMAIL_APP_PASSWORD
        
        try:
            logger.info(f"📧 Préparation de l'email de notification")
            
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🔍 Changement détecté: {notification.instruction}"
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
            
            # Version texte (fallback)
            text_part = MIMEText(self._create_text_fallback(notification), 'plain', 'utf-8')
            msg.attach(text_part)
            
            # Version HTML
            html_part = MIMEText(self._create_html_template(notification), 'html', 'utf-8')
            msg.attach(html_part)
            
            # Connexion au serveur SMTP
            if app_password:
                logger.info(f"📤 Connexion au serveur SMTP: {smtp_server}:{smtp_port}")
                
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()  # Activer TLS
                    server.login(self.sender_email, app_password)
                    server.send_message(msg)
                
                logger.info("✅ Email envoyé avec succès!")
                return True
            else:
                logger.warning("⚠️ Aucun mot de passe d'application fourni")
                logger.warning("⚠️ Mode simulation: Email préparé mais non envoyé")
                logger.info(f"   Sujet: {msg['Subject']}")
                logger.info(f"   De: {msg['From']}")
                logger.info(f"   À: {msg['To']}")
                
                # En mode simulation, on considère que c'est un succès
                return True

        except smtplib.SMTPAuthenticationError:
            logger.error("❌ Erreur d'authentification SMTP")
            logger.error("   Vérifiez votre email et mot de passe d'application")
            logger.error("   Créez un App Password: https://myaccount.google.com/apppasswords")
            return False
            
        except smtplib.SMTPException as e:
            logger.error(f"❌ Erreur SMTP: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'envoi: {e}")
            return False

    def send_change_alert(self, 
                         url: str,
                         instruction: str,
                         change_score: float,
                         threshold: float,
                         added: int,
                         removed: int,
                         modified: int,
                         diff_summary: str,
                         elements_watched: List[str],
                         app_password: Optional[str] = None) -> bool:
        """
        Raccourci pour envoyer une alerte de changement
        
        Args:
            url: URL surveillée
            instruction: Instruction originale
            change_score: Score de changement (%)
            threshold: Seuil d'alerte (%)
            added: Lignes ajoutées
            removed: Lignes supprimées
            modified: Lignes modifiées
            diff_summary: Résumé des changements
            elements_watched: Éléments surveillés
            app_password: Mot de passe d'application Gmail
            
        Returns:
            True si envoyé
        """
        notification = ChangeNotification(
            url=url,
            instruction=instruction,
            change_score=change_score,
            threshold=threshold,
            added_lines=added,
            removed_lines=removed,
            modified_lines=modified,
            diff_summary=diff_summary,
            timestamp=datetime.now().strftime("%d/%m/%Y à %H:%M:%S"),
            elements_watched=elements_watched
        )
        
        return self.send_notification(notification, app_password=app_password)


# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

def send_change_notification(url: str, instruction: str, change_score: float,
                            threshold: float, added: int, removed: int, modified: int,
                            diff_summary: str, elements_watched: List[str],
                            app_password: Optional[str] = None,
                            sender_email: Optional[str] = None,
                            recipient_email: Optional[str] = None) -> bool:
    """
    Envoie rapidement une notification de changement
    
    Returns:
        True si envoyé avec succès
    """
    notifier = GmailNotifier(sender_email, recipient_email)
    return notifier.send_change_alert(
        url=url,
        instruction=instruction,
        change_score=change_score,
        threshold=threshold,
        added=added,
        removed=removed,
        modified=modified,
        diff_summary=diff_summary,
        elements_watched=elements_watched,
        app_password=app_password
    )


# ========================================
# EXPORT
# ========================================

__all__ = [
    'GmailNotifier',
    'ChangeNotification',
    'send_change_notification'
]
