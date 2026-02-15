"""
Multilingual Text Cleaner for LVMH Voice Notes.
Removes filler words and verbal hesitations to improve LLM extraction quality.
Enhanced with Context-Aware cleaning, Protected Zones, and Semantic Deduplication.
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
import pandas as pd
from tqdm import tqdm
from difflib import SequenceMatcher

# DON'T import sentence_transformers at module level - it blocks for 30+ seconds
# Import lazily when needed to avoid Cloud Run startup timeout
HAS_EMBEDDINGS = None  # Will be set lazily

def _check_embeddings_available():
    global HAS_EMBEDDINGS
    if HAS_EMBEDDINGS is not None:
        return HAS_EMBEDDINGS
    try:
        from sentence_transformers import SentenceTransformer
        from torch.nn.functional import cosine_similarity
        import torch
        HAS_EMBEDDINGS = True
    except ImportError:
        HAS_EMBEDDINGS = False
    return HAS_EMBEDDINGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PIIEnforcer:
    """
    Couche PII avancée pour la détection et le masquage des données sensibles.
    Supporte 5 pays : FR, UK, ES, IT, DE
    """
    
    PATTERNS = {
        # IMPORTANT: IBAN avant carte bancaire pour éviter que l'IBAN soit partiellement masqué
        # IBAN: supporte formats avec/sans espaces, jusqu'à 34 caractères alphanumériques après le code pays
        'iban': (r'\b[A-Z]{2}\d{2}\s?(?:[A-Z0-9]{4}\s?){1,7}[A-Z0-9]{0,4}\b', '[RIB]'),
        # Cartes et paiement (patterns plus stricts)
        # Supporte: 4111111111111111, 4111 1111 1111 1111, 3782 8224 6310 005X (Amex avec masque)
        # Pattern strict: commence par un chiffre, pas par une lettre (évite de matcher dans IBAN)
        'carte_bancaire': (r'(?<![A-Z])\b(?:\d{4}[\s-]){2,3}[\dX]{4,6}\b|\b\d{15,16}\b', '[CARTE]'),
        'cvc': (r'\b(?:CVC|CVV|crypto)\s*:?\s*\d{3,4}\b', '[CVC]'),
        'exp': (r'\b(?:exp|expiration|expir|cad|valable|Ablauf)[\s:]*\d{2}[\/\-]?\d{2,4}\b', '[DATE_EXP]'),
        
        # Documents d'identité
        'ssn_us': (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]'),
        'numero_secu_fr': (r'\b[12]\s?\d{2}\s?\d{2}\s?(?:0\d|[1-9]\d)\s?\d{3}\s?\d{3}\s?(?:0\d|1[0-8])\b', '[SECU]'),
        'carte_vitale_fr': (r'\b1(?:\s*\d){12,15}\b', '[CARTE_VITALE]'),
        'dni_es': (r'\b\d{8}[A-Z]\b', '[DNI]'),
        'nif_es': (r'\b[XYZA-Z]\d{7,8}[A-Z]\b', '[NIF]'),
        'codice_fiscale_it': (r'\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b', '[FISCAL]'),
        'passport': (r'\b(?:passport|passeport|pasaporte)[\s:]+[A-Z]{1,2}\d{6,9}\b', '[PASSPORT]'),
        'personalausweis': (r'\b[A-Z]\d{2}[A-Z]\d{2}\w{1}\d{1}\b', '[ID]'),
        
        # Codes et références
        'code_porte': (r'\b(?:code|gate|porta|codigo|digicode|Türcode|buzzer|interphone)\s*(?:porte|entry|acces|porta|puerta)?\s*:?\s*\d{3,6}\b', '[CODE]'),
        'client_vip': (r'\b(?:VIP|client)\s*#?\s*\d{4,8}\b', '[VIP_ID]'),
        'produit_lv': (r'\b(?:LV|Louis Vuitton)-?[A-Z0-9-]{3,15}\b', '[PRODUIT_LV]'),
        
        # Adresses (patterns français) - must be before generic number patterns
        'adresse_paris': (r'\b\d{1,3}\s+(?:rue|avenue|boulevard|place|allée|chemin|impasse|champs?)\s+[\w\s\-\']+\d{5}\s+(?:Paris|Lyon|Marseille|Bordeaux|Lille|Nantes|Strasbourg|Nice|Toulouse)\b', '[ADRESSE]'),
        'adresse_livraison': (r'(?:livraison|expédition|ship)\s+(?:à|a|au|aux|urgente)?\s*:?\s*\d{1,3}\s+[\w\s\-\']+(?:\d{5})?', '[ADRESSE_LIVRAISON]'),
        'adresse_complete': (r'\d{1,3}\s+(?:Champs[-\s]Elysées|Avenue\s+\w+|Rue\s+\w+|Boulevard\s+\w+)\s*,?\s*\d{5}\s+\w+', '[ADRESSE_COMPLETE]'),
        
        # Téléphones internationaux (stricts avec indicatifs)
        'phone_fr': (r'(?:\+33|0)[1-9](?:\s?\d{2}){4}', '[PHONE]'),
        'phone_es': (r'\+34\d{9}', '[PHONE]'),
        'phone_it': (r'\+39\d{9,10}', '[PHONE]'),
        'phone_de': (r'\+49\d{10,11}', '[PHONE]'),
        'phone_uk': (r'\+44\d{10,11}', '[PHONE]'),
    }
    
    @classmethod
    def clean(cls, text: str, audit: bool = False) -> str:
        """
        Applique les patterns PII.
        Si audit=True, retourne aussi le compte par type PII.
        """
        pii_counts = {}
        for name, (pattern, mask) in cls.PATTERNS.items():
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
            if matches:
                pii_counts[name] = len(matches)
            text = re.sub(pattern, mask, text, flags=re.IGNORECASE)
        
        if audit:
            return text, pii_counts
        return text
    
    @classmethod
    def get_audit_report(cls, text: str) -> Dict:
        """Génère un rapport RGPD détaillé"""
        _, counts = cls.clean(text, audit=True)
        return {
            'total_pii_detected': sum(counts.values()),
            'pii_by_type': counts,
            'risk_level': 'HIGH' if sum(counts.values()) > 5 else 'MEDIUM' if sum(counts.values()) > 0 else 'LOW'
        }


class MultilingualTextCleaner:
    """
    Nettoyeur de texte avancé :
    1. Protection des entités business (Dates, Montants, Codes produits)
    2. Normalisation des variants orthographiques de fillers ("euhhh" -> "euh")
    3. Nettoyage contextuel (supprime "un peu" sauf si "un peu grand")
    4. Déduplication sémantique (si sentence_transformers dispo)
    """
    
    # -------------------------------------------------------------------------
    # CONFIGURATION
    # -------------------------------------------------------------------------

    PURE_FILLERS = {
        'FR': [
            # Hésitations sonores
            r'\b(euh|hum|bah|ben|bon|hein|quoi|voilà|alors|donc)\b',
            # Expressions d'hésitation / remplissage sans sens fort
            r'\b(tu sais|vous savez|tu vois|vous voyez)\b',
            r'\b(en fait|du coup|en gros|grosso modo)\b',
            r'\b(disons|disons que|on va dire)\b',
            r'\b(en quelque sorte|en quelque manière|pour ainsi dire|en quelque façon)\b',
            r'\b(c\'est-à-dire|à peu près)\b', # "plus ou moins" moved to nuances
            r'\b(eh bien|enfin|bref|là|machin|chose|truc|style|genre)\b',
            r'\b(si tu veux|si vous voulez|je veux dire|bonjour|salut|hello)\b',
        ],
        'EN': [
            r'\b(uh|um|er|ah|hmm|well|okay|ok|yeah|yep|right)\b',
            r'\b(you know|you see|I mean|I guess|I suppose)\b',
            r'\b(you know what I mean)\b',
            r'\b(sort of|kind of|like|basically|actually|literally)\b',
            r'\b(let me see|let\'s see)\b',
            r'\b(in a way|as it were|if you will)\b', # removed amount modifiers
        ],
        'IT': [
            r'\b(eh|ehm|beh|boh|va bene|ok|allora|quindi|cioè|insomma)\b',
            r'\b(tipo|tipo così|diciamo|diciamo che|praticamente|capito|sai|capisci|capite)\b',
            r'\b(se vuoi|se capite|se capisci)\b',
            r'\b(in qualche modo|per così dire)\b',
        ],
        'ES': [
            r'\b(eh|em|pues|bueno|vale|ok|entonces|ya)\b',
            r'\b(ya sabes|ya ves|ya veis|sabes)\b',
            r'\b(pues sí)\b',
            r'\b(digamos|digamos que|vamos a ver)\b',
            r'\b(o sea|es decir|tipo|como)\b',
            r'\b(de alguna manera|por así decirlo)\b',
            r'\b(si quieres|si queréis|en plan|en realidad)\b',
        ],
        'DE': [
            r'\b(äh|ähm|eh|halt|naja|genau|ja|okay|ok)\b',
            r'\b(sozusagen|gewissermaßen|irgendwie|quasi|eigentlich)\b',
            r'\b(weißt du|sag mal)\b',
            r'\b(auf eine Art|in gewisser Weise|so gesehen)\b',
            r'\b(wenn du willst|sagen wir)\b',
        ]
    }

    BUSINESS_NUANCES = {
        'FR': {
            'un peu': ['budget', 'flexible', 'grand', 'petit', 'large', 'cher', 'serré', 'juste'],
            'un petit peu': ['budget', 'flexible', 'grand', 'petit'],
            'plutôt': ['élégant', 'sportif', 'classique', 'moderne', 'jeune', 'âgé'],
            'assez': ['urgent', 'important', 'grand', 'petit', 'cher'],
            'plus ou moins': ['budget', 'âge', 'ans', 'euros'],
        },
        # Add basic support for EN amount modifiers to prevent stripping
        'EN': {
            'a bit': ['budget', 'flexible', 'big', 'small', 'tight', 'expensive'],
            'slightly': ['larger', 'smaller', 'damaged', 'worn'],
            'roughly': ['budget', 'years', '$'],
            'about': ['budget', 'years', '$'],
        }
    }

    FILLER_VARIANTS = {
        'FR': {
            'euh': ['euhh', 'euhhh', 'euhhhh', 'euuh', 'eeuh'],
            'hum': ['humm', 'hummm', 'hmm', 'hmmm'],
            'bah': ['bahh', 'baaah', 'baah'],
            'ben': ['benn', 'beeen', 'bhen'],
            'bon': ['boon', 'booon'],
        },
        'EN': {
            'uh': ['uhh', 'uhhh', 'uuuh'],
            'um': ['umm', 'ummm', 'uuum'],
            'hmm': ['hmmm', 'hmmmm'],
        }
    }

    def __init__(self, use_embeddings: bool = True):
        self.use_embeddings = use_embeddings and _check_embeddings_available()
        self.embedder = None
        self.current_lang = 'FR'
        
        if self.use_embeddings:
            try:
                logger.info("⏳ Loading semantic model for deduplication...")
                # Use a lightweight but effective model
                self.embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                logger.info("✅ Semantic model loaded")
            except Exception as e:
                logger.warning(f"⚠️ Could not load SentenceTransformer: {e}")
                self.use_embeddings = False
                
    # -------------------------------------------------------------------------
    # CORE CLEANING METHODS
    # -------------------------------------------------------------------------

    def _should_remove_nuance(self, text: str, match_term: str, position: int) -> bool:
        """Décide si supprimer une nuance selon si elle modifie un terme business voisin."""
        
        # Récupère contexte (5 mots avant/après)
        # On utilise une fenêtre de caractères pour simplifier, ou split
        words = text.split()
        
        # Trouver l'index du mot dans la liste de mots (approximatif mais rapide)
        # Note: position est l'index caractère. On doit mapper vers index mot.
        # Pour faire simple et robuste : on regarde autour dans le texte brut
        
        start_scope = max(0, position - 30)
        end_scope = min(len(text), position + len(match_term) + 30)
        context_window = text[start_scope:end_scope].lower()
        
        business_terms = self.BUSINESS_NUANCES.get(self.current_lang, {}).get(match_term.lower(), [])
        
        # Si un terme business est présent dans la fenêtre proche -> ON GARDE la nuance
        if any(term in context_window for term in business_terms):
            return False  # Ne pas supprimer
            
        return True  # Supprimer (c'est juste du bruit)

    def _normalize_fillers_variants(self, text: str, language: str) -> str:
        """Normalise les variants de fillers (ex: euhhh -> euh) avant traitement."""
        normalized = text
        variants_map = self.FILLER_VARIANTS.get(language, {})
        
        for canonical, variants in variants_map.items():
            for variant in variants:
                # Regex strict pour mot entier
                normalized = re.sub(
                    r'\b' + re.escape(variant) + r'\b',
                    canonical,
                    normalized,
                    flags=re.IGNORECASE
                )
        return normalized

    def _extract_protected_zones(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Remplace les entités critiques par des placeholders pour éviter corruption."""
        protected = {}
        placeholder_id = 0
        
        # 1. Montants (5000€, 5K, $500)
        # Supporte formats: 5 000 €, 5.000€, 5k, 5 k€
        amount_patterns = [
            r'\b\d{1,3}(?:[\s,.]\d{3})*\s*[kK€$euros]+\b',  # 5 000 €, 5k
            r'\b[€$]\s*\d+(?:[\s,.]\d+)*\b'                 # $500
        ]
        
        for pat in amount_patterns:
            for match in re.finditer(pat, text, re.I):
                placeholder = f"__AMOUNT_{placeholder_id}__"
                if placeholder not in protected: # Avoid double protect if overlap
                    protected[placeholder] = match.group()
                    text = text.replace(match.group(), placeholder, 1)
                    placeholder_id += 1

        # 2. Codes produits / Modèles (avec chiffres, ex: Birkin 25, Kelly 32)
        # Pattern: Majuscule + texte + espace + 2 chiffres
        product_matches = re.finditer(r'\b[A-Z][a-zA-Z]+\s+\d{2}\b', text)
        for match in product_matches:
            val = match.group()
            if "__" not in val: # Don't protect already protected
                placeholder = f"__PRODUCT_{placeholder_id}__"
                protected[placeholder] = val
                text = text.replace(val, placeholder, 1)
                placeholder_id += 1
                
        # 3. Dates (12/05/2024, 12 janvier)
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b'
        ]
        
        for pat in date_patterns:
            for match in re.finditer(pat, text, re.I):
                val = match.group()
                if "__" not in val:
                    placeholder = f"__DATE_{placeholder_id}__"
                    protected[placeholder] = val
                    text = text.replace(val, placeholder, 1)
                    placeholder_id += 1
                    
        return text, protected

    def _restore_protected_zones(self, text: str, protected: Dict[str, str]) -> str:
        """Restaure les zones protégées."""
        for placeholder, original in protected.items():
            text = text.replace(placeholder, original)
        return text

    def _remove_extra_chars(self, text: str) -> str:
        """Nettoyage caractères de base."""
        # Ponctuation répétée
        text = re.sub(r'([!?.]){2,}', r'\1', text)
        # Lettres répétées (>2)
        text = re.sub(r'([a-zA-Z])\1{2,}', r'\1', text)
        # Espaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def remove_duplicate_phrases(self, text: str, min_words: int = 3) -> Tuple[str, int]:
        """Déduplication intelligente (Sémantique si dispo, sinon séquence)."""
        if not text:
            return text, 0

        # Split sentences (using improved regex from before)
        sentences = re.split(r'(?<!\bM)(?<!\bMr)(?<!\bDr)(?<!\bMme)[.!?]+', text)
        unique_sentences = []
        duplicates_removed = 0
        
        # State for deduplication
        seen_phrases_text = set()
        seen_embeddings = [] # Only if usage embeddings
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            clean_sent = re.sub(r'\s+', ' ', sentence.lower().strip())
            word_count = len(clean_sent.split())
            
            if word_count < min_words:
                unique_sentences.append(sentence)
                continue
                
            is_dup = False
            
            # 1. Check Exact / String Fuzzy
            if clean_sent in seen_phrases_text:
                is_dup = True
            elif not self.use_embeddings:
                # Fallback to SequenceMatcher if no embeddings
                for seen in seen_phrases_text:
                     if SequenceMatcher(None, seen, clean_sent).ratio() > 0.85:
                         is_dup = True
                         break
            
            # 2. Check Semantic (if enabled and not yet found as dup)
            if not is_dup and self.use_embeddings and self.embedder:
                current_emb = self.embedder.encode(sentence, convert_to_tensor=True)
                
                # Compare with seen
                for seen_emb in seen_embeddings:
                     sim = cosine_similarity(current_emb.unsqueeze(0), seen_emb.unsqueeze(0)).item()
                     if sim > 0.85: # Seuil sémantique
                         is_dup = True
                         break
                
                if not is_dup:
                    seen_embeddings.append(current_emb)

            if not is_dup:
                seen_phrases_text.add(clean_sent)
                unique_sentences.append(sentence)
            else:
                duplicates_removed += 1
                
        # Reconstruct
        cleaned_text = '. '.join(unique_sentences)
        if cleaned_text and not cleaned_text.endswith('.'):
            cleaned_text += '.'
            
        return cleaned_text, duplicates_removed

    def _anonymize_pii(self, text: str) -> str:
        """
        Anonymisation des données personnelles (RGPD).
        - Emails
        - Téléphones (FR/Intl)
        - Noms (Pattern Civilité + Nom)
        """
        # 1. EMAILS
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        text = re.sub(email_pattern, '[EMAIL]', text)
        
        # 2. PHONES (Focus FR + Generic)
        # Handle +33 (non-word boundary start) OR 0 (word boundary start)
        # Matches: +33 6... | 06... | 0033 6...
        phone_pattern = r'(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}\b'
        text = re.sub(phone_pattern, '[PHONE]', text)
        
        # 3. NOMS PROPRES (Basés sur civilité)
        # Add Mr. (with dot) and ensure robust matching
        civilities = r'(?:M\.|Mme|Mlle|Mrs?|Ms|Monsieur|Madame|Dr|Prof\.|Mr\.)'
        # Pattern: Civilité + Espace + Mot Majuscule (+ optionnel trait d'union Autre)
        name_pattern = fr'\b{civilities}\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:[- ][A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+)?\b'
        
        def replace_name(match):
            # Keep the civility, mask the name
            full = match.group()
            # Split by first space to separate civility
            parts = full.split(maxsplit=1)
            if len(parts) > 0:
                return f"{parts[0]} [NAME]"
            return "[NAME]"

        text = re.sub(name_pattern, replace_name, text)
        
        # 4. PII AVANCÉ via PIIEnforcer (cartes, IBAN, CVC, carte vitale, etc.)
        text = PIIEnforcer.clean(text)
        
        return text

    def clean_text(self, text: str, language: str) -> Dict:
        """Pipeline complet de nettoyage."""
        if not text or not isinstance(text, str):
            return {
                'original': '',
                'cleaned': '',
                'fillers_removed': 0,
                'duplicates_removed': 0,
                'compression_ratio': 1.0,
                'tokens_saved_estimate': 0
            }

        self.current_lang = language
        language_supported = language in self.PURE_FILLERS or language in self.BUSINESS_NUANCES
        
        # 0. Protection données critiques D'ABORD (montants, dates, produits)
        # Cela évite que le PII anonymization ne corrompe les montants
        processing_text, protected_zones = self._extract_protected_zones(text)
        
        # 1. Anonymisation PII (sur le texte avec placeholders)
        # Les placeholders __AMOUNT_X__ etc ne seront pas affectés par les patterns PII
        processing_text = self._anonymize_pii(processing_text)
        
        # 2. Normalisation caractères & variants fillers
        processing_text = self._remove_extra_chars(processing_text)
        processing_text = self._normalize_fillers_variants(processing_text, language)
        
        # 2b. Word-level deduplication (consecutive repeated words like "bonjour bonjour")
        processing_text = re.sub(r'\b(\w+)(?:\s+\1\b)+', r'\1', processing_text, flags=re.IGNORECASE)
        
        fillers_count = 0
        
        # 3. Suppression Fillers PURS (Safe)
        if language in self.PURE_FILLERS:
            for pattern in self.PURE_FILLERS[language]:
                matches = re.findall(pattern, processing_text, flags=re.IGNORECASE)
                fillers_count += len(matches)
                processing_text = re.sub(pattern, '', processing_text, flags=re.IGNORECASE)
        
        # 4. Suppression Nuances Contextuelles (Smart)
        if language in self.BUSINESS_NUANCES:
            for nuance, business_terms in self.BUSINESS_NUANCES[language].items():
                # We iteratively find and check each occurrence
                # Using a while loop to handle changing string length
                pattern = r'\b' + re.escape(nuance) + r'\b'
                
                # Find all matches first to avoid infinite loops if we replace with something containing pattern
                # But here we replace with empty string so it's fine
                # However, indices shift. Better to do pass by pass or restart search
                
                has_match = True
                while has_match:
                    match = re.search(pattern, processing_text, re.IGNORECASE)
                    if not match:
                        has_match = False
                        continue
                        
                    if self._should_remove_nuance(processing_text, nuance, match.start()):
                        # Remove it
                        processing_text = processing_text[:match.start()] + processing_text[match.end():]
                        # Fix potential double spaces created
                        processing_text = re.sub(r'\s{2,}', ' ', processing_text)
                        fillers_count += 1
                    else:
                        # Skip this match for this iteration? Regex will find it again.
                        # We need to mask it temporarily to continue searching
                        # Or use finditer and build a reconstruction
                        # Simpler: Replace valid boolean matches with a temporary placeholder
                        # that we revert later.
                        
                        # Let's use a temporary placeholder for SAFE occurences
                        mask = f"__KEEP_{nuance.upper().replace(' ', '_')}__"
                        processing_text = processing_text[:match.start()] + mask + processing_text[match.end():]
                
                # Restore kept nuances
                processing_text = re.sub(r'__KEEP_[A-Z_]+__', nuance, processing_text)

        # 5. Clean cleanup (spaces, punctuation)
        processing_text = re.sub(r'\s+', ' ', processing_text)
        processing_text = re.sub(r'\s+([.,;:!?])', r'\1', processing_text)
        processing_text = processing_text.strip()
        
        # 6. Deduplication (Semantic/Fuzzy)
        if language_supported:
            processing_text, dupe_count = self.remove_duplicate_phrases(processing_text)
        else:
            dupe_count = 0
        
        # 7. Restore Protected Zones
        final_text = self._restore_protected_zones(processing_text, protected_zones)
        
        # Metrics
        compression = len(final_text) / len(text) if len(text) > 0 else 1.0
        
        return {
            'original': text,
            'cleaned': final_text,
            'fillers_removed': fillers_count,
            'duplicates_removed': dupe_count,
            'compression_ratio': compression,
            'tokens_saved_estimate': int((len(text) - len(final_text)) / 4)
        }

    def clean_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """Nettoie un dataset complet."""
        results = []
        total_saved = 0
        
        logger.info(f"🧹 Starting cleaning (Embeddings={'ON' if self.use_embeddings else 'OFF'})...")
        
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Cleaning"):
            res = self.clean_text(row.get('Transcription', ''), row.get('Language', 'FR'))
            row_dict = row.to_dict()
            row_dict.update({
                'Transcription_original': res['original'],
                'Transcription': res['cleaned'],
                'fillers_removed': res['fillers_removed'],
                'duplicates_removed': res.get('duplicates_removed', 0),
                'compression_ratio': res['compression_ratio'],
                'tokens_saved': res['tokens_saved_estimate']
            })
            results.append(row_dict)
            total_saved += res['tokens_saved_estimate']
            
        logger.info(f"✅ Finished. Est. tokens saved: {total_saved:,}")
        return pd.DataFrame(results)

