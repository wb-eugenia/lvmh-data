"""
Taxonomy loader and validator for Voice to Tag extraction.
Handles loading, validation and tag lookup for the hierarchical taxonomy.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Optional


class Taxonomy:
    """Manages the tag taxonomy for extraction validation."""
    
    def __init__(self, taxonomy_path: str = "config/taxonomy_v1.json"):
        """
        Initialize taxonomy from JSON file.
        
        Args:
            taxonomy_path: Path to the taxonomy JSON file
        """
        self.taxonomy_path = Path(taxonomy_path)
        self._taxonomy: Dict = {}
        self._all_tags: Set[str] = set()
        self._tag_to_category: Dict[str, str] = {}
        self._load_taxonomy()
    
    def _load_taxonomy(self) -> None:
        """Load and parse the taxonomy JSON file."""
        if not self.taxonomy_path.exists():
            raise FileNotFoundError(f"Taxonomy file not found: {self.taxonomy_path}")
        
        with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
            self._taxonomy = json.load(f)
        
        # Build flat tag set and tag-to-category mapping
        categories = self._taxonomy.get('categories', {})
        
        for category_name, category_data in categories.items():
            # Support v1 structure (direct tags list)
            if 'tags' in category_data:
                for tag in category_data['tags']:
                    self._all_tags.add(tag)
                    self._tag_to_category[tag] = category_name
            
            # Support v2 structure (subcategories -> examples)
            if 'subcategories' in category_data:
                for sub_name, sub_data in category_data['subcategories'].items():
                    # Treat examples as valid tags for validation purposes
                    examples = sub_data.get('examples', [])
                    for tag in examples:
                        self._all_tags.add(tag)
                        self._tag_to_category[tag] = category_name

    def get_all_tags(self) -> List[str]:
        """Return sorted list of all valid tags."""
        return sorted(list(self._all_tags))
    
    def get_categories(self) -> List[str]:
        """Return list of all category names."""
        return list(self._taxonomy.get('categories', {}).keys())
    
    def get_tags_by_category(self, category: str) -> List[str]:
        """Get all tags for a specific category."""
        return self._taxonomy.get('categories', {}).get(category, {}).get('tags', [])
    
    def get_category_for_tag(self, tag: str) -> Optional[str]:
        """Get the category a tag belongs to."""
        return self._tag_to_category.get(tag)
    
    def is_valid_tag(self, tag: str) -> bool:
        """Check if a tag exists in the taxonomy."""
        return tag in self._all_tags
    
    def validate_tags(self, tags: List[str]) -> Dict[str, List[str]]:
        """
        Validate a list of tags against the taxonomy.
        
        Returns:
            Dict with 'valid' and 'invalid' tag lists
        """
        valid_tags = [t for t in tags if self.is_valid_tag(t)]
        invalid_tags = [t for t in tags if not self.is_valid_tag(t)]
        return {
            'valid': valid_tags,
            'invalid': invalid_tags
        }
    
    def get_taxonomy_json(self) -> str:
        """Return the full taxonomy as JSON string for prompts."""
        return json.dumps(self._taxonomy, indent=2, ensure_ascii=False)

    def get_tags_summary(self) -> str:
        """Return a compact summary of all tags for prompts."""
        lines = []
        categories = self._taxonomy.get('categories', {})
        
        for category_name, category_data in categories.items():
            # v1 style
            if 'tags' in category_data:
                tags = category_data['tags']
                lines.append(f"{category_name}: {', '.join(tags)}")
            
            # v2 style
            elif 'subcategories' in category_data:
                # For v2, show subcategory names and a few examples to keep prompt concise
                sub_summaries = []
                for sub_name, sub_data in category_data['subcategories'].items():
                    examples = sub_data.get('examples', [])[:3] # Limit to 3 examples
                    sub_summaries.append(f"{sub_name} ({', '.join(examples)}...)")
                lines.append(f"{category_name}: {'; '.join(sub_summaries)}")
                
        return "\n".join(lines)
    
    @property
    def version(self) -> str:
        """Return taxonomy version."""
        return self._taxonomy.get('metadata', {}).get('version', 'unknown')
    
    @property
    def num_tags(self) -> int:
        """Return total number of tags."""
        return len(self._all_tags)
    
    @property
    def num_categories(self) -> int:
        """Return number of categories."""
        return len(self.get_categories())


# Convenience function for quick loading
def load_taxonomy(path: str = "config/taxonomy_v1.json") -> Taxonomy:
    """Quick loader for taxonomy."""
    return Taxonomy(path)


if __name__ == "__main__":
    # Quick test
    taxonomy = Taxonomy()
    print(f"Loaded taxonomy v{taxonomy.version}")
    print(f"Categories: {taxonomy.num_categories}")
    print(f"Tags: {taxonomy.num_tags}")
    print("\nTags by category:")
    for cat in taxonomy.get_categories():
        tags = taxonomy.get_tags_by_category(cat)
        print(f"  {cat}: {len(tags)} tags")
