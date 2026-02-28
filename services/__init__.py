"""
Services module
===============
Contains all business logic and integrations:
- AI Pipeline orchestration
- Feature processing
- Product listing generation
"""

from services.pipeline import AIPipeline

ai_pipeline = AIPipeline()

__all__ = ['ai_pipeline']
