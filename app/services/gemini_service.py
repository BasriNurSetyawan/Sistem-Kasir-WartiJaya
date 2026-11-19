"""Local AI and NLU Service Wrapper (Replaces Cloud Gemini API).

This module ensures 100% backward compatibility with existing callers while
running entirely offline on local Machine Learning (TF-IDF, Scikit-Learn)
without any external API key requirement.
"""

from app.services import local_nlu_service
from app.services.ai_response import SYSTEM_INSTRUCTION, clean_response


def is_gemini_available():
    """Gemini Cloud API is disabled in favor of 100% Local AI & ML."""
    return False


def generate_executive_insights(metrics):
    """Delegate to local ML service."""
    result = local_nlu_service.generate_executive_insights(metrics)
    result['insight'] = clean_response(result.get('insight'))
    return result


def ask_copilot(query, conversation_history, store_context):
    """Delegate to local NLU service."""
    result = local_nlu_service.ask_copilot(
        query, conversation_history, store_context, system_instruction=SYSTEM_INSTRUCTION
    )
    result['reply'] = clean_response(result.get('reply'))
    return result


def generate_market_basket_advice(popular_pairs, association_rules):
    """Delegate to local ML service."""
    result = local_nlu_service.generate_market_basket_advice(popular_pairs, association_rules)
    result['advice'] = clean_response(result.get('advice'))
    return result
