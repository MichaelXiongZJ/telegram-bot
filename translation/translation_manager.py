"""
Advanced translation management with OpenAI integration and fallback
"""
from openai import AsyncOpenAI
from deep_translator import GoogleTranslator
import logging
from typing import Dict, Any
from datetime import datetime
import json
from .patterns import IntensityAnalyzer, ModernChineseAdapter
from .subculture import SubcultureSlangHandler
from .cache import TranslationCache
from config import get_config

logger = logging.getLogger(__name__)

class TranslationManager:
    def __init__(self, api_key: str, cache_db_path: str, model: str = "gpt-3.5-turbo"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.cache = TranslationCache(cache_db_path)
        
        # Initialize components
        self.intensity_analyzer = IntensityAnalyzer()
        self.modern_adapter = ModernChineseAdapter()
        self.slang_handler = SubcultureSlangHandler()
        
        # Initialize Google translators for fallback
        self._init_google_translators()
        
        # Token usage tracking
        self.total_tokens = 0
        self.total_cost = 0

    def _init_google_translators(self):
        """Initialize Google Translators with error handling"""
        try:
            self.google_zh_to_en = GoogleTranslator(source='zh-CN', target='en')
            self.google_en_to_zh = GoogleTranslator(source='en', target='zh-CN')
            logger.info("Google Translators initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Translators: {e}")
            self.google_zh_to_en = None
            self.google_en_to_zh = None

    async def translate(self, text: str, source_lang: str, target_lang: str, 
                        context_type: str = 'group') -> Dict[str, Any]:
        """Main translation function with fallback mechanism"""
        config = get_config()  # Load the updated configuration dynamically
        
        try:
            # Check cache first
            cached = await self.cache.get_cached_translation(text, source_lang, target_lang)
            if cached and cached['quality_score'] >= config.TRANSLATION_MIN_QUALITY:
                return {
                    'translation': cached['translation'],
                    'source': 'cache',
                    'quality_score': cached['quality_score']
                }

            # Analyze patterns and context
            intensity_analysis = await self.intensity_analyzer.analyze_intensity(text, context_type)
            subculture_analysis = await self.slang_handler.analyze_text(text)
            
            # Determine if we should use GPT
            use_gpt = (
                intensity_analysis['final_intensity'] > 3 or
                subculture_analysis['intensity'] > 0.5 or
                len(text.split()) > 5
            )

            if use_gpt:
                try:
                    base_prompt = self.intensity_analyzer.get_intensity_preservation_prompt(intensity_analysis)
                    subculture_prompt = self.slang_handler.get_translation_prompt(subculture_analysis)
                    combined_prompt = f"{base_prompt} {subculture_prompt}"
                    
                    # GPT Translation
                    translation = await self._gpt_translate(
                        text, source_lang, target_lang, combined_prompt
                    )
                    quality_score = config.TRANSLATION_MIN_QUALITY  # Dynamically set the quality score
                    translation_source = 'gpt'
                except Exception as e:
                    logger.error(f"GPT translation failed, falling back to Google: {e}")
                    translation = await self._google_translate(text, source_lang, target_lang)
                    quality_score = config.TRANSLATION_MIN_QUALITY - 0.1  # Slightly below minimum for fallback
                    translation_source = 'google'
            else:
                # Google Translate for simple messages
                translation = await self._google_translate(text, source_lang, target_lang)
                quality_score = config.TRANSLATION_MIN_QUALITY - 0.1
                translation_source = 'google'
            
            # Fallback to GPT if quality is too low
            if quality_score < config.TRANSLATION_MIN_QUALITY:
                base_prompt = self.intensity_analyzer.get_intensity_preservation_prompt(intensity_analysis)
                subculture_prompt = self.slang_handler.get_translation_prompt(subculture_analysis)
                combined_prompt = f"{base_prompt} {subculture_prompt}"

                translation = await self._gpt_translate(text, source_lang, target_lang, combined_prompt)
                quality_score = config.TRANSLATION_MIN_QUALITY  # Match the exact minimum threshold
                translation_source = 'gpt'
            
            # Cache the result
            await self.cache.store_translation(
                text, translation, source_lang, target_lang, quality_score
            )
            
            return {
                'translation': translation,
                'source': translation_source,
                'quality_score': quality_score,
                'intensity_analysis': intensity_analysis,
                'subculture_analysis': subculture_analysis
            }
            
        except Exception as e:
            logger.error(f"Translation error: {e}")
            # Emergency fallback to Google Translate
            try:
                translation = await self._google_translate(text, source_lang, target_lang)
                return {
                    'translation': translation,
                    'source': 'google_emergency',
                    'quality_score': config.TRANSLATION_MIN_QUALITY - 0.2,
                    'error': str(e)
                }
            except Exception as fallback_error:
                logger.error(f"Emergency fallback failed: {fallback_error}")
                return {
                    'translation': text,
                    'source': 'failed',
                    'quality_score': 0.0,
                    'error': str(e)
                }


    async def _google_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """Handle Google translation with error handling"""
        try:
            translator = (self.google_zh_to_en if source_lang == 'zh' 
                        else self.google_en_to_zh)
            
            if not translator:
                raise ValueError("Google Translator not initialized")
                
            return translator.translate(text)
        except Exception as e:
            logger.error(f"Google translation error: {e}")
            raise

    async def _gpt_translate(self, text: str, source_lang: str, 
                           target_lang: str, prompt: str) -> str:
        """Handle GPT translation with context"""
        system_prompt = f"""You are a translator specialized in adult content and modern internet communication.
Translate from {source_lang} to {target_lang}.
{prompt}
Preserve the style, tone, and implications of the original message.
Maintain appropriate intensity and cultural context."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.7,
                max_tokens=len(text.split()) * 20
            )
            
            # Track usage
            self.total_tokens += response.usage.total_tokens
            self.total_cost += (response.usage.total_tokens / 1000) * 0.01
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"GPT translation error: {e}")
            raise

    async def get_usage_statistics(self) -> Dict[str, Any]:
        """Get usage statistics"""
        cache_stats = await self.cache._get_cache_stats()
        
        return {
            'total_tokens': self.total_tokens,
            'total_cost': self.total_cost,
            'cache_stats': cache_stats,
            'translations_count': cache_stats['total_entries'],
            'cache_hit_rate': cache_stats['hit_rate']
        }

    async def cleanup(self):
        """Cleanup resources"""
        await self.cache.cleanup()