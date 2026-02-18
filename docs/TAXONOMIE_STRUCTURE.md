# Documentation de la Taxonomie LVMH V2.2

## Vue d'ensemble

La taxonomie LVMH V2.2 est un système de classification à 4 piliers utilisé pour structurer les informations extraites des notes vocals des Client Advisors. Elle permet une analyse hyper-personnalisée des profils clients et de leurs besoins.

- **Version** : 2.2
- **Dernière mise à jour** : 2026-01-28

---

## Architecture à 4 Piliers

| Pilier | Description | Catégories |
|--------|-------------|------------|
| **Pilier 1 - Univers Produit** | Produits souhaités, catégories, styles, couleurs, matériaux | `products`, `materials`, `colors`, `context_usage` |
| **Pilier 2 - Profil Client** | Contexte d'achat, statut socio-professionnel, style de vie | `professions`, `lifestyle`, `context` |
| **Pilier 3 - Hospitalité & Care** | Occasions spéciales, allergies, régime alimentaire | `occasions`, `allergies`, `dietary` |
| **Pilier 4 - Action Business** | Potentiel budget, urgence, Next Best Action | `budget`, `customer_intent`, `luxury_service` |

---

## Pilier 1 : Univers Produit

### 1.1 Catégories de produits (`products`)

| Catégorie | Description | Exemples |
|-----------|-------------|----------|
| **Maroquineries iconic** | Sacs emblématiques LV | `capucines`, `neverfull`, `speedy`, `keepall`, `dauphine`, `twist`, `petite_malle`, `onthego` |
| **Maroquineries travel** | Luggage & travel | `horizon`, `pegase`, `travel_luggage`, `trunk` |
| **Maroquineries accessories** | Petits cuirs | `small_leather`, `belts`, `toiletry`, `vanity`, `cosmetic` |
| **Prêt-à-porter** | Habillement | `womenswear`, `menswear`, `ready_to_wear`, `outerwear` |
| **Chaussures** | Types de chaussures | `sneakers`, `heels`, `loafers`, `shoes` |
| **Accessoires** | Accessoires mode | `scarves`, `eyewear`, `headwear`, `fragrance`, `accessories` |
| **Montres & Joaillerie** | Horlogerie et bijouterie | `watches`, `jewelry` |
| **Matériaux preferés** | Préférences de matière | `monogram`, `damier`, `epi`, `empreinte`, `taiga`, `leather_preference`, `canvas_preference` |

### 1.2 Matériaux (`materials`)

```
smooth_leather    → Cuir lisse
grained_leather   → Cuir grainé
canvas            → Toile (Monogram, Damier)
exotic            → Exotique (Croco, Python, Autruche)
suede             → Daim / Veau velours
```

### 1.3 Couleurs (`colors`)

```
black             → Noir
brown_cognac      → Marron / Cognac
navy              → Bleu marine
beige_neutral     → Beige / Taupe / Écru / Sable
bold_colors       → Rouge / Vert / Jaune / Rose / Fuchsia
```

### 1.4 Contexte d'usage (`context_usage`)

```
professional_work → Usage professionnel / Bureau
travel            → Voyage / Vacances
evening           → Soirée / Événement gala
casual_daily      → Usage quotidien
gift              → Cadeau
```

---

## Pilier 2 : Profil Client

### 2.1 Professions (`professions`)

**Secteur Médical :**
- `medical_specialist`, `medical_general`, `dentist`, `pharmacist`, `nurse`, `medical_physician`, `medical_surgeon`

**Secteur Juridique :**
- `legal_corporate`, `legal_family`, `legal_general`, `legal_lawyer`, `notary`, `judge`

**Secteur Finance :**
- `banker`, `trader`, `investor`, `fund_manager`, `accountant`, `cfo`, `ceo`, `c_suite`, `director`, `board_member`

**Secteur Tech :**
- `tech_engineer`, `tech_lead`, `data_scientist`, `product_manager`, `tech_executable`, `entrepreneur_tech`, `entrepreneur_startup`

**Secteur Création :**
- `architect`, `designer`, `creative_designer`, `artist`, `artist_painter`, `photographer`, `writer`

**Secteur Entertainment :**
- `producer`, `director_film`, `actor`, `entertainer`, `influencer`, `influenceur`, `lifestyle_content_creator`

**Secteur Immobilier :**
- `real_estate`, `business_owner`

**Autres :**
- `professor`, `researcher`, `scientist`, `fashion_industry`, `art_dealer`, `luxury_retail`, `professional_athlete`, `diplomat`, `sustainable_values`

### 2.2 Style de vie (`lifestyle`)

**Collections & Arts :**
```
art_collector, art_lover, music_lover, theater_lover
```

**Gastronomie & Boissons :**
```
wine_collector, wine_enthusiast, gastronome, champagne_lover
```

**Sports :**
```
golf, tennis, ski, equestrian, sailing, fitness, yoga, running
sports_swimming, sports_crossfit, sports_combat
```

**Voyage :**
```
travel_frequent, jet_setter, world_traveler
```

**Automobile :**
```
car_collector, luxury_cars
```

**Tech & Modernité :**
```
tech_enthusiast, tech_early_adopter
```

**Bien-être :**
```
spa_wellness, wellness
```

