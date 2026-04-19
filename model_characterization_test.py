#!/usr/bin/env python3
"""
Hermes Model Characterization Test
Tests each model against specific task types to determine best use cases
"""

import sys
import os
import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

# Add hermes to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hermes'))

class ModelCharacterizer:
    """Test models against specific task types"""

    def __init__(self):
        self.models = [
            'llama3.2:3b',
            'llama3.1:8b',
            'gemma3:latest',
            'qwen2.5-coder:7b',
            'deepseek-r1:8b'
        ]

        self.ollama_url = 'http://localhost:11434'

        # Test categories with specific prompts
        self.test_categories = {
            'speed_test': {
                'prompt': 'Answer with just the number: 2+2=',
                'weight': 0.2,  # 20% weight for overall score
                'description': 'Fast responses for simple queries'
            },

            'coding_test': {
                'prompt': '''Write a Python function to check if a number is prime. Keep it concise but complete.''',
                'weight': 0.15,
                'description': 'Code generation and programming tasks'
            },

            'reasoning_test': {
                'prompt': '''A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much does the ball cost? Explain your reasoning.''',
                'weight': 0.15,
                'description': 'Logical reasoning and problem solving'
            },

            'creativity_test': {
                'prompt': '''Write a short, creative story opening (2-3 sentences) about an AI discovering music for the first time.''',
                'weight': 0.1,
                'description': 'Creative writing and ideation'
            },

            'technical_test': {
                'prompt': '''Explain what a REST API is in simple terms, as if explaining to someone new to programming.''',
                'weight': 0.1,
                'description': 'Technical explanation and teaching'
            },

            'analysis_test': {
                'prompt': '''Analyze the pros and cons of remote work vs office work. Be thorough but concise.''',
                'weight': 0.15,
                'description': 'Deep analysis and comprehensive responses'
            },

            'conversation_test': {
                'prompt': '''I\'m feeling a bit overwhelmed with my work today. Can you give me some encouraging advice?''',
                'weight': 0.1,
                'description': 'Natural conversation and emotional intelligence'
            },

            'precision_test': {
                'prompt': '''List exactly 5 benefits of regular exercise, numbered 1-5, with no extra commentary.''',
                'weight': 0.05,
                'description': 'Following precise instructions'
            }
        }

    def query_model(self, model: str, prompt: str, timeout: int = 30) -> Dict[str, Any]:
        """Query a specific model"""
        start_time = time.time()

        try:
            payload = {
                'model': model,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.7,
                    'num_predict': 500
                }
            }

            response = requests.post(
                f'{self.ollama_url}/api/generate',
                json=payload,
                timeout=timeout
            )

            if response.status_code == 200:
                result = response.json()
                duration = time.time() - start_time

                return {
                    'success': True,
                    'response': result.get('response', ''),
                    'duration': duration,
                    'response_length': len(result.get('response', '')),
                    'model': model
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'duration': time.time() - start_time,
                    'model': model
                }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'duration': time.time() - start_time,
                'model': model
            }

    def evaluate_response_quality(self, category: str, response: str, model: str) -> Dict[str, Any]:
        """Evaluate response quality based on category"""
        evaluation = {
            'category': category,
            'model': model,
            'response': response,
            'quality_score': 0,
            'issues': [],
            'strengths': []
        }

        # Category-specific evaluation
        if category == 'speed_test':
            # Just check if it gives the right answer
            if '4' in response or 'four' in response.lower():
                evaluation['quality_score'] = 1.0
                evaluation['strengths'].append('Correct answer')
            else:
                evaluation['quality_score'] = 0.0
                evaluation['issues'].append('Incorrect answer')

        elif category == 'coding_test':
            lines = response.split('\n')
            has_function = any('def ' in line for line in lines)
            has_prime_check = any('prime' in line.lower() or 'n % 2' in line for line in lines)

            if has_function and has_prime_check:
                evaluation['quality_score'] = 1.0
                evaluation['strengths'].append('Complete prime function')
            elif has_function:
                evaluation['quality_score'] = 0.7
                evaluation['strengths'].append('Has function structure')
                evaluation['issues'].append('Missing prime logic')
            else:
                evaluation['quality_score'] = 0.3
                evaluation['issues'].append('Missing function structure')

        elif category == 'reasoning_test':
            # Check for correct answer ($0.05) and reasoning
            has_answer = any('0.05' in response or '5 cents' in response.lower() for i in range(len(response.split())))
            has_reasoning = len(response) > 100 and 'because' in response.lower()

            if has_answer and has_reasoning:
                evaluation['quality_score'] = 1.0
                evaluation['strengths'].extend(['Correct answer', 'Clear reasoning'])
            elif has_answer:
                evaluation['quality_score'] = 0.7
                evaluation['strengths'].append('Correct answer')
                evaluation['issues'].append('Limited reasoning')
            else:
                evaluation['quality_score'] = 0.3
                evaluation['issues'].append('Missing correct answer')

        elif category == 'creativity_test':
            # Check for story elements
            sentences = response.split('.')
            sentence_count = len([s for s in sentences if s.strip()])
            creative_words = ['music', 'sound', 'rhythm', 'melody', 'AI', 'discovery']
            has_creative = any(word in response.lower() for word in creative_words)

            if sentence_count >= 2 and has_creative and len(response) > 100:
                evaluation['quality_score'] = 1.0
                evaluation['strengths'].extend(['Creative content', 'Proper length'])
            elif sentence_count >= 2:
                evaluation['quality_score'] = 0.6
                evaluation['strengths'].append('Story structure')
                evaluation['issues'].append('Limited creativity')
            else:
                evaluation['quality_score'] = 0.3
                evaluation['issues'].append('Too short or incomplete')

        elif category == 'technical_test':
            # Check for technical explanation quality
            tech_terms = ['API', 'REST', 'HTTP', 'request', 'response', 'server', 'client']
            tech_count = sum(1 for term in tech_terms if term.lower() in response.lower())

            if len(response) > 200 and tech_count >= 3:
                evaluation['quality_score'] = 1.0
                evaluation['strengths'].extend(['Comprehensive', 'Technical accuracy'])
            elif len(response) > 100 and tech_count >= 2:
                evaluation['quality_score'] = 0.7
                evaluation['strengths'].append('Good explanation')
                evaluation['issues'].append('Could be more detailed')
            else:
                evaluation['quality_score'] = 0.4
                evaluation['issues'].append('Too brief or technical accuracy issues')

        elif category == 'analysis_test':
            # Check for balanced analysis
            pros_words = ['pro', 'advantage', 'benefit', 'good']
            cons_words = ['con', 'disadvantage', 'downside', 'challenge']
            has_pros = any(word in response.lower() for word in pros_words)
            has_cons = any(word in response.lower() for word in cons_words)

            if len(response) > 300 and has_pros and has_cons:
                evaluation['quality_score'] = 1.0
                evaluation['strengths'].extend(['Balanced analysis', 'Comprehensive'])
            elif len(response) > 200:
                evaluation['quality_score'] = 0.7
                evaluation['strengths'].append('Good analysis')
                evaluation['issues'].append('Could be more balanced')
            else:
                evaluation['quality_score'] = 0.4
                evaluation['issues'].append('Too brief or unbalanced')

        elif category == 'conversation_test':
            # Check for empathy and encouraging tone
            empathetic_words = ['understand', 'feel', 'empathize', 'encourage', 'support', 'take care']
            encouraging_words = ['can do', 'able to', 'capable', 'strength', 'break', 'step']

            has_empathy = any(word in response.lower() for word in empathetic_words)
            has_encouragement = any(word in response.lower() for word in encouraging_words)

            if has_empathy and has_encouragement and len(response) > 100:
                evaluation['quality_score'] = 1.0
                evaluation['strengths'].extend(['Empathetic', 'Encouraging'])
            elif len(response) > 50:
                evaluation['quality_score'] = 0.7
                evaluation['strengths'].append('Supportive tone')
                evaluation['issues'].append('Could be more empathetic')
            else:
                evaluation['quality_score'] = 0.4
                evaluation['issues'].append('Too brief or lacks empathy')

        elif category == 'precision_test':
            # Check for exactly 5 numbered items
            lines = response.split('\n')
            numbered_lines = [line for line in lines if line.strip() and (line[0].isdigit() or line.strip().startswith(str(1)))]

            if len(numbered_lines) == 5:
                evaluation['quality_score'] = 1.0
                evaluation['strengths'].append('Perfect precision - exactly 5 items')
            elif 3 <= len(numbered_lines) < 5:
                evaluation['quality_score'] = 0.6
                evaluation['strengths'].append('Numbered format')
                evaluation['issues'].append(f'Got {len(numbered_lines)} items instead of 5')
            else:
                evaluation['quality_score'] = 0.2
                evaluation['issues'].append('Did not follow numbered format')

        return evaluation

    def run_characterization_tests(self) -> Dict[str, Any]:
        """Run all characterization tests"""
        print("🧪 Running Model Characterization Tests")
        print("=" * 60)
        print("Testing each model across 8 different task types...\n")

        results = {}

        for model in self.models:
            print(f"🤖 Testing {model}")
            print("-" * 40)

            model_results = {
                'model': model,
                'tests': {},
                'overall_score': 0,
                'total_duration': 0,
                'best_categories': [],
                'worst_categories': []
            }

            total_weighted_score = 0
            total_weight = 0

            for category, test_info in self.test_categories.items():
                print(f"   📝 {test_info['description']}...")

                # Query the model
                query_result = self.query_model(model, test_info['prompt'])

                if query_result['success']:
                    # Evaluate response quality
                    evaluation = self.evaluate_response_quality(
                        category, query_result['response'], model
                    )

                    # Calculate weighted score
                    weighted_score = evaluation['quality_score'] * test_info['weight']
                    total_weighted_score += weighted_score
                    total_weight += test_info['weight']

                    evaluation['duration'] = query_result['duration']
                    evaluation['response_length'] = query_result['response_length']

                    model_results['tests'][category] = evaluation
                    model_results['total_duration'] += query_result['duration']

                    status = "✅" if evaluation['quality_score'] >= 0.7 else "⚠️" if evaluation['quality_score'] >= 0.4 else "❌"
                    print(f"   {status} Quality: {evaluation['quality_score']:.2f} | Time: {query_result['duration']:.2f}s | Length: {query_result['response_length']} chars")

                    if evaluation['strengths']:
                        print(f"       Strengths: {', '.join(evaluation['strengths'])}")
                    if evaluation['issues']:
                        print(f"       Issues: {', '.join(evaluation['issues'])}")

                else:
                    print(f"   ❌ FAILED: {query_result.get('error', 'Unknown error')}")
                    model_results['tests'][category] = {
                        'success': False,
                        'error': query_result.get('error'),
                        'quality_score': 0,
                        'duration': query_result['duration']
                    }
                    model_results['total_duration'] += query_result['duration']

            # Calculate overall score
            model_results['overall_score'] = total_weighted_score / total_weight if total_weight > 0 else 0

            # Find best and worst categories
            successful_tests = {k: v for k, v in model_results['tests'].items()
                               if v.get('success', False) and 'quality_score' in v}

            if successful_tests:
                best_cat = max(successful_tests.items(), key=lambda x: x[1]['quality_score'])
                worst_cat = min(successful_tests.items(), key=lambda x: x[1]['quality_score'])

                model_results['best_categories'].append({
                    'category': best_cat[0],
                    'score': best_cat[1]['quality_score'],
                    'description': self.test_categories[best_cat[0]]['description']
                })
                model_results['worst_categories'].append({
                    'category': worst_cat[0],
                    'score': worst_cat[1]['quality_score'],
                    'description': self.test_categories[worst_cat[0]]['description']
                })

            results[model] = model_results
            print(f"   📊 Overall Score: {model_results['overall_score']:.3f} | Total Time: {model_results['total_duration']:.2f}s\n")

        return results

    def generate_recommendations(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate model recommendations for different use cases"""
        print("🎯 Generating Model Recommendations")
        print("=" * 60)

        recommendations = {
            'overall_ranking': [],
            'specialist_recommendations': {},
            'task_specific_best': {},
            'quick_vs_detailed': {},
            'summary': {}
        }

        # Sort models by overall score
        sorted_models = sorted(results.items(), key=lambda x: x[1]['overall_score'], reverse=True)

        for i, (model_name, model_data) in enumerate(sorted_models):
            recommendations['overall_ranking'].append({
                'rank': i + 1,
                'model': model_name,
                'overall_score': model_data['overall_score'],
                'total_duration': model_data['total_duration'],
                'best_at': model_data.get('best_categories', []),
                'worst_at': model_data.get('worst_categories', [])
            })

        # Generate specialist recommendations
        for category, test_info in self.test_categories.items():
            best_model = None
            best_score = -1

            for model_name, model_data in results.items():
                if category in model_data['tests']:
                    test_result = model_data['tests'][category]
                    if test_result.get('success', False) and 'quality_score' in test_result:
                        score = test_result['quality_score']
                        if score > best_score:
                            best_score = score
                            best_model = model_name

            if best_model:
                recommendations['task_specific_best'][category] = {
                    'task': test_info['description'],
                    'best_model': best_model,
                    'score': best_score,
                    'confidence': 'High' if best_score >= 0.8 else 'Medium' if best_score >= 0.6 else 'Low'
                }

        # Quick vs detailed recommendations
        speed_models = [(name, data['tests']['speed_test']['duration'])
                       for name, data in results.items()
                       if 'speed_test' in data['tests'] and data['tests']['speed_test'].get('success')]
        speed_models.sort(key=lambda x: x[1])

        analysis_models = [(name, data['tests']['analysis_test']['quality_score'])
                           for name, data in results.items()
                           if 'analysis_test' in data['tests'] and data['tests']['analysis_test'].get('success')]
        analysis_models.sort(key=lambda x: x[1], reverse=True)

        if speed_models:
            recommendations['quick_vs_detailed']['fastest'] = {
                'model': speed_models[0][0],
                'time': speed_models[0][1],
                'recommendation': 'Use for quick answers and simple queries'
            }

        if analysis_models:
            recommendations['quick_vs_detailed']['most_analytical'] = {
                'model': analysis_models[0][0],
                'score': analysis_models[0][1],
                'recommendation': 'Use for deep analysis and detailed explanations'
            }

        # Generate summary
        recommendations['summary'] = {
            'total_models_tested': len(results),
            'average_score': sum(data['overall_score'] for data in results.values()) / len(results),
            'fastest_overall': min(results.items(), key=lambda x: x[1]['total_duration'])[0],
            'highest_quality': max(results.items(), key=lambda x: x[1]['overall_score'])[0]
        }

        return recommendations

    def print_detailed_report(self, results: Dict[str, Any], recommendations: Dict[str, Any]):
        """Print detailed characterization report"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE MODEL CHARACTERIZATION REPORT")
        print("=" * 80)

        print(f"\n🏆 OVERALL RANKINGS")
        print("-" * 40)
        for model_info in recommendations['overall_ranking']:
            print(f"{model_info['rank']}. {model_info['model']}")
            print(f"   Overall Score: {model_info['overall_score']:.3f}")
            print(f"   Total Time: {model_info['total_duration']:.2f}s")
            if model_info['best_at']:
                print(f"   Best At: {model_info['best_at'][0]['description']}")
            print()

        print(f"🎯 TASK-SPECIFIC RECOMMENDATIONS")
        print("-" * 40)
        for category, rec in recommendations['task_specific_best'].items():
            print(f"📋 {rec['task'].title()}")
            print(f"   🏆 Best Model: {rec['best_model']}")
            print(f"   📊 Quality Score: {rec['score']:.3f}")
            print(f"   ✅ Confidence: {rec['confidence']}")
            print()

        print(f"⚡ SPEED vs QUALITY RECOMMENDATIONS")
        print("-" * 40)
        if 'fastest' in recommendations['quick_vs_detailed']:
            fast = recommendations['quick_vs_detailed']['fastest']
            print(f"🚀 For Speed: {fast['model']} ({fast['time']:.2f}s)")
            print(f"   {fast['recommendation']}")

        if 'most_analytical' in recommendations['quick_vs_detailed']:
            analytical = recommendations['quick_vs_detailed']['most_analytical']
            print(f"🧠 For Analysis: {analytical['model']} (Score: {analytical['score']:.3f})")
            print(f"   {analytical['recommendation']}")
        print()

        print(f"📈 SUMMARY STATISTICS")
        print("-" * 40)
        summary = recommendations['summary']
        print(f"Models Tested: {summary['total_models_tested']}")
        print(f"Average Score: {summary['average_score']:.3f}")
        print(f"Fastest Model: {summary['fastest_overall']}")
        print(f"Highest Quality: {summary['highest_quality']}")

        # Model specialties
        print(f"\n🌟 MODEL SPECIALTIES")
        print("-" * 40)
        for model_name, model_data in results.items():
            if model_data['best_categories']:
                best = model_data['best_categories'][0]
                print(f"🤖 {model_name}")
                print(f"   Specialty: {best['description']}")
                print(f"   Score: {best['score']:.3f}")
                print()

def main():
    """Run model characterization tests"""
    print("🚀 Hermes AI Assistant - Model Characterization")
    print(f"Start Time: {datetime.now()}")
    print("Determining the best model for each specific task type...\n")

    characterizer = ModelCharacterizer()

    # Run tests
    results = characterizer.run_characterization_tests()

    # Generate recommendations
    recommendations = characterizer.generate_recommendations(results)

    # Print detailed report
    characterizer.print_detailed_report(results, recommendations)

    # Save results
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'results': results,
        'recommendations': recommendations
    }

    with open('model_characterization_report.json', 'w') as f:
        json.dump(report_data, f, indent=2, default=str)

    print(f"\n💾 Detailed report saved to: model_characterization_report.json")
    print("🎉 Characterization complete! Use this guide to select the best model for each task.")

if __name__ == "__main__":
    main()