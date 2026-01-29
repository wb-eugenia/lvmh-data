import sys
import os
import asyncio
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd()))

from src.text_cleaner import MultilingualTextCleaner
from src.extractor import Tier3Enhanced

load_dotenv()

def test_pii():
    print("\n🔒 TESTING PII ANONYMIZATION:")
    cleaner = MultilingualTextCleaner()
    
    samples = [
        "Mme Dupont cherche un sac. Son email: sophie.dupont@gmail.com, tel: 06 12 34 56 78.",
        "Mr. Smith wants a refund. Contact: +33 7 89 01 23 45.",
        "M. Martin a un budget de 5000€.",
    ]
    
    for s in samples:
        # clean_text calls _anonymize_pii internaly
        res = cleaner.clean_text(s, "FR")
        print(f"  Input:  {s}")
        print(f"  Output: {res['cleaned']}")
        
    # Validation checks
    res1 = cleaner.clean_text("Mme Dupont", "FR")['cleaned']
    if "Mme [NAME]" in res1:
        print("  ✅ Name masking: OK")
    else:
        print(f"  ❌ Name masking: FAIL ({res1})")
        
    res2 = cleaner.clean_text("06 12 34 56 78", "FR")['cleaned']
    if "[PHONE]" in res2:
        print("  ✅ Phone masking: OK")
    else:
        print(f"  ❌ Phone masking: FAIL ({res2})")

async def test_mistral_init():
    print("\n🤖 TESTING MISTRAL TIER 3 INIT:")
    try:
        extractor = Tier3Enhanced()
        print(f"  ✅ Initialized Tier3Enhanced")
        print(f"  MODELS: {extractor.MODELS}")
        print(f"  Client Type: {type(extractor.client)}")
        
        # Check if client has chat.complete_async
        if hasattr(extractor.client.chat, 'complete_async'):
             print("  ✅ Client has 'complete_async' method")
        else:
             print("  ❌ Client MISSING 'complete_async' method")
             
    except Exception as e:
        print(f"  ❌ Init Failed: {e}")

if __name__ == "__main__":
    test_pii()
    asyncio.run(test_mistral_init())