**Valeurs :**
```
philanthropist, sustainable, eco_conscious
```

**Loisirs :**
```
housewarming, creative_designer
```

---

## Pilier 3 : Hospitalité & Care

### 3.1 Occasions (`occasions`)

| Type | Tags |
|------|------|
| **Cadeaux romantiques** | `wedding_gift`, `engagement_gift`, `valentines_gift` |
| **Cadeaux familiaux** | `birthday_gift`, `mothers_day`, `fathers_day`, `christmas_gift`, `baby_gift`, `christening` |
| **Cadeaux professionnels** | `graduation_gift`, `retirement_gift`, `career_milestone` |
| **Cadeaux rituels** | `coming_of_age` |
| **Achats personnels** | `self_reward`, `impulse_purchase` |

### 3.2 Allergies (`allergies`)

```
nickel_allergy        → Allergie au nickel
latex_allergy        → Allergie au latex
nut_allergy          → Allergie aux noix
gluten_intolerance   → Intolérance au gluten
lactose_intolerance  → Intolérance au lactose
shellfish_allergy    → Allergie aux crustacés
pollen_allergy       → Allergie au pollen
sulfite_allergy      → Allergie aux sulfites
perfume_sensitivity  → Sensibilité aux parfums
animal_allergy       → Allergie aux animaux
```

**Niveaux de sévérité** : `low`, `medium`, `high`

### 3.3 Régime alimentaire (`dietary`)

```
vegan           → Végan
vegetarian      → Végétarien
pescatarian     → Pescatarien
gluten_free     → Sans gluten
halal           → Halal
kosher          → Casher
organic_only    → Bio uniquement
```

---

## Pilier 4 : Action Business

### 4.1 Contexte client (`context`)

| Statut | Description |
|--------|-------------|
| `vip` | Client Very Important Person |
| `vic` | Client Very Important Client |
| `first_visit` | Première visite |
| `regular` | Client régulier |

**Intentions d'achat :**
```
customer_intent      → Intention d'achat détectée
ultimate              → Achat ultime
high_potential        → Fort potentiel
high_net_worth        → High Net Worth
```

**Contextes d'achat :**
```
gift_for_spouse      → Cadeau pour conjoint
gift_for_child       → Cadeau pour enfant
gift_for_parent      → Cadeau pour parent
gift_for_friend      → Cadeau pour ami
gift_for_colleague   → Cadeau pour collègue
gift_for_self        → Achat personnel
shopping_with_spouse → Achat avec conjoint
wedding              → Mariage
wedding_anniversary  → Anniversaire de mariage
```

### 4.2 Budget (`budget`)

| Niveau | Gamme | Indicateurs |
|--------|-------|-------------|
| `entry_level` | < 2 000€ | "petit budget", "moins de 2000" |
| `core` | 2 000 - 5 000€ | "budget moyen", "2-5k" |
| `high` | 5 000 - 15 000€ | "beau budget", "haut de gamme", "5-15k" |
| `ultra_high` | > 15 000€ | "sans limite", "exceptionnel", "plus de 15" |
| `flexible_unknown` | Flexible | "budget flexible", "ouvert" |

### 4.3 Intentions & Services (`customer_intent`, `luxury_service`)

**Mots-clés intention d'achat :**
```
chercher, besoin, aimerait, souhaite, demande, recherche,
regarder, essayer, voir, passage, visite, appel, revoir
```

**Mots-clés service luxury :**
```
accueil, boutique, service, expérience, remplacement,
réparation, entretien, nettoyage, merci, sourire, plaisir
```

---

## Mots-clés produits

Chaque catégorie de produit possède des mots-clés multilingues pour l'extraction :

| Catégorie | Langues | Exemples |
|-----------|---------|----------|
| `leather_goods` | FR, EN, IT, DE | "sac", "bag", "borsa", "tasche" |
| `small_leather` | FR, EN, IT | "pochette", "clutch", "portefeuille", "wallet" |
| `fragrance` | FR, EN, IT, DE | "parfum", "perfume", "profumo", "eau de parfum" |
| `jewelry` | FR, EN, IT, DE | "bijoux", "jewel", "earring", "necklace", "bracelet" |
| `shoes` | FR, EN, IT, DE | "chaussure", "shoe", "escarpin", "talon" |
| `accessories` | FR, EN | "écharpe", "scarf", "lunettes", "sunglasses" |

---

## Flux d'extraction

```
Note Vocale
     ↓
Text Cleaner (nettoyage)
     ↓
Smart Router V3 (scoring 0-100)
     ↓
    ├─ Score < 20  → Tier 1 (Regex/Règles)
    ├─ Score 20-75 → Tier 2 (Groq/Mistral)
    └─ Score > 75  → Tier 3 (Mistral Large/GPT-4)
     ↓
Extraction des tags selon les 4 piliers
     ↓
RAG Product Matching
     ↓
Recommandation NBA
```

---

## RGPD & Compliance

- Tous les tags sensibles (données médicales, allergies) sont anonymisés avant traitement LLM
- Detection automatique des données personnelles (emails, phones, noms)
- Logs d'audit pour traçabilité

---

*Document généré automatiquement depuis `config/taxonomy_v2.2.json`*