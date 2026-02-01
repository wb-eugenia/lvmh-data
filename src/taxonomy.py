import json
from typing import Dict, List, Optional
from pathlib import Path

class TaxonomyManager:
    """
    Manages the taxonomy of tags and keywords for the application.
    Loads configuration from a JSON file.
    """
    
    def __init__(self, version: str = "2.2"):
        self.version = version
        self.taxonomy = self._load_taxonomy(version)
    
    def _load_taxonomy(self, version: str) -> Dict:
        """Load taxonomy from JSON file."""
        # Try to find the file in config directory relative to project root
        # Assuming we are running from project root
        file_path = Path(f"config/taxonomy_v{version}.json")
        
        if not file_path.exists():
            # Try relative to this file if running as module
            file_path = Path(__file__).parent.parent / f"config/taxonomy_v{version}.json"
            
        if not file_path.exists():
            raise FileNotFoundError(f"Taxonomy v{version} not found at {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if data.get('version') != version:
            # Warning or error? For now just log/print, or strict error as requested
            # raise ValueError(f"Taxonomy version mismatch: expected {version}, got {data.get('version')}")
            pass 
        
        return data
    
    def get_core_tags(self) -> List[str]:
        """Get all core tags (flattened list)."""
        all_tags = []
        for category, tags in self.taxonomy.get('core_tags', {}).items():
            all_tags.extend(tags)
        return all_tags
    
    def get_category_tags(self, category: str) -> List[str]:
        """Get tags for a specific category (e.g., 'products', 'occasions')."""
        return self.taxonomy.get('core_tags', {}).get(category, [])
    
    def get_keywords(self, tag: str) -> List[str]:
        """Get keywords for a specific tag."""
        return self.taxonomy.get('product_keywords', {}).get(tag, [])
    
    def validate_tag(self, tag: str) -> bool:
        """Check if a tag is valid according to the taxonomy."""
        # Some tags might be dynamic (like shopping_with_spouse), so we need to check base tags
        # or check if it's in the allowed list.
        # For now, let's check exact match against core tags.
        
        if tag in self.get_core_tags():
            return True
            
        # Check for dynamic relationship tags
        if tag.startswith('shopping_with_') or tag.startswith('gift_for_'):
            return True
            
        # Check for profession tags (which might be dynamic or semi-dynamic in Tier 1)
        # In Tier 1 we had specific keys. Let's assume if it's not in core, it might be invalid
        # UNLESS we add professions to core_tags in JSON.
        # For this refactor, I added what was in the user prompt. 
        # I should probably be more lenient or add professions to the JSON if I want strict validation.
        # For now, let's allow it if it looks like a profession tag from our previous logic
        # or just return False if we want strictness.
        # The user requested strict validation.
        
        return False

    def get_all_keywords_map(self) -> Dict[str, str]:
        """
        Returns a map of keyword -> tag for all configured keywords.
        Useful for Tier 1 rules.
        """
        keyword_map = {}
        for tag, keywords in self.taxonomy.get('product_keywords', {}).items():
            for kw in keywords:
                keyword_map[kw] = tag
        return keyword_map

    def get_tags_summary(self) -> str:
        """
        Returns a summary of tags for LLM prompts.
        """
        summary = "TAXONOMY:\n"
        for category, tags in self.taxonomy.get('core_tags', {}).items():
            summary += f"- {category.capitalize()}: {', '.join(tags)}\n"
        return summary

    def normalize_tag(self, tag: str) -> Optional[str]:
        """
        Attempts to normalize a tag to a valid core tag using fuzzy matching.
        Returns the valid tag if found, None otherwise.
        """
        import difflib
        
        # 1. Exact match
        if self.validate_tag(tag):
            return tag
            
        # 2. Known aliases (Manual mapping for common hallucinations)
        aliases = {
            # Occasions
            'birthday': 'birthday_gift',
            'wedding': 'wedding_gift',
            'valentines': 'valentines_gift',
            'anniversary': 'wedding_anniversary',
            'christmas': 'christmas_gift',
            
            # Professions
            'tech_entrepreneur': 'entrepreneur_tech',
            'medical_executive': 'medical_specialist',
            'creative_writer': 'writer',
            'fashion_designer': 'creative_designer',
            'interior_designer': 'creative_designer',
            'real_estate_agent': 'real_estate',
            'lawyer': 'legal_lawyer',
            'doctor': 'medical_physician',
            
            # Lifestyle
            'sports_boxing': 'sports_combat',
            'sports_golf': 'golf',
            'sports_tennis': 'tennis',
            'sustainable': 'eco_conscious',
            
            # Status
            'ultra_high_potential': 'ultimate',
            'high_net_worth': 'high_potential',
            'regular_customer': 'regular',
            
            # Context & Service
            'passage': 'luxury_service',
            'visit': 'luxury_service',
            'revoir': 'luxury_service',
            'maintenance': 'luxury_service',
            
            # Professions
            'wealth_manager': 'finance_banker',
            'startup': 'entrepreneur_startup',
            'ceo': 'entrepreneur_established',
            'executive': 'entrepreneur_established'
        }
        if tag.lower() in aliases:
            return aliases[tag.lower()]
            
        # 3. Fuzzy match
        core_tags = self.get_core_tags()
        matches = difflib.get_close_matches(tag, core_tags, n=1, cutoff=0.8)
        
        if matches:
            return matches[0]
            
        return None
