"""
Emotion detection utilities for avatar generation.

Analyzes text scripts to detect emotional tone and map to avatar expressions.
"""

from typing import Optional, Dict
import re
import structlog

logger = structlog.get_logger()

# Emotion keywords mapping
EMOTION_KEYWORDS = {
    "happy": [
        "happy", "excited", "joy", "wonderful", "amazing", "great", "fantastic",
        "love", "delighted", "thrilled", "cheerful", "pleased", "glad"
    ],
    "sad": [
        "sad", "unhappy", "disappointed", "sorry", "regret", "unfortunate",
        "depressed", "down", "blue", "melancholy", "grief"
    ],
    "angry": [
        "angry", "mad", "furious", "outraged", "annoyed", "frustrated",
        "irritated", "upset", "rage", "hate"
    ],
    "surprised": [
        "surprised", "shocked", "amazed", "astonished", "wow", "incredible",
        "unbelievable", "unexpected"
    ],
    "neutral": []
}

# Punctuation-based emotion hints
PUNCTUATION_EMOTIONS = {
    "!": "happy",  # Exclamation suggests excitement
    "?": "surprised",  # Questions can suggest curiosity
}


def detect_emotion_from_text(text: str, use_ml: bool = False) -> str:
    """
    Detect dominant emotion from text.
    
    Args:
        text: Input text to analyze
        use_ml: Whether to use ML-based detection (requires transformers)
    
    Returns:
        Emotion string: "neutral", "happy", "sad", "angry", "surprised"
    """
    if not text or len(text.strip()) < 10:
        return "neutral"
    
    # Try ML-based detection if enabled
    if use_ml:
        try:
            return _detect_emotion_ml(text)
        except Exception as e:
            logger.warning("ML emotion detection failed, using keyword fallback", error=str(e))
    
    # Fallback to keyword-based detection
    return _detect_emotion_keywords(text)


def _detect_emotion_keywords(text: str) -> str:
    """Detect emotion using keyword matching."""
    text_lower = text.lower()
    
    # Count emotion keywords
    emotion_scores: Dict[str, int] = {
        "happy": 0,
        "sad": 0,
        "angry": 0,
        "surprised": 0
    }
    
    for emotion, keywords in EMOTION_KEYWORDS.items():
        if emotion == "neutral":
            continue
        for keyword in keywords:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(keyword) + r'\b'
            matches = len(re.findall(pattern, text_lower))
            emotion_scores[emotion] += matches
    
    # Check punctuation
    exclamation_count = text.count("!")
    question_count = text.count("?")
    
    if exclamation_count > 2:
        emotion_scores["happy"] += exclamation_count // 2
    if question_count > 1:
        emotion_scores["surprised"] += question_count
    
    # Get dominant emotion
    max_score = max(emotion_scores.values())
    if max_score == 0:
        return "neutral"
    
    for emotion, score in emotion_scores.items():
        if score == max_score:
            logger.info("Emotion detected (keywords)", emotion=emotion, score=score)
            return emotion
    
    return "neutral"


def _detect_emotion_ml(text: str) -> str:
    """
    Detect emotion using ML model (transformers).
    
    Requires: pip install transformers torch
    """
    try:
        from transformers import pipeline
        
        # Use cached classifier if available
        if not hasattr(_detect_emotion_ml, 'classifier'):
            logger.info("Loading emotion classification model...")
            _detect_emotion_ml.classifier = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                top_k=1
            )
        
        # Classify (limit to first 512 chars for performance)
        result = _detect_emotion_ml.classifier(text[:512])[0][0]
        
        # Map model labels to our emotion set
        emotion_map = {
            "joy": "happy",
            "sadness": "sad",
            "anger": "angry",
            "fear": "neutral",
            "surprise": "surprised",
            "disgust": "neutral",
            "neutral": "neutral"
        }
        
        detected = emotion_map.get(result['label'].lower(), "neutral")
        confidence = result['score']
        
        logger.info("Emotion detected (ML)",
                   emotion=detected,
                   confidence=f"{confidence:.2f}",
                   raw_label=result['label'])
        
        return detected
        
    except ImportError:
        logger.warning("transformers not installed, using keyword detection")
        return _detect_emotion_keywords(text)
    except Exception as e:
        logger.error("ML emotion detection error", error=str(e))
        return _detect_emotion_keywords(text)


def get_emotion_parameters(
    emotion: str,
    expression_scale: Optional[float] = None,
    head_pose_scale: Optional[float] = None
) -> Dict[str, float]:
    """
    Get recommended parameters for an emotion.
    
    Args:
        emotion: Emotion type
        expression_scale: Override expression scale (None = use default)
        head_pose_scale: Override head pose scale (None = use default)
    
    Returns:
        Dict with expression_scale and head_pose_scale
    """
    # Default parameters per emotion
    defaults = {
        "neutral": {"expression": 0.8, "pose": 0.8},
        "happy": {"expression": 1.2, "pose": 1.1},
        "sad": {"expression": 0.9, "pose": 0.7},
        "angry": {"expression": 1.3, "pose": 1.2},
        "surprised": {"expression": 1.4, "pose": 1.3},
    }
    
    params = defaults.get(emotion, defaults["neutral"])
    
    return {
        "expression_scale": expression_scale if expression_scale is not None else params["expression"],
        "head_pose_scale": head_pose_scale if head_pose_scale is not None else params["pose"]
    }


# Example usage
if __name__ == "__main__":
    test_texts = [
        "I'm so excited about this amazing product!",
        "Unfortunately, we have some bad news to share.",
        "This is absolutely outrageous and unacceptable!",
        "Wow, I can't believe what just happened!",
        "The weather is nice today."
    ]
    
    for text in test_texts:
        emotion = detect_emotion_from_text(text, use_ml=False)
        params = get_emotion_parameters(emotion)
        print(f"\nText: {text}")
        print(f"Emotion: {emotion}")
        print(f"Parameters: {params}")
