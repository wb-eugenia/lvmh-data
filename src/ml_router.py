"""
ML Router - Routeur basé sur Machine Learning
Remplace les heuristiques par un modèle entraîné pour une meilleure précision de routing
"""

import os
import json
import pickle
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

# Try importing sklearn
try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, classification_report
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    logger.warning("scikit-learn not available, falling back to heuristic router")


@dataclass
class MLRoutingDecision:
    """Decision from ML router"""
    tier: int
    confidence: float
    probs: List[float]  # Probabilities for each tier
    features: Dict[str, float]
    model_version: str


class MLRouter:
    """
    Routeur ML avec Random Forest pour prédire le tier optimal
    
    Features utilisées:
    - TF-IDF du texte
    - Longueur du texte
    - Nombre de mots
    - Présence de mots-clés critiques (VIP, budget, etc.)
    """
    
    KEYWORDS_FEATURES = {
        'has_vip': r'\b(vip|vic|ultimate|platinum)\b',
        'has_budget': r'\b(budget|€|\$|euros?|k\s*€)\b',
        'has_urgent': r'\b(urgent|asap|aujourd|demain|today)\b',
        'has_gift': r'\b(cadeau|gift|anniversaire|noël|mariage)\b',
        'has_complaint': r'\b(plainte|mécontent|problème|déçu|insatisfait)\b',
        'has_allergy': r'\b(allergi|allergy|intolérance)\b',
        'has_negation': r'\b(pas|sans|non|not|no)\b',
        'has_question': r'\?',
    }
    
    def __init__(self, model_dir: str = "models/router"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        self.model: Optional[Pipeline] = None
        self.is_trained = False
        self.model_version = "0.0"
        
        # Feedback buffer for online learning
        self.feedback_buffer: List[Dict] = []
        self.min_feedback_for_retrain = 50
        
        if HAS_SKLEARN:
            self._load_or_init_model()
        else:
            logger.warning("ML Router: scikit-learn not available")
    
    def _extract_features(self, text: str, language: str) -> Dict[str, float]:
        """Extract numerical features from text"""
        import re
        
        text_lower = text.lower()
        words = text.split()
        
        features = {
            'length': len(text),
            'word_count': len(words),
            'avg_word_length': np.mean([len(w) for w in words]) if words else 0,
            'sentence_count': len([s for s in re.split(r'[.!?]+', text) if s.strip()]),
            'question_count': text.count('?'),
            'exclamation_count': text.count('!'),
            'digit_count': sum(c.isdigit() for c in text),
            'uppercase_ratio': sum(c.isupper() for c in text) / max(len(text), 1),
        }
        
        # Add keyword features
        for feature_name, pattern in self.KEYWORDS_FEATURES.items():
            features[feature_name] = 1.0 if re.search(pattern, text_lower) else 0.0
        
        return features
    
    def _load_or_init_model(self):
        """Load existing model or initialize new one"""
        model_path = os.path.join(self.model_dir, "router_model.pkl")
        version_path = os.path.join(self.model_dir, "version.txt")
        
        if os.path.exists(model_path) and os.path.exists(version_path):
            try:
                with open(model_path, 'rb') as f:
                    self.model = pickle.load(f)
                with open(version_path, 'r') as f:
                    self.model_version = f.read().strip()
                self.is_trained = True
                logger.info(f"✅ ML Router loaded (version {self.model_version})")
                return
            except Exception as e:
                logger.error(f"Failed to load model: {e}")
        
        # Initialize new model
        self._init_new_model()
    
    def _init_new_model(self):
        """Initialize a new untrained model"""
        if not HAS_SKLEARN:
            return
        
        self.model = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=500, ngram_range=(1, 2))),
            ('clf', RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                class_weight='balanced'
            ))
        ])
        self.is_trained = False
        logger.info("🆕 ML Router initialized (untrained)")
    
    def predict(self, text: str, language: str = "FR") -> Optional[MLRoutingDecision]:
        """
        Predict optimal tier for given text
        Returns None if model not trained or sklearn unavailable
        """
        if not HAS_SKLEARN or not self.is_trained or self.model is None:
            return None
        
        try:
            # Get prediction probabilities
            probs = self.model.predict_proba([text])[0]
            tier = int(np.argmax(probs)) + 1  # Tiers are 1, 2, 3
            confidence = float(np.max(probs))
            
            # Extract features for debugging
            features = self._extract_features(text, language)
            
            return MLRoutingDecision(
                tier=tier,
                confidence=confidence,
                probs=probs.tolist(),
                features=features,
                model_version=self.model_version
            )
        except Exception as e:
            logger.error(f"ML prediction failed: {e}")
            return None
    
    def train(self, texts: List[str], labels: List[int], language: str = "FR") -> Dict:
        """
        Train or retrain the model
        
        Args:
            texts: List of note texts
            labels: List of optimal tiers (1, 2, or 3)
        
        Returns:
            Training metrics
        """
        if not HAS_SKLEARN:
            return {"error": "scikit-learn not available"}
        
        if len(texts) < 10:
            return {"error": "Need at least 10 samples to train"}
        
        try:
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=0.2, random_state=42, stratify=labels
            )
            
            # Train
            self.model.fit(X_train, y_train)
            
            # Evaluate
            y_pred = self.model.predict(X_test)
            accuracy = accuracy_score(y_test, y_pred)
            
            # Save model
            self._save_model()
            
            self.is_trained = True
            self.model_version = datetime.now().strftime("%Y.%m.%d-%H%M")
            
            metrics = {
                "accuracy": round(accuracy, 3),
                "train_samples": len(X_train),
                "test_samples": len(X_test),
                "model_version": self.model_version,
                "classification_report": classification_report(y_test, y_pred, output_dict=True)
            }
            
            logger.info(f"✅ ML Router trained (accuracy: {accuracy:.3f})")
            return metrics
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {"error": str(e)}
    
    def add_feedback(self, text: str, predicted_tier: int, actual_tier: int, was_correct: bool):
        """
        Add feedback for online learning
        """
        self.feedback_buffer.append({
            'text': text,
            'predicted_tier': predicted_tier,
            'actual_tier': actual_tier,
            'was_correct': was_correct,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save feedback
        feedback_path = os.path.join(self.model_dir, "feedback.json")
        try:
            existing = []
            if os.path.exists(feedback_path):
                with open(feedback_path, 'r') as f:
                    existing = json.load(f)
            existing.extend(self.feedback_buffer)
            with open(feedback_path, 'w') as f:
                json.dump(existing[-1000:], f)  # Keep last 1000
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
        
        # Check if retraining needed
        if len(self.feedback_buffer) >= self.min_feedback_for_retrain:
            logger.info(f"🔄 Retraining triggered ({len(self.feedback_buffer)} feedback samples)")
            # In production, trigger async retraining here
            self.feedback_buffer = []
    
    def _save_model(self):
        """Save model to disk"""
        try:
            model_path = os.path.join(self.model_dir, "router_model.pkl")
            version_path = os.path.join(self.model_dir, "version.txt")
            
            with open(model_path, 'wb') as f:
                pickle.dump(self.model, f)
            
            with open(version_path, 'w') as f:
                f.write(self.model_version)
                
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
    
    def get_stats(self) -> Dict:
        """Get router statistics"""
        return {
            "enabled": HAS_SKLEARN,
            "trained": self.is_trained,
            "model_version": self.model_version,
            "feedback_buffer_size": len(self.feedback_buffer),
            "min_feedback_for_retrain": self.min_feedback_for_retrain
        }


# Singleton instance
_ml_router: Optional[MLRouter] = None


def get_ml_router() -> MLRouter:
    """Get or create ML router singleton"""
    global _ml_router
    if _ml_router is None:
        _ml_router = MLRouter()
    return _ml_router
