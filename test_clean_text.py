import sys
sys.path.insert(0, '.')
from src.text_cleaner import MultilingualTextCleaner

cleaner = MultilingualTextCleaner()
text = "Euh bonjour je cherche un sac"
result = cleaner.clean_text(text, language='FR')
print(f"Original: {text}")
print(f"Cleaned: {result.get('cleaned_text')}")
print(f"Stats: {result.get('stats')}")
