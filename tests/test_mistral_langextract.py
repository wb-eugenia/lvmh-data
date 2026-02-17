"""
Test LangExtract with Mistral API via OpenAI-compatible endpoint
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(override=True)

from src.mistral_rotator import get_mistral_key
import langextract as lx
from langextract import factory


def test_mistral_via_openai():
    """Test LangExtract with Mistral via OpenAI-compatible API."""
    
    api_key = get_mistral_key()
    if not api_key:
        print("[X] No Mistral API key found")
        return False
    
    print(f"[OK] Using Mistral API key: {api_key[:10]}...")
    
    # Define prompt and examples
    prompt = "Extract product, brand, budget from text"
    examples = [
        lx.data.ExampleData(
            text="Cliente busca bolso Hermès 5000€",
            extractions=[
                lx.data.Extraction(
                    extraction_class="produit",
                    extraction_text="bolso Hermès 5000€",
                    attributes={"marque": "Hermès", "budget": "5000€"}
                )
            ]
        )
    ]
    
    # Use factory to explicitly specify OpenAI provider
    # Mistral's OpenAI-compatible endpoint
    model_id = "mistral-small-latest"
    
    print(f"\n[->] Testing with model: {model_id} via OpenAI provider")
    
    try:
        # Create model config with explicit provider
        config = factory.ModelConfig(
            model_id=model_id,
            provider="OpenAILanguageModel",
            provider_kwargs={
                "api_key": api_key,
                "base_url": "https://api.mistral.ai/v1"  # Mistral endpoint
            }
        )
        model = factory.create_model(config)
        
        # Test simple extraction
        result = lx.extract(
            text_or_documents="Cliente busca bolso Dior 3000€",
            prompt_description=prompt,
            examples=examples,
            model=model,  # Pass the model directly
        )
        print(f"    [OK] SUCCESS!")
        print(f"    Result type: {type(result)}")
        
        if hasattr(result, 'extractions'):
            print(f"    Extractions: {len(result.extractions)} items")
            for ext in result.extractions:
                print(f"      - {ext.extraction_class}: {ext.extraction_text}")
        
        return True
        
    except Exception as e:
        print(f"    [X] FAILED: {type(e).__name__}: {str(e)[:300]}")
        import traceback
        traceback.print_exc()
        return False


def test_with_full_examples():
    """Test with full LVMH 4-pillar examples."""
    
    api_key = get_mistral_key()
    if not api_key:
        print("[X] No Mistral API key found")
        return False
    
    print("\n[->] Testing with LVMH 4-pillar examples...")
    
    # Define prompt and examples
    prompt = """Extract LVMH client interaction data in 4 categories:
    1. PRODUIT (marque, catégorie, budget, style)
    2. PROFIL CLIENT (statut VIC, contexte achat)
    3. HOSPITALITÉ (occasion, préférences)
    4. ACTION BUSINESS (next step, urgence)
    
    Use exact text. No paraphrasing."""
    
    examples = [
        lx.data.ExampleData(
            text="Mme Dupont cliente VIC cherche sac Hermès budget 8000€ anniversaire mari.",
            extractions=[
                lx.data.Extraction(
                    extraction_class="profil_client",
                    extraction_text="cliente VIC",
                    attributes={"statut": "VIC"}
                ),
                lx.data.Extraction(
                    extraction_class="produit",
                    extraction_text="sac Hermès budget 8000€",
                    attributes={"marque": "Hermès", "budget": "8000€"}
                ),
                lx.data.Extraction(
                    extraction_class="hospitalite",
                    extraction_text="anniversaire mari",
                    attributes={"occasion": "anniversaire"}
                )
            ]
        )
    ]
    
    test_text = "Mme Martin cliente fidèle cherche montre Rolex budget 15000€ pour son anniversaire"
    
    try:
        # Create model config with explicit provider
        config = factory.ModelConfig(
            model_id="mistral-small-latest",
            provider="OpenAILanguageModel",
            provider_kwargs={
                "api_key": api_key,
                "base_url": "https://api.mistral.ai/v1"
            }
        )
        model = factory.create_model(config)
        
        result = lx.extract(
            text_or_documents=test_text,
            prompt_description=prompt,
            examples=examples,
            model=model,
        )
        print(f"    [OK] SUCCESS with LVMH examples!")
        
        if hasattr(result, 'extractions'):
            print(f"    Extractions: {len(result.extractions)} items")
            for ext in result.extractions:
                print(f"      - {ext.extraction_class}: {ext.extraction_text}")
                if hasattr(ext, 'attributes') and ext.attributes:
                    print(f"        Attributes: {ext.attributes}")
        
        return True
        
    except Exception as e:
        print(f"    [X] FAILED: {type(e).__name__}: {str(e)[:200]}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("LangExtract + Mistral (OpenAI-Compatible) Test")
    print("=" * 60)
    
    success = test_mistral_via_openai()
    
    if success:
        print("\n" + "=" * 60)
        test_with_full_examples()
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)
