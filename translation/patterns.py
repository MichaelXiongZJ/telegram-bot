"""
Pattern recognition and intensity analysis for translations
"""
import re
from typing import Dict, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class IntensityAnalyzer:
    def __init__(self):
        # Modern Chinese internet patterns
        self.cn_patterns = {
            # Base patterns
            'kaomoji': r'(\(づ￣3￣\)づ|\(╯°□°）╯|╮\(￣▽￣\)╭)',
            'emoji_text': r'(😊|😍|😘|🥰|💕|💗|💓|💞|💖|💝)',
            
            # Internet expressions
            'internet_slang': (
                r'(awsl|xswl|yyds|绝绝子|啊这|蚌埠住了|'
                r'麻了|顶不住|破防了|不愧是你|永远的神|'
                r'太可了|就这|搞快点|太强了|太牛了)'
            ),
            
            # Tone and intensity markers
            'tone_markers': r'([!！]{2,}|[?？]{2,}|\.{3,}|[啊哦呜]{2,})',
            'intensity_chars': r'[很太非常极超级特别]',
            'emotion_chars': r'[想要需渴望盼望期待]',
            
            # Physical descriptions
            'physical_desc': r'[软滑嫩润湿甜香]',
            'state_desc': r'[热冷颤抖酥麻]',
            'action_desc': r'[摸揉捏按压推]',
            
            # Relationship terms
            'relationship': r'[亲密暧昧缠绵]',
            'intimacy': r'[情人爱人宝贝]',
            
            # Metaphorical expressions
            'metaphors': r'(云雨|巫山|露水|蜜意|销魂|迷醉)',
        }
        
        # English patterns
        self.en_patterns = {
            # Base patterns
            'intensifiers': r'\b(very|really|so|quite|extremely)\b',
            'emotions': r'\b(want|need|desire|crave|yearn)\b',
            
            # Physical descriptions
            'sensations': r'\b(soft|smooth|wet|warm|hot|tight)\b',
            'actions': r'\b(caress|stroke|touch|rub|massage)\b',
            'states': r'\b(trembling|shaking|quivering|throbbing)\b',
            
            # Relationship terms
            'intimacy': r'\b(intimate|close|personal|private)\b',
            'relationship': r'\b(lover|baby|darling|dear)\b',
            
            # Context markers
            'location': r'\b(bedroom|bed|sheets|blanket)\b',
            'time': r'\b(night|evening|moment|forever)\b'
        }
        
        # Context multipliers for different situations
        self.context_multipliers = {
            'private': 1.2,
            'group': 0.8,
            'public': 0.6
        }

    async def analyze_intensity(self, text: str, context_type: str = 'group') -> Dict[str, Any]:
        """Analyze text intensity with context awareness"""
        is_chinese = self._is_chinese(text)
        patterns = self.cn_patterns if is_chinese else self.en_patterns
        
        # Initialize analysis
        analysis = {
            'patterns_found': {},
            'intensity_scores': {},
            'total_matches': 0
        }
        
        # Analyze each pattern type
        base_intensity = 0
        for pattern_type, pattern in patterns.items():
            matches = len(re.findall(pattern, text))
            if matches > 0:
                analysis['patterns_found'][pattern_type] = matches
                analysis['total_matches'] += matches
                
                # Calculate intensity contribution
                intensity_score = matches * self._get_pattern_weight(pattern_type)
                analysis['intensity_scores'][pattern_type] = intensity_score
                base_intensity += intensity_score
        
        # Apply context multiplier
        context_mult = self.context_multipliers.get(context_type, 1.0)
        final_intensity = min(5, base_intensity * context_mult)
        
        return {
            'raw_intensity': base_intensity,
            'context_multiplier': context_mult,
            'final_intensity': final_intensity,
            'analysis': analysis,
            'language': 'zh' if is_chinese else 'en'
        }

    def _is_chinese(self, text: str) -> bool:
        """Detect if text is primarily Chinese"""
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text.strip())
        return chinese_chars / max(total_chars, 1) > 0.5

    def _get_pattern_weight(self, pattern_type: str) -> float:
        """Get weight for different pattern types"""
        weights = {
            'kaomoji': 0.3,
            'emoji_text': 0.3,
            'tone_markers': 0.5,
            'intensity_chars': 0.8,
            'emotion_chars': 0.7,
            'physical_desc': 1.0,
            'state_desc': 0.9,
            'action_desc': 1.0,
            'relationship': 0.8,
            'intimacy': 1.0,
            'metaphors': 0.9,
            # English patterns
            'intensifiers': 0.6,
            'emotions': 0.7,
            'sensations': 0.9,
            'actions': 0.8,
            'states': 0.7,
            'location': 0.5,
            'time': 0.4
        }
        return weights.get(pattern_type, 0.5)

    def get_intensity_preservation_prompt(self, analysis: Dict) -> str:
        """Generate translation prompt based on intensity analysis"""
        intensity = analysis['final_intensity']
        prompts = []
        
        if intensity >= 4:
            prompts.append("maintain high emotional intensity and intimate tone")
        elif intensity >= 3:
            prompts.append("preserve moderate suggestive elements and emotional nuances")
        elif intensity >= 2:
            prompts.append("keep subtle implications while maintaining natural flow")
        else:
            prompts.append("translate naturally while preserving any subtle hints")
            
        # Add pattern-specific guidance
        if analysis['analysis']['patterns_found'].get('metaphors'):
            prompts.append("preserve metaphorical expressions appropriately")
        if analysis['analysis']['patterns_found'].get('intimacy'):
            prompts.append("maintain intimate context sensitively")
            
        return " and ".join(prompts)

class ModernChineseAdapter:
    def __init__(self):
        self.modern_mappings = {
            'awsl': ['dying from cuteness', 'absolutely adorable'],
            'xswl': ['laughing to death', 'ROFL'],
            'yyds': ['GOAT', 'absolutely the best'],
            '绝绝子': ['totally perfect', 'absolutely amazing'],
            '蚌埠住了': ["can't handle this", "completely losing it"],
            '麻了': ['mind blown', 'totally numb'],
            '破防了': ['emotional damage', 'hitting right in the feels'],
            '太可了': ['too cute', 'adorably perfect'],
            '冲鸭': ["let's go", "full speed ahead"],
            '顶不住': ["can't take it", "too much to handle"],
            '不愧是你': ["as expected", "living up to expectations"],
            '搞快点': ["hurry up", "make it quick"]
        }
        
        self.style_patterns = {
            r'[啊]{3,}': lambda m: 'aaa' * (len(m.group()) // 3),
            r'[哈]{3,}': lambda m: 'haha' * (len(m.group()) // 2),
            r'[。]{3,}': '...',
            r'[！]{2,}': '!!',
            r'[？]{2,}': '??'
        }

    async def adapt_translation(self, text: str, intensity_analysis: Dict) -> str:
        """Adapt translation for modern Chinese internet style"""
        intensity = intensity_analysis['final_intensity']
        adapted = text
        
        # Apply modern slang translations
        for cn_term, en_options in self.modern_mappings.items():
            if cn_term in text:
                # Choose translation based on intensity
                index = min(len(en_options) - 1, 
                          int(intensity * len(en_options) / 5))
                adapted = adapted.replace(cn_term, en_options[index])
        
        # Apply style patterns
        for pattern, replacement in self.style_patterns.items():
            if callable(replacement):
                adapted = re.sub(pattern, replacement, adapted)
            else:
                adapted = re.sub(pattern, replacement, adapted)
        
        return adapted