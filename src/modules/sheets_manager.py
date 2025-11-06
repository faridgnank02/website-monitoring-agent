"""
Module de gestion Google Sheets pour Monitor Agent
Stocke l'historique des scrapings et des comparaisons
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
import json
import os

# Google Sheets API
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configuration
from config.settings import (
    GOOGLE_CREDENTIALS_FILE,
    GOOGLE_SHEET_ID,
    GOOGLE_SHEET_LOG_TAB,
    GOOGLE_SHEET_COMPARISON_TAB,
    BASE_DIR
)

# Logging
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ScrapingLog:
    """Modèle pour un log de scraping"""
    timestamp: str
    url: str
    instruction: str
    status: str  # "success" ou "error"
    content_hash: str
    content_length: int
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_row(self) -> List[Any]:
        """Convertit en ligne pour Google Sheets"""
        return [
            self.timestamp,
            self.url,
            self.instruction,
            self.status,
            self.content_hash,
            str(self.content_length),
            self.error_message or "",
            json.dumps(self.metadata) if self.metadata else ""
        ]


@dataclass
class ComparisonLog:
    """Modèle pour un log de comparaison"""
    timestamp: str
    url: str
    instruction: str
    has_changes: bool
    change_score: float
    added_lines: int
    removed_lines: int
    modified_lines: int
    threshold: float
    diff_summary: str
    old_hash: str
    new_hash: str

    def to_row(self) -> List[Any]:
        """Convertit en ligne pour Google Sheets"""
        return [
            self.timestamp,
            self.url,
            self.instruction,
            "OUI" if self.has_changes else "NON",
            f"{self.change_score:.2f}%",
            str(self.added_lines),
            str(self.removed_lines),
            str(self.modified_lines),
            f"{self.threshold}%",
            self.diff_summary,
            self.old_hash,
            self.new_hash
        ]


class SheetsManager:
    """
    Gestionnaire Google Sheets
    
    Gère deux onglets :
    - Log : Historique des scrapings
    - Comparison : Historique des comparaisons
    """

    # Scopes requis pour Google Sheets
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    # Headers des onglets
    LOG_HEADERS = [
        'Timestamp', 'URL', 'Instruction', 'Status',
        'Content Hash', 'Content Length', 'Error', 'Metadata'
    ]

    COMPARISON_HEADERS = [
        'Timestamp', 'URL', 'Instruction', 'Changements',
        'Score %', 'Lignes Ajoutées', 'Lignes Supprimées',
        'Lignes Modifiées', 'Seuil %', 'Résumé', 'Hash Ancien', 'Hash Nouveau'
    ]

    def __init__(self, credentials_file: Optional[str] = None, sheet_id: Optional[str] = None):
        """
        Initialise le gestionnaire Sheets
        
        Args:
            credentials_file: Chemin vers credentials.json (optionnel)
            sheet_id: ID du Google Sheet (optionnel)
        """
        self.credentials_file = credentials_file or GOOGLE_CREDENTIALS_FILE
        self.sheet_id = sheet_id or GOOGLE_SHEET_ID
        
        # Résoudre le chemin complet
        if not os.path.isabs(self.credentials_file):
            self.credentials_file = str(BASE_DIR / self.credentials_file)
        
        self.service = None
        self.log_tab = GOOGLE_SHEET_LOG_TAB
        self.comparison_tab = GOOGLE_SHEET_COMPARISON_TAB

        logger.info(f"📊 SheetsManager initialisé (Sheet ID: {self.sheet_id[:8]}...)")

    def authenticate(self) -> bool:
        """
        Authentifie avec Google Sheets API
        
        Returns:
            True si succès, False sinon
        """
        try:
            if not os.path.exists(self.credentials_file):
                logger.error(f"❌ Fichier credentials non trouvé: {self.credentials_file}")
                return False

            logger.info(f"🔑 Authentification avec {self.credentials_file}")
            
            creds = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.SCOPES
            )
            
            self.service = build('sheets', 'v4', credentials=creds)
            logger.info("✅ Authentification réussie!")
            
            return True

        except Exception as e:
            logger.error(f"❌ Erreur d'authentification: {e}")
            return False

    def initialize_sheets(self) -> bool:
        """
        Initialise les onglets avec les headers si nécessaire
        
        Returns:
            True si succès, False sinon
        """
        if not self.service:
            if not self.authenticate():
                return False

        try:
            # Vérifier si les onglets existent
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.sheet_id
            ).execute()

            existing_sheets = [sheet['properties']['title'] 
                             for sheet in sheet_metadata.get('sheets', [])]

            logger.info(f"📋 Onglets existants: {existing_sheets}")

            # Créer les onglets si nécessaire
            if self.log_tab not in existing_sheets:
                self._create_sheet(self.log_tab, self.LOG_HEADERS)
            else:
                logger.info(f"✓ Onglet '{self.log_tab}' existe déjà")

            if self.comparison_tab not in existing_sheets:
                self._create_sheet(self.comparison_tab, self.COMPARISON_HEADERS)
            else:
                logger.info(f"✓ Onglet '{self.comparison_tab}' existe déjà")

            return True

        except HttpError as e:
            logger.error(f"❌ Erreur HTTP lors de l'initialisation: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation: {e}")
            return False

    def _create_sheet(self, title: str, headers: List[str]) -> bool:
        """Crée un nouvel onglet avec headers"""
        try:
            # Créer l'onglet
            request_body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': title
                        }
                    }
                }]
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body=request_body
            ).execute()

            logger.info(f"✅ Onglet '{title}' créé")

            # Ajouter les headers
            self._write_row(title, headers, row_number=1)
            
            # Formater les headers (gras)
            self._format_headers(title)

            return True

        except Exception as e:
            logger.error(f"❌ Erreur création onglet '{title}': {e}")
            return False

    def _format_headers(self, sheet_name: str):
        """Formate la ligne de headers (gras, fond gris)"""
        try:
            # Obtenir l'ID de l'onglet
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.sheet_id
            ).execute()

            sheet_id = None
            for sheet in sheet_metadata.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    break

            if sheet_id is None:
                return

            request_body = {
                'requests': [{
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {'bold': True},
                                'backgroundColor': {
                                    'red': 0.9,
                                    'green': 0.9,
                                    'blue': 0.9
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(textFormat,backgroundColor)'
                    }
                }]
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body=request_body
            ).execute()

        except Exception as e:
            logger.warning(f"⚠️ Impossible de formater les headers: {e}")

    def _write_row(self, sheet_name: str, values: List[Any], row_number: Optional[int] = None):
        """
        Écrit une ligne dans un onglet
        
        Args:
            sheet_name: Nom de l'onglet
            values: Valeurs à écrire
            row_number: Numéro de ligne (None = append)
        """
        try:
            if row_number:
                # Écrire à une ligne spécifique
                range_name = f"{sheet_name}!A{row_number}"
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body={'values': [values]}
                ).execute()
            else:
                # Append à la fin
                range_name = f"{sheet_name}!A:A"
                self.service.spreadsheets().values().append(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body={'values': [values]}
                ).execute()

        except Exception as e:
            logger.error(f"❌ Erreur écriture dans '{sheet_name}': {e}")
            raise

    def log_scraping(self, log: ScrapingLog) -> bool:
        """
        Enregistre un log de scraping
        
        Args:
            log: Instance de ScrapingLog
            
        Returns:
            True si succès
        """
        if not self.service:
            if not self.authenticate():
                return False

        try:
            logger.info(f"📝 Enregistrement scraping: {log.url}")
            self._write_row(self.log_tab, log.to_row())
            logger.info("✅ Log de scraping enregistré")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur log scraping: {e}")
            return False

    def log_comparison(self, log: ComparisonLog) -> bool:
        """
        Enregistre un log de comparaison
        
        Args:
            log: Instance de ComparisonLog
            
        Returns:
            True si succès
        """
        if not self.service:
            if not self.authenticate():
                return False

        try:
            logger.info(f"📝 Enregistrement comparaison: {log.url}")
            self._write_row(self.comparison_tab, log.to_row())
            logger.info("✅ Log de comparaison enregistré")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur log comparaison: {e}")
            return False

    def get_last_scraping(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Récupère le dernier scraping réussi pour une URL
        
        Args:
            url: URL à rechercher
            
        Returns:
            Dict avec les données du dernier scraping ou None
        """
        if not self.service:
            if not self.authenticate():
                return None

        try:
            # Lire toutes les lignes du Log
            range_name = f"{self.log_tab}!A2:H"  # Skip header
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()

            rows = result.get('values', [])

            # Chercher la dernière occurrence de l'URL avec status = success
            for row in reversed(rows):
                if len(row) >= 4 and row[1] == url and row[3] == 'success':
                    return {
                        'timestamp': row[0],
                        'url': row[1],
                        'instruction': row[2],
                        'status': row[3],
                        'content_hash': row[4] if len(row) > 4 else '',
                        'content_length': int(row[5]) if len(row) > 5 else 0,
                        'metadata': json.loads(row[7]) if len(row) > 7 and row[7] else {}
                    }

            logger.info(f"ℹ️ Aucun scraping précédent trouvé pour {url}")
            return None

        except Exception as e:
            logger.error(f"❌ Erreur récupération dernier scraping: {e}")
            return None

    def get_scraping_history(self, url: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des scrapings pour une URL
        
        Args:
            url: URL à rechercher
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des scrapings
        """
        if not self.service:
            if not self.authenticate():
                return []

        try:
            range_name = f"{self.log_tab}!A2:H"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()

            rows = result.get('values', [])

            # Filtrer par URL
            history = []
            for row in reversed(rows):
                if len(row) >= 2 and row[1] == url:
                    history.append({
                        'timestamp': row[0],
                        'url': row[1],
                        'instruction': row[2] if len(row) > 2 else '',
                        'status': row[3] if len(row) > 3 else '',
                        'content_hash': row[4] if len(row) > 4 else '',
                        'content_length': int(row[5]) if len(row) > 5 else 0
                    })

                    if len(history) >= limit:
                        break

            logger.info(f"📜 Récupéré {len(history)} scrapings pour {url}")
            return history

        except Exception as e:
            logger.error(f"❌ Erreur récupération historique: {e}")
            return []

    def get_comparison_history(self, url: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des comparaisons pour une URL
        
        Args:
            url: URL à rechercher
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des comparaisons
        """
        if not self.service:
            if not self.authenticate():
                return []

        try:
            range_name = f"{self.comparison_tab}!A2:L"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()

            rows = result.get('values', [])

            # Filtrer par URL
            history = []
            for row in reversed(rows):
                if len(row) >= 2 and row[1] == url:
                    history.append({
                        'timestamp': row[0],
                        'url': row[1],
                        'instruction': row[2] if len(row) > 2 else '',
                        'has_changes': row[3] == 'OUI' if len(row) > 3 else False,
                        'change_score': row[4] if len(row) > 4 else '0%',
                        'diff_summary': row[9] if len(row) > 9 else ''
                    })

                    if len(history) >= limit:
                        break

            logger.info(f"📊 Récupéré {len(history)} comparaisons pour {url}")
            return history

        except Exception as e:
            logger.error(f"❌ Erreur récupération historique comparaisons: {e}")
            return []


# ========================================
# CONVENIENCE FUNCTIONS
# ========================================

def create_sheets_manager(credentials_file: Optional[str] = None, 
                         sheet_id: Optional[str] = None) -> SheetsManager:
    """
    Crée et initialise un SheetsManager
    
    Args:
        credentials_file: Chemin vers credentials.json
        sheet_id: ID du Google Sheet
        
    Returns:
        Instance de SheetsManager
    """
    manager = SheetsManager(credentials_file, sheet_id)
    manager.initialize_sheets()
    return manager


def log_scraping_result(url: str, instruction: str, success: bool, 
                       content_hash: str = "", content_length: int = 0,
                       error_message: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Enregistre rapidement un résultat de scraping
    
    Args:
        url: URL scrapée
        instruction: Instruction originale
        success: True si succès
        content_hash: Hash du contenu
        content_length: Longueur du contenu
        error_message: Message d'erreur éventuel
        metadata: Métadonnées additionnelles
        
    Returns:
        True si enregistré
    """
    manager = SheetsManager()
    
    log = ScrapingLog(
        timestamp=datetime.now().isoformat(),
        url=url,
        instruction=instruction,
        status="success" if success else "error",
        content_hash=content_hash,
        content_length=content_length,
        error_message=error_message,
        metadata=metadata
    )
    
    return manager.log_scraping(log)


def log_comparison_result(url: str, instruction: str, 
                         has_changes: bool, change_score: float,
                         added: int, removed: int, modified: int,
                         threshold: float, diff_summary: str,
                         old_hash: str, new_hash: str) -> bool:
    """
    Enregistre rapidement un résultat de comparaison
    
    Returns:
        True si enregistré
    """
    manager = SheetsManager()
    
    log = ComparisonLog(
        timestamp=datetime.now().isoformat(),
        url=url,
        instruction=instruction,
        has_changes=has_changes,
        change_score=change_score,
        added_lines=added,
        removed_lines=removed,
        modified_lines=modified,
        threshold=threshold,
        diff_summary=diff_summary,
        old_hash=old_hash,
        new_hash=new_hash
    )
    
    return manager.log_comparison(log)


# ========================================
# EXPORT
# ========================================

__all__ = [
    'SheetsManager',
    'ScrapingLog',
    'ComparisonLog',
    'create_sheets_manager',
    'log_scraping_result',
    'log_comparison_result'
]
