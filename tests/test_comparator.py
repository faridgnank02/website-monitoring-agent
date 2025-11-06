"""
Test du module Content Comparator
"""

from src.modules.content_comparator import compare_content

print("🔄 Test du Content Comparator")
print("=" * 80)

# Test 1: Aucun changement
print("\n" + "="*80)
print("Test 1: Aucun changement")
print("="*80)

content_v1 = """
# Page Pricing

## Plan Pro
Prix: 99€/mois
Fonctionnalités:
- 10 utilisateurs
- 100GB stockage
- Support premium
"""

content_v2 = content_v1  # Identique

result = compare_content(content_v1, content_v2, threshold=1.0)
print(f"Changements détectés: {result.has_changes}")
print(f"Score: {result.change_score:.2f}%")
print(f"Hash ancien: {result.hash_old}")
print(f"Hash nouveau: {result.hash_new}")

# Test 2: Changement de prix (significatif)
print("\n" + "="*80)
print("Test 2: Changement de prix (> seuil)")
print("="*80)

content_v1 = """
# Page Pricing

## Plan Pro
Prix: 99€/mois
Fonctionnalités:
- 10 utilisateurs
- 100GB stockage
- Support premium
"""

content_v2 = """
# Page Pricing

## Plan Pro
Prix: 129€/mois
Fonctionnalités:
- 10 utilisateurs
- 100GB stockage
- Support premium
"""

result = compare_content(content_v1, content_v2, threshold=1.0)
print(f"Changements détectés: {result.has_changes}")
print(f"Score: {result.change_score:.2f}%")
print(f"\nRésumé:")
print(result.diff_summary)

# Test 3: Ajout de fonctionnalités
print("\n" + "="*80)
print("Test 3: Ajout de nouvelles fonctionnalités")
print("="*80)

content_v1 = """
# Features

## Fonctionnalités actuelles
- Collaboration en temps réel
- Exports PDF
- Intégrations Slack
"""

content_v2 = """
# Features

## Fonctionnalités actuelles
- Collaboration en temps réel
- Exports PDF
- Intégrations Slack
- IA générative (NOUVEAU)
- API avancée (NOUVEAU)
- Templates personnalisés (NOUVEAU)
"""

result = compare_content(content_v1, content_v2, threshold=1.0)
print(f"Changements détectés: {result.has_changes}")
print(f"Score: {result.change_score:.2f}%")
print(f"\nLignes ajoutées: {len(result.added_lines)}")
for line in result.added_lines[:5]:
    print(f"  + {line}")

# Test 4: Éléments dynamiques filtrés
print("\n" + "="*80)
print("Test 4: Filtrage des éléments dynamiques (timestamps)")
print("="*80)

content_v1 = """
# Blog Post

Article publié le 2025-11-05
Updated: 2025-11-05 10:30:00
Session ID: abc123def456

Contenu de l'article...
"""

content_v2 = """
# Blog Post

Article publié le 2025-11-06
Updated: 2025-11-06 03:00:00
Session ID: xyz789ghi012

Contenu de l'article...
"""

result = compare_content(content_v1, content_v2, threshold=1.0)
print(f"Changements détectés: {result.has_changes}")
print(f"Score: {result.change_score:.2f}%")
print("Note: Les timestamps et Session ID sont filtrés automatiquement")

# Test 5: Changement mineur (< seuil)
print("\n" + "="*80)
print("Test 5: Changement mineur (< 1% = ignoré)")
print("="*80)

content_v1 = """
Lorem ipsum dolor sit amet, consectetur adipiscing elit.
Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.
Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
Nisi ut aliquip ex ea commodo consequat.
Duis aute irure dolor in reprehenderit in voluptate velit esse.
Cillum dolore eu fugiat nulla pariatur.
Excepteur sint occaecat cupidatat non proident.
Sunt in culpa qui officia deserunt mollit anim id est laborum.
"""

content_v2 = content_v1.replace("Lorem ipsum", "Lorem Ipsum")  # Changement mineur

result = compare_content(content_v1, content_v2, threshold=1.0)
print(f"Changements détectés: {result.has_changes}")
print(f"Score: {result.change_score:.2f}%")
print(f"Seuil: 1.0%")
print(f"→ Changement ignoré car score < seuil")

print("\n" + "="*80)
print("✨ Tests terminés!")
print("="*80)
