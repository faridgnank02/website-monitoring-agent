"""
Module de comparaison de contenu
Détecte les changements entre deux versions d'une page web
"""

import difflib
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import hashlib

from src.utils import setup_logger


logger = setup_logger(__name__)


@dataclass
class ComparisonResult:
    """Résultat de la comparaison de deux contenus"""
    has_changes: bool
    change_score: float  # Pourcentage de changement
    added_lines: List[str]
    removed_lines: List[str]
    modified_lines: List[Tuple[str, str]]  # (ancienne, nouvelle)
    diff_summary: str
    total_lines_old: int
    total_lines_new: int
    hash_old: str
    hash_new: str


class ContentComparator:
    """
    Compare deux versions de contenu et détecte les changements significatifs
    Filtre les éléments dynamiques pour éviter les faux positifs
    """
    
    # Patterns d'éléments dynamiques à ignorer
    DYNAMIC_PATTERNS = [
        r'\d{4}-\d{2}-\d{2}',  # Dates YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',  # Dates DD/MM/YYYY
        r'\d{1,2}:\d{2}:\d{2}',  # Heures HH:MM:SS
        r'Updated:.*',  # Lignes "Updated: ..."
        r'Last modified:.*',  # Lignes "Last modified: ..."
        r'Session ID:.*',  # Session IDs
        r'Cookie:.*',  # Cookies
        r'\d+ visitors? online',  # Compteurs de visiteurs
        r'Copyright © \d{4}',  # Copyright avec année
        r'Generated on.*',  # "Generated on ..."
    ]
    
    def __init__(self, 
                 threshold: float = 1.0,
                 ignore_whitespace: bool = True,
                 ignore_case: bool = False):
        """
        Initialise le comparateur
        
        Args:
            threshold: Seuil de changement en % (1.0 = 1%)
            ignore_whitespace: Ignorer les changements d'espaces
            ignore_case: Ignorer la casse
        """
        self.threshold = threshold
        self.ignore_whitespace = ignore_whitespace
        self.ignore_case = ignore_case
        logger.info(f"ContentComparator initialisé (seuil: {threshold}%)")
    
    def compare(self, 
                content_old: str, 
                content_new: str,
                filter_dynamic: bool = True) -> ComparisonResult:
        """
        Compare deux contenus et retourne les différences
        
        Args:
            content_old: Contenu précédent
            content_new: Contenu actuel
            filter_dynamic: Filtrer les éléments dynamiques
            
        Returns:
            ComparisonResult avec les détails des changements
        """
        logger.info("Comparaison de contenu...")
        
        # Calculer les hashs
        hash_old = self._hash(content_old)
        hash_new = self._hash(content_new)
        
        # Quick check: si les hashs sont identiques, pas de changement
        if hash_old == hash_new:
            logger.info("✓ Aucun changement détecté (hashs identiques)")
            return ComparisonResult(
                has_changes=False,
                change_score=0.0,
                added_lines=[],
                removed_lines=[],
                modified_lines=[],
                diff_summary="Aucun changement",
                total_lines_old=len(content_old.splitlines()),
                total_lines_new=len(content_new.splitlines()),
                hash_old=hash_old,
                hash_new=hash_new
            )
        
        # Normaliser les contenus
        lines_old = self._normalize_content(content_old)
        lines_new = self._normalize_content(content_new)
        
        # Filtrer les éléments dynamiques si demandé
        if filter_dynamic:
            lines_old = self._filter_dynamic_content(lines_old)
            lines_new = self._filter_dynamic_content(lines_new)
        
        # Calculer le diff
        diff = list(difflib.unified_diff(
            lines_old, 
            lines_new,
            lineterm='',
            n=0  # Pas de contexte
        ))
        
        # Analyser le diff
        added = []
        removed = []
        modified = []
        
        i = 0
        while i < len(diff):
            line = diff[i]
            
            if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                i += 1
                continue
            
            if line.startswith('-'):
                removed.append(line[1:].strip())
            elif line.startswith('+'):
                added.append(line[1:].strip())
            
            i += 1
        
        # Détecter les modifications (lignes supprimées puis ajoutées)
        for rem in removed[:]:
            for add in added[:]:
                if self._are_similar(rem, add):
                    modified.append((rem, add))
                    removed.remove(rem)
                    added.remove(add)
                    break
        
        # Calculer le score de changement
        total_changes = len(added) + len(removed) + len(modified)
        total_lines = max(len(lines_old), len(lines_new), 1)
        change_score = (total_changes / total_lines) * 100
        
        # Générer le résumé
        diff_summary = self._generate_summary(added, removed, modified, change_score)
        
        has_changes = change_score > self.threshold
        
        if has_changes:
            logger.info(f"⚠ Changements détectés: {change_score:.2f}% (seuil: {self.threshold}%)")
        else:
            logger.info(f"✓ Changements mineurs: {change_score:.2f}% (< seuil: {self.threshold}%)")
        
        return ComparisonResult(
            has_changes=has_changes,
            change_score=change_score,
            added_lines=added,
            removed_lines=removed,
            modified_lines=modified,
            diff_summary=diff_summary,
            total_lines_old=len(lines_old),
            total_lines_new=len(lines_new),
            hash_old=hash_old,
            hash_new=hash_new
        )
    
    def _normalize_content(self, content: str) -> List[str]:
        """
        Normalise le contenu pour la comparaison
        
        Args:
            content: Contenu à normaliser
            
        Returns:
            Liste de lignes normalisées
        """
        lines = content.splitlines()
        
        if self.ignore_case:
            lines = [line.lower() for line in lines]
        
        if self.ignore_whitespace:
            lines = [' '.join(line.split()) for line in lines]
        
        # Retirer les lignes vides
        lines = [line for line in lines if line.strip()]
        
        return lines
    
    def _filter_dynamic_content(self, lines: List[str]) -> List[str]:
        """
        Filtre les lignes contenant des éléments dynamiques
        
        Args:
            lines: Lignes à filtrer
            
        Returns:
            Lignes filtrées
        """
        filtered = []
        
        for line in lines:
            is_dynamic = False
            
            for pattern in self.DYNAMIC_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    is_dynamic = True
                    break
            
            if not is_dynamic:
                filtered.append(line)
        
        return filtered
    
    def _are_similar(self, str1: str, str2: str, threshold: float = 0.7) -> bool:
        """
        Vérifie si deux chaînes sont similaires
        
        Args:
            str1: Première chaîne
            str2: Deuxième chaîne
            threshold: Seuil de similarité (0-1)
            
        Returns:
            True si les chaînes sont similaires
        """
        ratio = difflib.SequenceMatcher(None, str1, str2).ratio()
        return ratio >= threshold
    
    def _generate_summary(self,
                         added: List[str],
                         removed: List[str],
                         modified: List[Tuple[str, str]],
                         score: float) -> str:
        """
        Génère un résumé lisible des changements
        
        Args:
            added: Lignes ajoutées
            removed: Lignes supprimées
            modified: Lignes modifiées
            score: Score de changement
            
        Returns:
            Résumé formaté
        """
        summary_parts = []
        
        summary_parts.append(f"Score de changement: {score:.2f}%")
        
        if added:
            summary_parts.append(f"\n✚ {len(added)} ligne(s) ajoutée(s):")
            for line in added[:5]:  # Limiter à 5 exemples
                summary_parts.append(f"  + {line[:100]}")
            if len(added) > 5:
                summary_parts.append(f"  ... et {len(added) - 5} autres")
        
        if removed:
            summary_parts.append(f"\n✖ {len(removed)} ligne(s) supprimée(s):")
            for line in removed[:5]:
                summary_parts.append(f"  - {line[:100]}")
            if len(removed) > 5:
                summary_parts.append(f"  ... et {len(removed) - 5} autres")
        
        if modified:
            summary_parts.append(f"\n✎ {len(modified)} ligne(s) modifiée(s):")
            for old, new in modified[:3]:
                summary_parts.append(f"  • {old[:80]} → {new[:80]}")
            if len(modified) > 3:
                summary_parts.append(f"  ... et {len(modified) - 3} autres")
        
        return "\n".join(summary_parts)
    
    def _hash(self, content: str) -> str:
        """
        Génère un hash MD5 du contenu
        
        Args:
            content: Contenu à hasher
            
        Returns:
            Hash MD5
        """
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_detailed_diff(self, content_old: str, content_new: str) -> str:
        """
        Retourne un diff détaillé au format unified diff
        
        Args:
            content_old: Contenu ancien
            content_new: Contenu nouveau
            
        Returns:
            Diff formaté
        """
        lines_old = content_old.splitlines(keepends=True)
        lines_new = content_new.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            lines_old,
            lines_new,
            fromfile='ancien',
            tofile='nouveau'
        )
        
        return ''.join(diff)


# Fonction de commodité
def compare_content(content_old: str, 
                   content_new: str,
                   threshold: float = 1.0) -> ComparisonResult:
    """
    Fonction utilitaire pour comparer deux contenus rapidement
    
    Args:
        content_old: Ancien contenu
        content_new: Nouveau contenu
        threshold: Seuil de changement en %
        
    Returns:
        ComparisonResult
    """
    comparator = ContentComparator(threshold=threshold)
    return comparator.compare(content_old, content_new)


__all__ = [
    'ContentComparator',
    'ComparisonResult',
    'compare_content',
]
