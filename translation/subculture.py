"""
Subculture-aware translation handling
"""
from typing import Dict, Any
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SubcultureSlangHandler:
    def __init__(self):
        # Initialize pattern categories
        self.subculture_patterns = {
            'dating': {
                'patterns': {
                    'meetup': r'(约\s*?茶|喝\s*?咖啡|吃\s*?饭)',
                    'availability': r'(有空|在线上|在吗|在不在)',
                    'interest': r'(缘分|眼缘|聊聊|了解)',
                    'personal': r'(身高|体重|颜值|素质|经验)',
                },
                'translations': {
                    '约茶': ['tea time', 'meet up'],
                    '喝咖啡': ['coffee date', 'casual meet'],
                    '吃饭': ['dinner date', 'meal together']
                }
            },
            'intimate': {
                'patterns': {
                    'hints': r'(暗示|明示|懂的都懂|xhs)',
                    'mood': r'(想你|想约|寂寞|无聊|空虚)',
                    'invitation': r'(来玩|一起|陪我|约吗)',
                    'status': r'(单身|有主|空窗|一个人)'
                },
                'translations': {
                    '暗示': ['hinting', 'suggesting'],
                    '明示': ['stating', 'directly saying'],
                    '懂的都懂': ['you know what I mean', 'if yk yk']
                }
            },
            'service': {
                'patterns': {
                    'type': r'(推拿|按摩|SPA|轻松)',
                    'style': r'(专业|业余|兼职|全职)',
                    'experience': r'(老手|新人|熟练|生手)'
                },
                'translations': {
                    '推拿': ['massage', 'bodywork'],
                    '按摩': ['massage', 'therapy'],
                    'SPA': ['spa', 'relaxation']
                }
            },
            'location': {
                'patterns': {
                    'area': r'(上门|到付|外围|本地)',
                    'venue': r'(住处|家里|你家|我家)',
                    'transport': r'(车费|路费|打车|接送)'
                },
                'translations': {
                    '上门': ['visit', 'come over'],
                    '到付': ['pay on arrival', 'pay later'],
                    '本地': ['local', 'nearby']
                }
            }
        }
        
        # Context intensity levels
        self.context_intensity = {
            'dating': 0.7,
            'intimate': 1.0,
            'service': 0.8,
            'location': 0.6
        }
        
        # Compile patterns
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        self.compiled_patterns = {}
        for category, data in self.subculture_patterns.items():
            self.compiled_patterns[category] = {
                name: re.compile(pattern)
                for name, pattern in data['patterns'].items()
            }

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze text for subculture-specific patterns"""
        results = {
            'categories': [],
            'matches': {},
            'intensity': 0
        }
        
        total_matches = 0
        for category, patterns in self.compiled_patterns.items():
            category_matches = {}
            for name, pattern in patterns.items():
                matches = pattern.findall(text)
                if matches:
                    category_matches[name] = matches
                    total_matches += len(matches)
            
            if category_matches:
                results['categories'].append(category)
                results['matches'][category] = category_matches
                results['intensity'] += (
                    len(category_matches) * 
                    self.context_intensity[category]
                )
        
        if total_matches > 0:
            results['intensity'] /= total_matches
        
        if results['categories']:
            results['primary_context'] = max(
                results['categories'],
                key=lambda x: len(results['matches'][x])
            )
        
        return results

    async def adapt_translation(self, text: str, translation: str, 
                              analysis: Dict) -> str:
        """Adapt translation based on subculture analysis"""
        adapted = translation
        
        for category in analysis['categories']:
            if category in self.subculture_patterns:
                translations = self.subculture_patterns[category]['translations']
                for cn_term, en_options in translations.items():
                    if cn_term in text:
                        # Choose translation based on intensity
                        index = min(
                            len(en_options) - 1,
                            int(analysis['intensity'] * len(en_options))
                        )
                        adapted = adapted.replace(
                            cn_term, 
                            en_options[index]
                        )
        
        return adapted

    def get_translation_prompt(self, analysis: Dict) -> str:
        """Generate translation prompt based on subculture analysis"""
        if not analysis['categories']:
            return "Translate naturally while preserving any implications."
            
        prompts = []
        
        # Add category-specific prompts
        if 'dating' in analysis['categories']:
            prompts.append("maintain dating-specific terminology")
        if 'intimate' in analysis['categories']:
            prompts.append("preserve intimate nuances appropriately")
        if 'social' in analysis['categories']:
            prompts.append("keep social context clear")
        if 'service' in analysis['categories']:
            prompts.append("maintain service-specific terminology")
        if 'location' in analysis['categories']:
            prompts.append("keep location context appropriate")
            
        # Add intensity-based guidance
        if analysis['intensity'] > 0.8:
            prompts.append("maintain strong contextual implications")
        elif analysis['intensity'] > 0.5:
            prompts.append("preserve moderate suggestive elements")
        else:
            prompts.append("keep subtle hints")
            
        return f"Please {', '.join(prompts)} while ensuring natural flow."
