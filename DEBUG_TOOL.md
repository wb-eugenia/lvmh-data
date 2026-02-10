# Outil de Debug Pipeline

## Vue d'ensemble

L'outil **Debug Pipeline** remplace l'ancien onglet "Résultats CSV" dans le ManagerView. Il permet de tester manuellement des transcriptions et de voir en détail tout ce qui se passe dans la pipeline.

## Fonctionnalités

### 1. Input de Texte
- Zone de texte libre pour entrer une transcription
- Sélection de langue (FR, EN, ES, IT, DE)
- Boutons d'exemples rapides pour tester

### 2. Métriques en Temps Réel
- **Tier utilisé** : T1, T2 ou T3 avec couleur (gris/jaune/rouge)
- **Confiance** : Score de confiance du routing (0-100%)
- **Temps API** : Latence réseau
- **Temps de traitement** : Durée totale du pipeline
- **Tags extraits** : Nombre de tags
- **Qualité** : Score de qualité global

### 3. Visualisation des 4 Piliers

#### Pilier 1 : Univers Produit
- Catégories détectées
- Produits mentionnés
- Préférences (couleurs, matières, styles)

#### Pilier 2 : Profil Client
- Contexte d'achat (type, comportement, urgence)
- Relation (cadeau pour, occasion)
- Profession et style de vie

#### Pilier 3 : Hospitalité & Care
- Allergies et restrictions (avec alerte rouge si détectées)
- Préférences de livraison (emballage discret)
- Occasion spéciale

#### Pilier 4 : Action Business
- Budget détecté (potentiel + spécifique)
- Niveau d'urgence (low/medium/high)
- Next Best Action (NBA) avec raisonnement

### 4. RAG (Matching Produits)
- Liste des produits recommandés
- Score de similarité pour chaque produit
- Prix et catégorie

### 5. Routing & Performance
- Détails du tier sélectionné
- Confiance du routing
- Priorité (low/medium/high/critical)
- Cache hit/miss
- Raisons du routing

### 6. RGPD & Anonymisation
- Détection de PII (emails, téléphones, cartes, etc.)
- Catégories de données sensibles détectées
- Texte anonymisé

### 7. Méta-Analyse
- Quality Score
- Confiance d'extraction
- Score de complétude
- Informations manquantes (warnings)
- Risk Flags (alertes)

### 8. JSON Brut
- Vue dépliable du JSON complet retourné par l'API
- Pour debug avancé

## Utilisation

1. **Naviguer** vers l'onglet "Debug Pipeline" dans le ManagerView
2. **Entrer** une transcription dans la zone de texte
3. **Sélectionner** la langue appropriée
4. **Cliquer** sur "Analyser"
5. **Explorer** les résultats dans les différentes sections dépliables

## Exemples de Test

### Exemple 1: Client VIP
```
M. Legrand, client VIP depuis 5 ans, cherche un cadeau pour sa femme. 
Budget 5000€. Il veut quelque chose d'élégant et intemporel.
```

### Exemple 2: Allergies
```
Mme Martin est allergique au cuir véritable. Elle cherche un sac 
synthétique noir pour le travail. Budget 800€.
```

### Exemple 3: Urgence
```
M. Dupont a besoin d'une ceinture marron urgent pour un mariage 
samedi. Budget ouvert.
```

## API Endpoint Utilisé

```
POST /api/analyze
Content-Type: application/json

{
  "text": "...",
  "language": "FR",
  "client_id": "DEBUG_..."
}
```

## Troubleshooting

### L'analyse ne fonctionne pas
- Vérifier que le backend est démarré sur le port 8080
- Vérifier la connexion réseau
- Consulter les logs du navigateur (F12 > Console)

### Les résultats semblent incorrects
- Vérifier la langue sélectionnée
- Essayer avec une transcription plus détaillée
- Consulter le JSON brut pour voir les données brutes

### Performance lente
- Vérifier le temps de traitement affiché
- Si > 5s, c'est probablement Tier 3 (normal)
- Vérifier que le cache sémantique est activé

## Fichiers Concernés

- `frontend-v2/src/components/DebugAnalyzer.jsx` : Composant principal
- `frontend-v2/src/components/ManagerView.jsx` : Intégration dans le Manager
- `api/routers/analyze.py` : Endpoint API