if __name__ == "__main__":
    import os
    
    # 1. Quick Unit Tests
    cleaner = MultilingualTextCleaner(use_embeddings=True)
    print("\n🔬 UNIT TESTS:")
    res = cleaner.clean_text("Cliente euh cherche un sac un peu plus grand, budget 5000€.", "FR")
    print(f"Test 1: {res['cleaned']}")

    # 2. Main Dataset Processing
    input_file = 'data/raw/LVMH_Notes_CA101-400.csv'
    output_file = 'data/processed/LVMH_Notes_CA101-400_cleaned.csv'
    
    if os.path.exists(input_file):
        print(f"\n📂 Loading {input_file}...")
        df = pd.read_csv(input_file)
        
        # Limit to 300 if needed, but file name implies 101-400 which is 300 rows
        print(f"📊 Processing {len(df)} notes...")
        
        df_cleaned = cleaner.clean_dataset(df)
        
        os.makedirs('data/processed', exist_ok=True)
        df_cleaned.to_csv(output_file, index=False)
        print(f"✅ Exported to {output_file}")
        
        # Stats
        total_fillers = df_cleaned['fillers_removed'].sum()
        total_dups = df_cleaned['duplicates_removed'].sum()
        total_tokens = df_cleaned['tokens_saved'].sum()
        
        print(f"\n📈 FINAL STATS:")
        print(f"  - Fillers removed: {total_fillers:,}")
        print(f"  - Duplicates removed: {total_dups:,}")
        print(f"  - Tokens saved: {total_tokens:,} (~${total_tokens * 0.00015:.2f})")
    else:
        print(f"❌ File not found: {input_file}")
