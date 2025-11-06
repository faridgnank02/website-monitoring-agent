"""
Test de l'agent IA avec différentes instructions
"""

from src.modules.ai_agent import parse_instruction

# Instructions de test
test_instructions = [
    "surveille les prix sur la page homme de Zalando",
    "monitore la page pricing de TechCorp pour les changements de tarifs",
    "track les nouvelles fonctionnalités sur la page produit de Notion",
    "surveille le blog de OpenAI pour les nouveaux articles sur GPT",
]

print("🤖 Test de l'Agent IA (CrewAI + Groq)")
print("=" * 80)
print()

for i, instruction in enumerate(test_instructions, 1):
    print(f"\n{'='*80}")
    print(f"Test {i}/{len(test_instructions)}")
    print(f"{'='*80}")
    print(f"📝 Instruction: \"{instruction}\"")
    print()
    
    result = parse_instruction(instruction)
    
    if result.success:
        print("✅ Parsing réussi!")
        print(f"\n🔗 URL extraite: {result.url}")
        print(f"\n📋 Éléments à surveiller:")
        for element in result.elements_to_watch:
            print(f"   • {element}")
        print(f"\n💡 Description: {result.description}")
        print(f"\n🏷️  Mots-clés: {', '.join(result.keywords)}")
    else:
        print(f"❌ Échec du parsing")
        print(f"Erreur: {result.error}")
    
    print()

print("\n" + "=" * 80)
print("✨ Tests terminés!")
