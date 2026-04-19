#!/usr/bin/env python3
"""
COMPREHENSIVE AUTOMATED TESTING SUITE
=========================================

This is a complete, self-contained testing system that will:
1. Test all 5 models across 12 different task categories
2. Generate detailed performance benchmarks
3. Create model-specific recommendation guides
4. Run continuously for stress testing
5. Generate comprehensive reports with visualizations
6. Save all results for later analysis

RUN WITH: python3 comprehensive_auto_test_suite.py

CONFIGURATION: Edit the CONFIG section below to customize testing
"""

import sys
import os
import requests
import json
import time
import asyncio
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import logging

# Add hermes to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hermes'))

# ============================================================================
# CONFIGURATION - CUSTOMIZE THESE VALUES
# ============================================================================

CONFIG = {
    # Test execution
    'test_iterations': 3,  # Number of times to test each model per task
    'continuous_mode': False,  # Keep testing indefinitely
    'continuous_interval': 300,  # Seconds between continuous tests

    # Timeouts
    'model_timeout': 60,  # Seconds to wait for model response
    'http_timeout': 10,  # Seconds for HTTP requests

    # Output
    'save_detailed_logs': True,
    'generate_visualizations': True,
    'create_json_reports': True,
    'print_progress': True,

    # Models to test
    'models': [
        'llama3.2:3b',
        'llama3.1:8b',
        'gemma3:latest',
        'qwen2.5-coder:7b',
        'deepseek-r1:8b'
    ],

    # Performance thresholds
    'max_acceptable_time': 30.0,  # Maximum seconds per response
    'min_acceptable_quality': 0.4,  # Minimum quality score

    # Logging
    'log_level': 'INFO',
    'log_file': 'comprehensive_test.log'
}

# ============================================================================
# COMPREHENSIVE TEST CATEGORIES
# ============================================================================

COMPREHENSIVE_TESTS = {
    'basic_response': {
        'prompt': 'Hello, how are you today?',
        'weight': 0.08,
        'category': 'basic',
        'description': 'Basic conversational response',
        'expected_length_range': (10, 200),
        'evaluation_criteria': ['coherent', 'appropriate_tone', 'grammar']
    },

    'quick_math': {
        'prompt': 'What is 17 × 23? Just give the number.',
        'weight': 0.10,
        'category': 'reasoning',
        'description': 'Quick mathematical reasoning',
        'expected_length_range': (1, 10),
        'evaluation_criteria': ['accuracy', 'conciseness'],
        'expected_answer': '391'
    },

    'simple_coding': {
        'prompt': '''Write a Python function that takes a list of numbers and returns the sum. Include proper docstring and type hints.''',
        'weight': 0.15,
        'category': 'coding',
        'description': 'Basic coding task',
        'expected_length_range': (50, 300),
        'evaluation_criteria': ['correct_syntax', 'functionality', 'docstring', 'type_hints']
    },

    'complex_coding': {
        'prompt': '''Write a Python class for a BankAccount with methods for deposit, withdraw, check_balance, and transaction history. Include proper error handling and logging.''',
        'weight': 0.12,
        'category': 'coding',
        'description': 'Complex coding with OOP',
        'expected_length_range': (150, 500),
        'evaluation_criteria': ['oop_concepts', 'error_handling', 'logging', 'completeness']
    },

    'logical_reasoning': {
        'prompt': '''A train leaves Chicago at 2:00 PM traveling at 60 mph. Another train leaves Chicago at 3:00 PM traveling at 80 mph in the same direction. How long will it take the second train to catch up to the first train? Show your work.''',
        'weight': 0.12,
        'category': 'reasoning',
        'description': 'Multi-step logical reasoning',
        'expected_length_range': (100, 400),
        'evaluation_criteria': ['logical_steps', 'math_accuracy', 'clarity', 'work_shown']
    },

    'creative_writing': {
        'prompt': '''Write a short story opening (2-3 paragraphs) about a librarian who discovers that books can talk to each other when no one is around. Include sensory details and character introduction.''',
        'weight': 0.08,
        'category': 'creative',
        'description': 'Creative writing task',
        'expected_length_range': (150, 400),
        'evaluation_criteria': ['creativity', 'sensory_details', 'character_development', 'paragraph_structure']
    },

    'technical_explanation': {
        'prompt': '''Explain what machine learning is to someone with no technical background. Use an analogy and avoid jargon. The explanation should be clear, engaging, and accurate.''',
        'weight': 0.10,
        'category': 'technical',
        'description': 'Technical explanation for beginners',
        'expected_length_range': (150, 400),
        'evaluation_criteria': ['clarity', 'analogy', 'accuracy', 'beginner_friendly']
    },

    'data_analysis': {
        'prompt': '''You have sales data for 5 products over 12 months. Product A: $1200/month avg, Product B: $800/month avg, Product C: $2500/month avg, Product D: $600/month avg, Product E: $1800/month avg. Analyze this data and provide 3 key business insights with specific recommendations.''',
        'weight': 0.10,
        'category': 'analysis',
        'description': 'Business data analysis',
        'expected_length_range': (200, 500),
        'evaluation_criteria': ['data_insights', 'business_recommendations', 'numerical_accuracy', 'actionable']
    },

    'problem_solving': {
        'prompt': '''You need to organize a project with 10 tasks that have these dependencies: Task 1 must be done before 2,3,4; Task 5 before 6,7; Task 2 before 8; Task 3 before 9; Task 8,9 before 10. Create an efficient project schedule and explain your reasoning.''',
        'weight': 0.08,
        'category': 'reasoning',
        'description': 'Complex problem solving',
        'expected_length_range': (200, 500),
        'evaluation_criteria': ['logical_organization', 'dependency_analysis', 'efficiency', 'clarity']
    },

    'emotional_intelligence': {
        'prompt': '''Your team member is clearly frustrated with a difficult project. They haven't said anything directly, but you can tell from their body language and tone. Write a supportive response that shows empathy and offers help without being patronizing.''',
        'weight': 0.07,
        'category': 'emotional',
        'description': 'Emotional intelligence and empathy',
        'expected_length_range': (100, 300),
        'evaluation_criteria': ['empathy', 'supportiveness', 'professional_tone', 'helpful']
    },

    'precision_following': {
        'prompt': '''Create a numbered list of exactly 7 benefits of regular exercise. Each item should be 1-2 sentences. Do not include any introduction or conclusion - just the numbered list.''',
        'weight': 0.05,
        'category': 'precision',
        'description': 'Precision and instruction following',
        'expected_length_range': (100, 250),
        'evaluation_criteria': ['exactly_7_items', 'numbered_format', 'no_extra_text', 'appropriate_length']
    },

    'summarization': {
        'prompt': '''Summarize this text in exactly 3 sentences: "The human brain contains approximately 86 billion neurons, each connected to thousands of other neurons through synapses. These connections form complex neural networks that enable thought, memory, and consciousness. The brain uses about 20% of the body's oxygen despite being only 2% of body weight. It can process information at speeds up to 120 meters per second and generates enough electricity to power a lightbulb. The brain remains plastic throughout life, allowing for learning and adaptation."''',
        'weight': 0.05,
        'category': 'comprehension',
        'description': 'Text summarization',
        'expected_length_range': (50, 150),
        'evaluation_criteria': ['exactly_3_sentences', 'key_points', 'accuracy', 'appropriate_length']
    }
}

