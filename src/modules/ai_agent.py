"""
Module AI Agent avec CrewAI et Groq
Parse les instructions en langage naturel et extrait les informations nécessaires
"""

from typing import Dict, Optional, List
from dataclasses import dataclass
import json
from groq import Groq

from config import settings
from src.utils import setup_logger, normalize_url, is_valid_url


logger = setup_logger(__name__)


@dataclass
class ParsedInstruction:
    """Résultat du parsing d'une instruction"""
    url: str
    elements_to_watch: List[str]
    description: str
    keywords: List[str]
    success: bool
    raw_instruction: str
    error: Optional[str] = None


class AIAgent:
    """
    Agent IA utilisant Groq pour interpréter les instructions en langage naturel
    Identifie les URLs à surveiller et les éléments importants
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialise l'agent IA
        
        Args:
            api_key: Clé API Groq (utilise settings si non fourni)
            model: Modèle à utiliser (utilise settings si non fourni)
        """
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        
        if not self.api_key:
            raise ValueError("Groq API key manquante. Configurez GROQ_API_KEY dans .env")
        
        self.client = Groq(api_key=self.api_key)
        logger.info(f"AIAgent initialisé avec le modèle: {self.model}")
    
    def parse_instruction(self, instruction: str) -> ParsedInstruction:
        """
        Parse une instruction en langage naturel et extrait les informations
        
        Args:
            instruction: Instruction en français (ex: "surveille les prix sur Zalando")
            
        Returns:
            ParsedInstruction avec URL et éléments à surveiller
        """
        logger.info(f"Parsing de l'instruction: '{instruction}'")
        
        # Créer le prompt pour l'agent IA
        prompt = self._create_prompt(instruction)
        
        try:
            # Appel à l'API Groq
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Tu es un assistant expert en analyse d'instructions pour la surveillance de sites web.
Ta tâche est d'extraire:
1. L'URL exacte du site à surveiller
2. Les éléments spécifiques à surveiller (prix, fonctionnalités, articles, etc.)
3. Des mots-clés pertinents

Réponds UNIQUEMENT au format JSON valide, sans texte supplémentaire."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            # Extraire la réponse
            content = response.choices[0].message.content.strip()
            logger.debug(f"Réponse brute de l'IA: {content}")
            
            # Parser le JSON
            # Nettoyer la réponse si elle contient des balises markdown
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            
            parsed_data = json.loads(content)
            
            # Valider et normaliser l'URL
            url = parsed_data.get("url", "")
            if url:
                url = normalize_url(url)
                if not is_valid_url(url):
                    logger.warning(f"URL invalide extraite: {url}")
                    return ParsedInstruction(
                        url="",
                        elements_to_watch=[],
                        description="",
                        keywords=[],
                        success=False,
                        raw_instruction=instruction,
                        error=f"URL invalide: {url}"
                    )
            else:
                logger.error("Aucune URL extraite de l'instruction")
                return ParsedInstruction(
                    url="",
                    elements_to_watch=[],
                    description="",
                    keywords=[],
                    success=False,
                    raw_instruction=instruction,
                    error="Aucune URL trouvée dans l'instruction"
                )
            
            # Construire le résultat
            result = ParsedInstruction(
                url=url,
                elements_to_watch=parsed_data.get("elements_to_watch", []),
                description=parsed_data.get("description", instruction),
                keywords=parsed_data.get("keywords", []),
                success=True,
                raw_instruction=instruction
            )
            
            logger.info(f"✓ Instruction parsée avec succès: {url}")
            logger.debug(f"Éléments à surveiller: {result.elements_to_watch}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Erreur de parsing JSON: {str(e)}")
            logger.error(f"Contenu reçu: {content}")
            return ParsedInstruction(
                url="",
                elements_to_watch=[],
                description="",
                keywords=[],
                success=False,
                raw_instruction=instruction,
                error=f"Erreur de parsing JSON: {str(e)}"
            )
        
        except Exception as e:
            logger.error(f"Erreur lors du parsing: {str(e)}")
            return ParsedInstruction(
                url="",
                elements_to_watch=[],
                description="",
                keywords=[],
                success=False,
                raw_instruction=instruction,
                error=str(e)
            )
    
    def _create_prompt(self, instruction: str) -> str:
        """
        Crée le prompt pour l'agent IA
        
        Args:
            instruction: Instruction utilisateur
            
        Returns:
            Prompt formaté
        """
        return f"""Analyse cette instruction de surveillance de site web et extrais les informations au format JSON:

Instruction: "{instruction}"

Retourne un JSON avec cette structure exacte:
{{
    "url": "URL complète du site à surveiller (ex: https://www.example.com/page)",
    "elements_to_watch": ["liste", "des", "éléments", "à", "surveiller"],
    "description": "Description claire de ce qui doit être surveillé",
    "keywords": ["mots", "clés", "pertinents"]
}}

Exemples:
- "surveille les prix sur Zalando" → url: "https://www.zalando.fr", elements: ["prix", "promotions"]
- "monitore la page pricing de TechCorp" → url: "https://techcorp.com/pricing", elements: ["prix", "plans", "tarifs"]
- "track les nouvelles features de ProductY" → url: "https://producty.com/features", elements: ["fonctionnalités", "nouveautés"]

Important:
- L'URL doit être complète et valide
- Si le nom de domaine n'est pas évident, devine le plus probable
- Elements_to_watch doit être spécifique et pertinent

JSON:"""
    
    def validate_url(self, url: str) -> bool:
        """
        Valide si une URL est accessible
        
        Args:
            url: URL à valider
            
        Returns:
            True si l'URL est valide et accessible
        """
        if not is_valid_url(url):
            return False
        
        # On pourrait ajouter une vérification HTTP ici
        # mais on la garde simple pour l'instant
        return True


# Fonction de commodité
def parse_instruction(instruction: str) -> ParsedInstruction:
    """
    Fonction utilitaire pour parser une instruction rapidement
    
    Args:
        instruction: Instruction en langage naturel
        
    Returns:
        ParsedInstruction
    """
    agent = AIAgent()
    return agent.parse_instruction(instruction)


__all__ = [
    'AIAgent',
    'ParsedInstruction',
    'parse_instruction',
]