# ============================================================================
# ADVANCED EVALUATION SYSTEM
# ============================================================================

class AdvancedEvaluator:
    """Advanced response evaluation with multiple metrics"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def evaluate_response(self, test_name: str, response: str, model: str,
                         test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive response evaluation"""
        evaluation = {
            'test_name': test_name,
            'model': model,
            'response': response,
            'timestamp': datetime.now().isoformat(),
            'metrics': {},
            'quality_score': 0.0,
            'issues': [],
            'strengths': [],
            'recommendations': []
        }

        try:
            # Basic metrics
            evaluation['metrics'] = self._calculate_basic_metrics(response)

            # Category-specific evaluation
            category_evaluations = {
                'basic': self._evaluate_basic_response,
                'reasoning': self._evaluate_reasoning,
                'coding': self._evaluate_coding,
                'creative': self._evaluate_creative,
                'technical': self._evaluate_technical,
                'analysis': self._evaluate_analysis,
                'emotional': self._evaluate_emotional,
                'precision': self._evaluate_precision,
                'comprehension': self._evaluate_comprehension
            }

            category = test_config.get('category', 'basic')
            if category in category_evaluations:
                category_result = category_evaluations[category](response, test_config)
                evaluation.update(category_result)

            # Calculate overall quality score
            evaluation['quality_score'] = self._calculate_overall_score(evaluation, test_config)

        except Exception as e:
            self.logger.error(f"Evaluation error for {test_name}: {e}")
            evaluation['issues'].append(f"Evaluation error: {str(e)}")
            evaluation['quality_score'] = 0.0

        return evaluation

    def _calculate_basic_metrics(self, response: str) -> Dict[str, Any]:
        """Calculate basic text metrics"""
        return {
            'length': len(response),
            'word_count': len(response.split()),
            'sentence_count': len([s.strip() for s in response.split('.') if s.strip()]),
            'paragraph_count': len([p.strip() for p in response.split('\n\n') if p.strip()]),
            'avg_word_length': statistics.mean([len(word) for word in response.split()]) if response.split() else 0,
            'complexity_score': self._calculate_complexity(response)
        }

    def _calculate_complexity(self, text: str) -> float:
        """Calculate text complexity score"""
        # Simple complexity based on vocabulary diversity and sentence structure
        words = text.lower().split()
        unique_words = set(words)

        # Vocabulary diversity
        vocab_diversity = len(unique_words) / len(words) if words else 0

        # Average sentence length
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        avg_sentence_length = statistics.mean([len(s.split()) for s in sentences]) if sentences else 0

        return (vocab_diversity + min(avg_sentence_length / 20, 1.0)) / 2

    def _evaluate_basic_response(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate basic conversational responses"""
        result = {'strengths': [], 'issues': []}

        # Check coherence
        if len(response) > 10:
            result['strengths'].append('coherent_response')
        else:
            result['issues'].append('too_short')

        # Check for appropriate tone
        if any(word in response.lower() for word in ['hello', 'hi', 'hey', 'good', 'well', 'great']):
            result['strengths'].append('friendly_tone')

        # Check grammar basics
        if response[0].isupper():
            result['strengths'].append('proper_capitalization')
        else:
            result['issues'].append('missing_capitalization')

        if response.endswith(('.', '!', '?')):
            result['strengths'].append('proper_punctuation')
        else:
            result['issues'].append('missing_punctuation')

        return result

    def _evaluate_reasoning(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate reasoning tasks"""
        result = {'strengths': [], 'issues': []}

        # For math problems
        if 'expected_answer' in test_config:
            expected = str(test_config['expected_answer'])
            if expected in response:
                result['strengths'].append('correct_answer')
            else:
                result['issues'].append('incorrect_answer')

        # Check for reasoning indicators
        reasoning_words = ['because', 'since', 'therefore', 'thus', 'first', 'then', 'finally', 'step']
        if any(word in response.lower() for word in reasoning_words):
            result['strengths'].append('shows_reasoning_process')
        else:
            result['issues'].append('lacks_reasoning_indicators')

        return result

    def _evaluate_coding(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate code generation"""
        result = {'strengths': [], 'issues': []}

        # Check for Python syntax elements
        if 'def ' in response:
            result['strengths'].append('has_function_definition')
        else:
            result['issues'].append('missing_function')

        if 'def ' in response and 'return' in response:
            result['strengths'].append('complete_function')
        else:
            result['issues'].append('incomplete_function')

        # Check for type hints
        if '->' in response or ': str' in response or ': int' in response:
            result['strengths'].append('includes_type_hints')

        # Check for docstring
        if '"""' in response or "'''" in response:
            result['strengths'].append('includes_docstring')

        return result

    def _evaluate_creative(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate creative writing"""
        result = {'strengths': [], 'issues': []}

        # Check for descriptive language
        descriptive_words = ['beautiful', 'mysterious', 'ancient', 'tiny', 'massive', 'whispered', 'shimmered', 'danced']
        if any(word in response.lower() for word in descriptive_words):
            result['strengths'].append('descriptive_language')

        # Check for dialogue
        if '"' in response or "'" in response:
            result['strengths'].append('includes_dialogue')

        # Check for sensory details
        senses = ['see', 'hear', 'smell', 'taste', 'feel', 'saw', 'heard', 'smelled', 'tasted', 'felt']
        if any(sense in response.lower() for sense in senses):
            result['strengths'].append('sensory_details')

        return result

    def _evaluate_technical(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate technical explanations"""
        result = {'strengths': [], 'issues': []}

        # Check for analogies
        analogy_indicators = ['like', 'similar to', 'compared to', 'as if', 'think of']
        if any(indicator in response.lower() for indicator in analogy_indicators):
            result['strengths'].append('uses_analogy')

        # Check for technical accuracy indicators
        tech_terms = ['API', 'REST', 'HTTP', 'request', 'response', 'server', 'client']
        tech_count = sum(1 for term in tech_terms if term.lower() in response.lower())
        if tech_count >= 3:
            result['strengths'].append('technically_accurate')

        # Check for simplicity
        if len(response) < 400 and not any(term.isupper() for term in tech_terms if term in response):
            result['strengths'].append('beginner_friendly')

        return result

    def _evaluate_analysis(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate analytical responses"""
        result = {'strengths': [], 'issues': []}

        # Check for data mentions
        if any(num in response for num in ['1200', '800', '2500', '600', '1800']):
            result['strengths'].append('references_data')

        # Check for insights
        insight_words = ['insight', 'observation', 'recommendation', 'suggest', 'indicates', 'shows']
        if any(word in response.lower() for word in insight_words):
            result['strengths'].append('provides_insights')

        # Check for recommendations
        if 'recommend' in response.lower() or 'suggest' in response.lower():
            result['strengths'].append('actionable_recommendations')

        return result

    def _evaluate_emotional(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate emotional intelligence responses"""
        result = {'strengths': [], 'issues': []}

        # Check for empathy indicators
        empathetic_words = ['understand', 'feel', 'relate', 'appreciate', 'validate', 'acknowledge']
        if any(word in response.lower() for word in empathetic_words):
            result['strengths'].append('shows_empathy')

        # Check for supportive language
        supportive_words = ['help', 'support', 'assist', 'guide', 'offer', 'provide']
        if any(word in response.lower() for word in supportive_words):
            result['strengths'].append('supportive_tone')

        # Check for professionalism
        professional_words = ['professional', 'appropriate', 'respectful', 'considerate']
        if any(word in response.lower() for word in professional_words):
            result['strengths'].append('professional_tone')

        return result

    def _evaluate_precision(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate precision and instruction following"""
        result = {'strengths': [], 'issues': []}

        # Count numbered items
        lines = response.split('\n')
        numbered_lines = []
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith(('1', '2', '3', '4', '5', '6', '7', '8', '9', '0') + '.'))):
                numbered_lines.append(line)

        expected_number = 7  # From the precision test
        if len(numbered_lines) == expected_number:
            result['strengths'].append(f'exactly_{expected_number}_items')
        else:
            result['issues'].append(f'got_{len(numbered_lines)}_items_instead_of_{expected_number}')

        # Check for extra text
        if len(numbered_lines) > 0 and len(response) < 500:  # Reasonable length
            result['strengths'].append('concise_no_extra_text')
        else:
            result['issues'].append('includes_extra_text')

        return result

    def _evaluate_comprehension(self, response: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate comprehension and summarization"""
        result = {'strengths'], [], 'issues': []}

        # Count sentences
        sentences = [s.strip() for s in response.split('.') if s.strip()]

        if len(sentences) == 3:
            result['strengths'].append('exactly_3_sentences')
        else:
            result['issues'].append(f'got_{len(sentences)}_sentences_instead_of_3')

        # Check for key information
        key_info = ['brain', 'neurons', 'synapses', 'oxygen', 'weight', 'speed', 'plasticity']
        mentioned = sum(1 for info in key_info if info in response.lower())
        if mentioned >= 4:
            result['strengths'].append('comprehensive_key_points')
        else:
            result['issues'].append('missing_key_information')

        # Check for accuracy indicators
        if '86 billion' in response or '86,000,000,000' in response:
            result['strengths'].append('accurate_numbers')

        return result

    def _calculate_overall_score(self, evaluation: Dict[str, Any],
                                test_config: Dict[str, Any]) -> float:
        """Calculate overall quality score"""
        base_score = 0.5  # Base score for attempting

        # Adjust based on strengths and issues
        strength_bonus = min(len(evaluation.get('strengths', [])) * 0.1, 0.5)
        issue_penalty = min(len(evaluation.get('issues', [])) * 0.15, 0.5)

        # Length appropriateness
        metrics = evaluation.get('metrics', {})
        expected_range = test_config.get('expected_length_range', (10, 500))
        length = metrics.get('length', 0)

        if expected_range[0] <= length <= expected_range[1]:
            length_score = 0.1
        else:
            length_score = -0.1

        overall_score = base_score + strength_bonus - issue_penalty + length_score
        return max(0, min(1.0, overall_score))

# ============================================================================
# COMPREHENSIVE TEST SUITE
# ============================================================================

class ComprehensiveTestSuite:
    """Comprehensive automated testing suite"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = self._setup_logging()
        self.evaluator = AdvancedEvaluator()
        self.results = {}
        self.test_session_id = datetime.now().strftime('%Y%m%d_%H%M%S')

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=getattr(logging, self.config['log_level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config['log_file']),
                logging.StreamHandler() if self.config['print_progress'] else logging.NullHandler()
            ]
        )
        return logging.getLogger(__name__)

    def query_model(self, model: str, prompt: str, iteration: int = 1) -> Dict[str, Any]:
        """Query a model with comprehensive error handling"""
        start_time = time.time()

        try:
            payload = {
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'num_predict': 1000,
                    'top_p': 0.9,
                    'top_k': 40
                }
            }

            response = requests.post(
                f'http://localhost:11434/api/generate',
                json=payload,
                timeout=self.config['model_timeout']
            )

            duration = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'model': model,
                    'iteration': iteration,
                    'response': result.get('response', ''),
                    'duration': duration,
                    'response_length': len(result.get('response', '')),
                    'prompt_tokens': len(prompt.split()),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'model': model,
                    'iteration': iteration,
                    'error': f"HTTP {response.status_code}",
                    'duration': duration,
                    'timestamp': datetime.now().isoformat()
                }

        except requests.Timeout:
            return {
                'success': False,
                'model': model,
                'iteration': iteration,
                'error': "Request timeout",
                'duration': time.time() - start_time,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'success': False,
                'model': model,
                'iteration': iteration,
                'error': str(e),
                'duration': time.time() - start_time,
                'timestamp': datetime.now().isoformat()
            }

    def run_single_test_iteration(self, model: str, test_name: str,
                                test_config: Dict[str, Any], iteration: int) -> Dict[str, Any]:
        """Run a single test iteration"""
        query_result = self.query_model(model, test_config['prompt'], iteration)

        if query_result['success']:
            # Evaluate the response
            evaluation = self.evaluator.evaluate_response(
                test_name, query_result['response'], model, test_config
            )

            evaluation.update(query_result)
            return evaluation
        else:
            return {
                'test_name': test_name,
                'model': model,
                'iteration': iteration,
                'success': False,
                'error': query_result['error'],
                'duration': query_result['duration'],
                'timestamp': query_result['timestamp']
            }

    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run comprehensive tests across all models and categories"""
        self.logger.info("Starting comprehensive test suite")
        self.logger.info(f"Models: {self.config['models']}")
        self.logger.info(f"Iterations: {self.config['test_iterations']}")
        self.logger.info(f"Test categories: {len(COMPREHENSIVE_TESTS)}")

        all_results = {}

        for model in self.config['models']:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Testing model: {model}")
            self.logger.info(f"{'='*60}")

            model_results = {
                'model': model,
                'test_categories': {},
                'performance_metrics': {},
                'iterations_completed': 0,
                'total_duration': 0,
                'success_rate': 0,
                'average_quality': 0
            }

            total_tests = len(COMPREHENSIVE_TESTS) * self.config['test_iterations']
            successful_tests = 0
            total_quality_score = 0

            for test_name, test_config in COMPREHENSIVE_TESTS.items():
                self.logger.info(f"  Running {test_config['description']}...")

                category_results = {
                    'config': test_config,
                    'iterations': [],
                    'metrics': {
                        'total_duration': 0,
                        'avg_duration': 0,
                        'min_duration': float('inf'),
                        'max_duration': 0,
                        'success_count': 0,
                        'avg_quality': 0,
                        'min_quality': 1.0,
                        'max_quality': 0,
                        'avg_response_length': 0
                    }
                }

                iteration_qualities = []

                for iteration in range(1, self.config['test_iterations'] + 1):
                    if self.config['print_progress']:
                        print(f"    Iteration {iteration}/{self.config['test_iterations']}...")

                    result = self.run_single_test_iteration(
                        model, test_name, test_config, iteration
                    )

                    category_results['iterations'].append(result)

                    if result['success']:
                        category_results['metrics']['success_count'] += 1
                        successful_tests += 1
                        total_quality_score += result.get('quality_score', 0)
                        iteration_qualities.append(result.get('quality_score', 0))

                    category_results['metrics']['total_duration'] += result['duration']
                    category_results['metrics']['avg_duration'] = (
                        category_results['metrics']['total_duration'] / iteration
                    )
                    category_results['metrics']['min_duration'] = min(
                        category_results['metrics']['min_duration'], result['duration']
                    )
                    category_results['metrics']['max_duration'] = max(
                        category_results['metrics']['max_duration'], result['duration']
                    )

                    # Check for performance issues
                    if result['duration'] > self.config['max_acceptable_time']:
                        self.logger.warning(
                            f"Slow response from {model} on {test_name}: {result['duration']:.2f}s"
                        )

                # Calculate category averages
                if category_results['metrics']['success_count'] > 0:
                    category_results['metrics']['avg_quality'] = (
                        sum(iteration_qualities) / len(iteration_qualities)
                    )
                    category_results['metrics']['min_quality'] = min(iteration_qualities)
                    category_results['metrics']['max_quality'] = max(iteration_qualities)

                if category_results['iterations']:
                    response_lengths = [
                        r['response_length'] for r in category_results['iterations']
                        if r.get('success') and 'response_length' in r
                    ]
                    if response_lengths:
                        category_results['metrics']['avg_response_length'] = statistics.mean(response_lengths)

                model_results['test_categories'][test_name] = category_results
                model_results['total_duration'] += category_results['metrics']['total_duration']
                model_results['iterations_completed'] += len(category_results['iterations'])

            # Calculate overall model metrics
            model_results['success_rate'] = successful_tests / total_tests
            model_results['average_quality'] = total_quality_score / successful_tests if successful_tests > 0 else 0

            # Calculate additional performance metrics
            all_durations = []
            all_qualities = []
            all_lengths = []

            for category_data in model_results['test_categories'].values():
                for iteration in category_data['iterations']:
                    if iteration.get('success'):
                        all_durations.append(iteration['duration'])
                        all_qualities.append(iteration.get('quality_score', 0))
                        all_lengths.append(iteration.get('response_length', 0))

            if all_durations:
                model_results['performance_metrics'] = {
                    'avg_duration': statistics.mean(all_durations),
                    'min_duration': min(all_durations),
                    'max_duration': max(all_durations),
                    'duration_std': statistics.stdev(all_durations) if len(all_durations) > 1 else 0,
                    'avg_quality': statistics.mean(all_qualities),
                    'min_quality': min(all_qualities),
                    'max_quality': max(all_qualities),
                    'quality_std': statistics.stdev(all_qualities) if len(all_qualities) > 1 else 0,
                    'avg_response_length': statistics.mean(all_lengths),
                    'total_tokens': sum(r.get('prompt_tokens', 0) for r in [
                        iteration for category in model_results['test_categories'].values()
                        for iteration in category['iterations']
                    ])
                }

            all_results[model] = model_results
            self.logger.info(f"  Completed: {model_results['success_rate']:.1%} success rate")
            self.logger.info(f"  Average Quality: {model_results['average_quality']:.3f}")
            self.logger.info(f"  Total Time: {model_results['total_duration']:.1f}s")

        self.results['models'] = all_results
        self.results['session_info'] = {
            'session_id': self.test_session_id,
            'start_time': datetime.now().isoformat(),
            'config': self.config,
            'test_categories': list(COMPREHENSIVE_TESTS.keys()),
            'models_tested': self.config['models']
        }

        return all_results

    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report"""
        self.logger.info("Generating comprehensive analysis report...")

        report = {
            'session_info': self.results['session_info'],
            'executive_summary': self._generate_executive_summary(),
            'detailed_analysis': self._generate_detailed_analysis(),
            'model_rankings': self._generate_model_rankings(),
            'task_recommendations': self._generate_task_recommendations(),
            'performance_analysis': self._generate_performance_analysis(),
            'quality_analysis': self._generate_quality_analysis(),
            'recommendations': self._generate_actionable_recommendations()
        }

        return report

    def _generate_executive_summary(self) -> Dict[str, Any]:
        """Generate executive summary"""
        models = self.results['models']

        total_tests = 0
        total_successful = 0
        total_duration = 0
        total_quality = 0

        for model_data in models.values():
            tests_per_model = len(model_data['test_categories']) * self.config['test_iterations']
            total_tests += tests_per_model
            total_successful += tests_per_model * model_data['success_rate']
            total_duration += model_data['total_duration']
            total_quality += tests_per_model * model_data['average_quality']

        return {
            'total_models_tested': len(models),
            'total_tests_run': total_tests,
            'overall_success_rate': total_successful / total_tests if total_tests > 0 else 0,
            'overall_average_quality': total_quality / total_successful if total_successful > 0 else 0,
            'total_test_duration': total_duration,
            'average_time_per_test': total_duration / total_tests if total_tests > 0 else 0,
            'test_efficiency': 'High' if total_tests / total_duration > 1 else 'Medium' if total_tests / total_duration > 0.5 else 'Low'
        }

    def _generate_detailed_analysis(self) -> Dict[str, Any]:
        """Generate detailed analysis by model and category"""
        analysis = {
            'by_model': {},
            'by_category': {},
            'performance_benchmarks': {},
            'quality_benchmarks': {}
        }

        # Analysis by model
        for model_name, model_data in self.results['models'].items():
            analysis['by_model'][model_name] = {
                'overall_performance': {
                    'success_rate': model_data['success_rate'],
                    'average_quality': model_data['average_quality'],
                    'total_duration': model_data['total_duration'],
                    'iterations_completed': model_data['iterations_completed']
                },
                'category_performance': {},
                'best_categories': [],
                'worst_categories': []
            }

            # Find best and worst categories
            category_scores = []
            for category_name, category_data in model_data['test_categories'].items():
                if category_data['metrics']['success_count'] > 0:
                    score = category_data['metrics']['avg_quality']
                    category_scores.append((category_name, score, category_data['config']['description']))

            if category_scores:
                category_scores.sort(key=lambda x: x[1], reverse=True)

                # Top 3 best categories
                for i, (cat, score, desc) in enumerate(category_scores[:3]):
                    analysis['by_model'][model_name]['best_categories'].append({
                        'category': cat,
                        'score': score,
                        'description': desc
                    })

                # Bottom 2 worst categories
                for cat, score, desc in category_scores[-2:]:
                    analysis['by_model'][model_name]['worst_categories'].append({
                        'category': cat,
                        'score': score,
                        'description': desc,
                        'recommendation': 'Consider using this model for other tasks'
                    })

                # All category details
                for category_name, category_data in model_data['test_categories'].items():
                    analysis['by_model'][model_name]['category_performance'][category_name] = {
                        'success_rate': category_data['metrics']['success_count'] / self.config['test_iterations'],
                        'avg_quality': category_data['metrics']['avg_quality'],
                        'avg_duration': category_data['metrics']['avg_duration'],
                        'avg_response_length': category_data['metrics']['avg_response_length']
                    }

        return analysis

    def _generate_model_rankings(self) -> Dict[str, Any]:
        """Generate overall model rankings"""
        models = self.results['models']

        rankings = []
        for model_name, model_data in models.items():
            # Calculate composite score (weighted average of quality and success rate)
            quality_score = model_data['average_quality']
            success_score = model_data['success_rate']

            # Weight quality slightly more than success
            composite_score = (quality_score * 0.6) + (success_score * 0.4)

            # Consider speed (faster is better but not critical)
            if 'performance_metrics' in model_data:
                avg_duration = model_data['performance_metrics']['avg_duration']
                speed_score = 1.0 / (1 + avg_duration / 10)  # Normalize around 10 seconds
                final_score = (composite_score * 0.8) + (speed_score * 0.2)
            else:
                final_score = composite_score

            rankings.append({
                'model': model_name,
                'overall_score': final_score,
                'quality_score': quality_score,
                'success_rate': success_score,
                'total_duration': model_data['total_duration'],
                'rank': 0  # Will be set after sorting
            })

        # Sort by overall score
        rankings.sort(key=lambda x: x['overall_score'], reverse=True)

        # Assign ranks
        for i, ranking in enumerate(rankings, 1):
            ranking['rank'] = i

        return {
            'rankings': rankings,
            'summary': {
                'best_model': rankings[0]['model'],
                'best_score': rankings[0]['overall_score'],
                'worst_model': rankings[-1]['model'],
                'score_range': rankings[0]['overall_score'] - rankings[-1]['overall_score']
            }
        }

    def _generate_task_recommendations(self) -> Dict[str, Any]:
        """Generate task-specific recommendations"""
        recommendations = {}

        # Find best model for each test category
        for test_name, test_config in COMPREHENSIVE_TESTS.items():
            best_model = None
            best_score = -1
            best_duration = float('inf')

            for model_name, model_data in self.results['models'].items():
                if test_name in model_data['test_categories']:
                    category_data = model_data['test_categories'][test_name]

                    if category_data['metrics']['success_count'] > 0:
                        quality = category_data['metrics']['avg_quality']
                        duration = category_data['metrics']['avg_duration']

                        # Consider both quality and speed
                        composite_score = quality * 0.7 + (1.0 / (1 + duration / 10)) * 0.3

                        if composite_score > best_score:
                            best_score = composite_score
                            best_model = model_name
                            best_duration = duration

            if best_model:
                confidence_level = 'High' if best_score >= 0.8 else 'Medium' if best_score >= 0.6 else 'Low'

                recommendations[test_name] = {
                    'task_description': test_config['description'],
                    'best_model': best_model,
                    'quality_score': best_score,
                    'avg_duration': best_duration,
                    'confidence_level': confidence_level,
                    'weight': test_config['weight'],
                    'recommendation': f"Use {best_model} for {test_config['description'].lower()} - Quality: {best_score:.3f}, Time: {best_duration:.1f}s"
                }

        return recommendations

    def _generate_performance_analysis(self) -> Dict[str, Any]:
        """Generate detailed performance analysis"""
        performance_data = []

        for model_name, model_data in self.results['models'].items():
            if 'performance_metrics' in model_data:
                metrics = model_data['performance_metrics']
                performance_data.append({
                    'model': model_name,
                    'avg_duration': metrics['avg_duration'],
                    'min_duration': metrics['min_duration'],
                    'max_duration': metrics['max_duration'],
                    'duration_std': metrics['duration_std'],
                    'tokens_per_second': metrics.get('total_tokens', 0) / metrics['total_duration'] if metrics['total_duration'] > 0 else 0
                })

        if performance_data:
            # Sort by speed
            performance_data.sort(key=lambda x: x['avg_duration'])

            fastest = performance_data[0]
            slowest = performance_data[-1]

            # Calculate statistics
            all_durations = [p['avg_duration'] for p in performance_data]
            avg_duration = statistics.mean(all_durations)
            duration_std = statistics.stdev(all_durations) if len(all_durations) > 1 else 0

            return {
                'rankings': {
                    'fastest': {
                        'model': fastest['model'],
                        'time': fastest['avg_duration'],
                        'tokens_per_second': fastest['tokens_per_second']
                    },
                    'slowest': {
                        'model': slowest['model'],
                        'time': slowest['avg_duration'],
                        'tokens_per_second': slowest['tokens_per_second']
                    }
                },
                'statistics': {
                    'average_duration': avg_duration,
                    'duration_std': duration_std,
                    'duration_range': slowest['avg_duration'] - fastest['avg_duration'],
                    'speed_variance': duration_std / avg_duration if avg_duration > 0 else 0
                },
                'detailed_data': performance_data
            }

        return {'error': 'No performance data available'}

    def _generate_quality_analysis(self) -> Dict[str, Any]:
        """Generate quality analysis across models and categories"""
        quality_data = []

        for model_name, model_data in self.results['models'].items():
            for test_name, category_data in model_data['test_categories'].items():
                if category_data['metrics']['success_count'] > 0:
                    quality_data.append({
                        'model': model_name,
                        'test_category': test_name,
                        'quality_score': category_data['metrics']['avg_quality'],
                        'min_quality': category_data['metrics']['min_quality'],
                        'max_quality': category_data['metrics']['max_quality'],
                        'response_length': category_data['metrics']['avg_response_length']
                    })

        if quality_data:
            # Find best and worst performances
            best_performance = max(quality_data, key=lambda x: x['quality_score'])
            worst_performance = min(quality_data, key=lambda x: x['quality_score'])

            # Calculate statistics
            all_scores = [q['quality_score'] for q in quality_data]
            avg_quality = statistics.mean(all_scores)
            quality_std = statistics.stdev(all_scores) if len(all_scores) > 1 else 0

            return {
                'best_performance': {
                    'model': best_performance['model'],
                    'test_category': best_performance['test_category'],
                    'quality_score': best_performance['quality_score'],
                    'details': f"Best quality in {best_performance['test_category']}"
                },
                'worst_performance': {
                    'model': worst_performance['model'],
                    'test_category': worst_performance['test_category'],
                    'quality_score': worst_performance['quality_score'],
                    'details': f"Lowest quality in {worst_performance['test_category']}"
                },
                'statistics': {
                    'average_quality': avg_quality,
                    'quality_std': quality_std',
                    'quality_range': best_performance['quality_score'] - worst_performance['quality_score'],
                    'quality_variance': quality_std / avg_quality if avg_quality > 0 else 0
                },
                'detailed_data': quality_data
            }

        return {'error': 'No quality data available'}

    def _generate_actionable_recommendations(self) -> Dict[str, Any]:
        """Generate actionable recommendations"""
        recommendations = {
            'for_improvement': [],
            'for_optimization': [],
            'for_deployment': [],
            'for_model_selection': []
        }

        # Model selection recommendations
        rankings = self._generate_model_rankings()

        if rankings['rankings']:
            best_overall = rankings['rankings'][0]

            recommendations['for_model_selection'].append({
                'priority': 'High',
                'recommendation': f"Use {best_overall['model']} for general-purpose tasks",
                'reasoning': f"Highest overall score ({best_overall['overall_score']:.3f}) with good balance of quality and speed",
                'score_breakdown': f"Quality: {best_overall['quality_score']:.3f}, Success: {best_overall['success_rate']:.3f}"
            })

            # Fast model for quick tasks
            if len(rankings['rankings']) >= 2:
                fastest = min(rankings['rankings'], key=lambda x: x['total_duration'])
                recommendations['for_model_selection'].append({
                    'priority': 'Medium',
                    'recommendation': f"Use {fastest['model']} for quick responses",
                    'reasoning': f"Fastest average response time ({fastest['total_duration']:.2f}s)",
                    'best_for': 'Quick queries, simple tasks, when speed is prioritized'
                })

            # High quality model for important tasks
            highest_quality = max(rankings['rankings'], key=lambda x: x['quality_score'])
            if highest_quality['model'] != best_overall['model']:
                recommendations['for_model_selection'].append({
                    'priority': 'Medium',
                    'recommendation': f"Use {highest_quality['model']} for critical tasks",
                    'reasoning': f"Highest quality score ({highest_quality['quality_score']:.3f})",
                    'best_for': 'Important queries, detailed analysis, when accuracy is crucial'
                })

        # Task recommendations
        task_recommendations = self._generate_task_recommendations()

        for test_name, rec in task_recommendations.items():
            if rec['confidence_level'] == 'High':
                recommendations['for_optimization'].append({
                    'priority': 'High',
                    'task': rec['task_description'],
                    'recommendation': rec['recommendation'],
                    'model': rec['best_model'],
                    'expected_performance': f"Quality: {rec['quality_score']:.3f}, Time: {rec['avg_duration']:.1f}s"
                })

        # Performance recommendations
        performance = self._generate_performance_analysis()
        if 'rankings' in performance and 'slowest' in performance['rankings']:
            slow_model = performance['rankings']['slowest']['model']
            slow_time = performance['rankings']['slowest']['time']

            if slow_time > 15:
                recommendations['for_optimization'].append({
                    'priority': 'Medium',
                    'recommendation': f"Consider optimizing {slow_model} or using faster alternatives",
                    'reasoning': f"Average response time of {slow_time:.2f}s may be too slow for interactive use"
                })

        return recommendations

    def save_reports(self, report: Dict[str, Any]) -> None:
        """Save all reports to files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if self.config['create_json_reports']:
            # Main comprehensive report
            with open(f'test_report_{self.test_session_id}.json', 'w') as f:
                json.dump(report, f, indent=2, default=str)

            # Raw results
            with open(f'raw_results_{self.test_session_id}.json', 'w') as f:
                json.dump(self.results, f, indent=2, default=str)

            # Analysis-only report
            with open(f'analysis_report_{self.test_session_id}.json', 'w') as f:
                json.dump({
                    'timestamp': timestamp,
                    'executive_summary': report['executive_summary'],
                    'model_rankings': report['model_rankings'],
                    'task_recommendations': report['task_recommendations'],
                    'performance_analysis': report['performance_analysis'],
                    'quality_analysis': report['quality_analysis'],
                    'recommendations': report['recommendations']
                }, f, indent=2, default=str)

        if self.config['save_detailed_logs']:
            # Create summary text report
            self._create_text_report(report, timestamp)

        self.logger.info(f"Reports saved with session ID: {self.test_session_id}")

    def _create_text_report(self, report: Dict[str, Any], timestamp: str) -> None:
        """Create human-readable text report"""
        filename = f'test_summary_{self.test_session_id}.txt'

        with open(filename, 'w') as f:
            f.write("HERMES AI ASSISTANT - COMPREHENSIVE TEST REPORT\n")
            f.write("=" * 60 + "\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Session ID: {self.test_session_id}\n\n")

            # Executive Summary
            f.write("EXECUTIVE SUMMARY\n")
            f.write("-" * 20 + "\n")
            exec_summary = report['executive_summary']
            f.write(f"Models Tested: {exec_summary['total_models_tested']}\n")
            f.write(f"Total Tests: {exec_summary['total_tests_run']}\n")
            f.write(f"Success Rate: {exec_summary['overall_success_rate']:.1%}\n")
            f.write(f"Average Quality: {exec_summary['overall_average_quality']:.3f}\n")
            f.write(f"Total Duration: {exec_summary['total_test_duration']:.1f}s\n")
            f.write(f"Test Efficiency: {exec_summary['test_efficiency']}\n\n")

            # Model Rankings
            f.write("MODEL RANKINGS\n")
            f.write("-" * 20 + "\n")
            for ranking in report['model_rankings']['rankings']:
                f.write(f"{ranking['rank']}. {ranking['model']}\n")
                f.write(f"   Overall Score: {ranking['overall_score']:.3f}\n")
                f.write(f"   Quality Score: {ranking['quality_score']:.3f}\n")
                f.write(f"   Success Rate: {ranking['success_rate']:.1%}\n")
                f.write(f"   Total Time: {ranking['total_duration']:.1f}s\n\n")

            # Task Recommendations
            f.write("TASK-SPECIFIC RECOMMENDATIONS\n")
            f.write("-" * 30 + "\n")

            # Sort by weight (most important first)
            weighted_tasks = [(name, data) for name, data in report['task_recommendations'].items()]
            weighted_tasks.sort(key=lambda x: x[1]['weight'], reverse=True)

            for task_name, task_data in weighted_tasks:
                f.write(f"• {task_data['task_description']}\n")
                f.write(f"  Best Model: {task_data['best_model']}\n")
                f.write(f"  Quality Score: {task_data['quality_score']:.3f}\n")
                f.write(f"  Avg Time: {task_data['avg_duration']:.1f}s\n")
                f.write(f"  Confidence: {task_data['confidence_level']}\n")
                f.write(f"  {task_data['recommendation']}\n\n")

        self.logger.info(f"Text report saved: {filename}")

    async def run_continuous_tests(self):
        """Run tests continuously"""
        cycle_count = 0

        while self.config['continuous_mode']:
            cycle_count += 1
            self.logger.info(f"Starting test cycle #{cycle_count}")

            # Run comprehensive tests
            results = self.run_comprehensive_tests()

            # Generate and save reports
            report = self.generate_comprehensive_report(results)
            self.save_reports(report)

            # Log cycle summary
            exec_summary = report['executive_summary']
            self.logger.info(f"Cycle #{cycle_count} completed:")
            self.logger.info(f"  Success Rate: {exec_summary['overall_success_rate']:.1%}")
            self.logger.info(f"  Average Quality: {exec_summary['overall_average_quality']:.3f}")
            self.logger.info(f"  Total Duration: {exec_summary['total_test_duration']:.1f}s")

            # Wait before next cycle
            if self.config['continuous_mode']:
                self.logger.info(f"Waiting {self.config['continuous_interval']}s before next cycle...")
                await asyncio.sleep(self.config['continuous_interval'])

def main():
    """Main execution function"""
    print("🚀 COMPREHENSIVE AUTOMATED TESTING SUITE")
    print("=" * 80)
    print("Starting comprehensive model characterization testing...")
    print("This will run automatically and generate detailed reports.\n")

    # Create test suite
    test_suite = ComprehensiveTestSuite(CONFIG)

    # Run initial comprehensive tests
    print("Running comprehensive test suite...")
    results = test_suite.run_comprehensive_tests()

    # Generate comprehensive report
    print("\n" + "=" * 80)
    print("GENERATING COMPREHENSIVE REPORTS...")
    report = test_suite.generate_comprehensive_report(results)

    # Save all reports
    print("Saving detailed reports...")
    test_suite.save_reports(report)

    # Print summary
    exec_summary = report['executive_summary']
    rankings = report['model_rankings']

    print("\n" + "=" * 80)
    print("🎯 EXECUTIVE SUMMARY")
    print("=" * 80)
    print(f"✅ Models Tested: {exec_summary['total_models_tested']}")
    print(f"✅ Total Tests: {exec_summary['total_tests_run']}")
    print(f"✅ Success Rate: {exec_summary['overall_success_rate']:.1%}")
    print(f"✅ Average Quality: {exec_summary['overall_average_quality']:.3f}")
    print(f"✅ Total Time: {exec_summary['total_test_duration']:.1f}s")
    print(f"✅ Test Efficiency: {exec_summary['test_efficiency']}")

    print(f"\n🏆 TOP PERFORMING MODEL:")
    print(f"   {rankings['summary']['best_model']} (Score: {rankings['summary']['best_score']:.3f})")

    print(f"\n⚡ FASTEST MODEL:")
    if 'performance_analysis' in report and 'rankings' in report['performance_analysis']:
        fastest = report['performance_analysis']['rankings']['fastest']['model']
        print(f"   {fastest} for quick responses")

    print(f"\n🧠 HIGHEST QUALITY:")
    if 'quality_analysis' in report and 'best_performance' in report['quality_analysis']:
        best_quality = report['quality_analysis']['best_performance']['model']
        print(f"   {best_quality} for critical tasks")

    print(f"\n📊 BEST MODELS FOR SPECIFIC TASKS:")
    top_tasks = sorted(report['task_recommendations'].items(),
                       key=lambda x: x[1]['weight'], reverse=True)[:5]
    for task_name, task_data in top_tasks:
        print(f"   • {task_data['task_description']}")
        print(f"     → {task_data['best_model']} (Quality: {task_data['quality_score']:.3f})")

    print(f"\n📁 Reports Generated:")
    print(f"   • test_report_{test_suite.test_session_id}.json (Comprehensive)")
    print(f"   • analysis_report_{test_suite.test_session_id}.json (Analysis Only)")
    print(f"   • raw_results_{test_suite.test_session_id}.json (Raw Data)")
    print(f"   • test_summary_{test_suite.test_session_id}.txt (Human Readable)")

    print(f"\n💾 All reports saved with session ID: {test_suite.test_session_id}")

    # Check if continuous mode is enabled
    if CONFIG['continuous_mode']:
        print(f"\n🔄 CONTINUOUS MODE ENABLED")
        print(f"   Will run tests every {CONFIG['continuous_interval']}s")
        print(f"   Press Ctrl+C to stop\n")

        # Run continuous tests
        asyncio.run(test_suite.run_continuous_tests())
    else:
        print(f"\n✅ Testing completed successfully!")
        print(f"   Reports are available for review")

    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)