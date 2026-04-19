#!/usr/bin/env python3
"""
Strategic Model Optimizer Suite
Provides actionable intelligence for model selection across specific tasks
Designed for autonomous execution and comprehensive reporting
"""

import sys
import os
import requests
import json
import time
import asyncio
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import concurrent.futures
import sqlite3
import hashlib

# Add hermes to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hermes'))

@dataclass
class ModelPerformance:
    """Comprehensive model performance metrics"""
    model_name: str
    task_category: str
    success_rate: float  # 0-100%
    avg_response_time: float  # seconds
    avg_quality_score: float  # 0-100
    avg_tokens_per_second: float
    reliability_score: float  # consistency across runs
    resource_efficiency: float  # memory/cpu usage proxy
    total_tests: int
    last_updated: datetime

    def get_overall_score(self) -> float:
        """Calculate weighted overall score"""
        weights = {
            'success_rate': 0.3,
            'response_time': 0.25,  # inverted - lower is better
            'quality_score': 0.3,
            'reliability': 0.15
        }

        # Invert response time score (lower time = higher score)
        time_score = max(0, 100 - (self.avg_response_time * 10))

        return (
            self.success_rate * weights['success_rate'] +
            time_score * weights['response_time'] +
            self.avg_quality_score * weights['quality_score'] +
            self.reliability_score * weights['reliability']
        )

@dataclass
class TaskCategory:
    """Definition of a task category for testing"""
    name: str
    description: str
    test_prompts: List[str]
    evaluation_criteria: List[str]
    weight: float = 1.0

class ModelOptimizerSuite:
    """Strategic testing suite for model optimization"""

    def __init__(self):
        self.models = [
            'llama3.2:3b',
            'llama3.1:8b',
            'gemma3:latest',
            'qwen2.5-coder:7b',
            'deepseek-r1:8b'
        ]

        self.task_categories = self._define_task_categories()
        self.results: Dict[str, List[ModelPerformance]] = {}
        self.db_path = 'model_performance.db'
        self.base_url = 'http://localhost:11434/api/generate'

        # Initialize database
        self._init_database()

        print("🧠 Model Optimizer Suite Initialized")
        print(f"   Testing {len(self.models)} models across {len(self.task_categories)} task categories")

    def _define_task_categories(self) -> List[TaskCategory]:
        """Define real-world task categories for characterization"""
        return [
            TaskCategory(
                name="quick_qa",
                description="Quick questions and factual answers",
                test_prompts=[
                    "What is the capital of France?",
                    "Who wrote Romeo and Juliet?",
                    "What year did World War II end?",
                    "What is photosynthesis?",
                    "Define 'artificial intelligence'"
                ],
                evaluation_criteria=["accuracy", "conciseness", "speed"],
                weight=1.2
            ),

            TaskCategory(
                name="code_generation",
                description="Writing code snippets and functions",
                test_prompts=[
                    "Write a Python function to reverse a string",
                    "Create a JavaScript function to validate email",
                    "Write a simple REST API endpoint in Python",
                    "Generate a SQL query to find users over 18",
                    "Create a React component for a button"
                ],
                evaluation_criteria=["correctness", "readability", "efficiency"],
                weight=1.5
            ),

            TaskCategory(
                name="creative_writing",
                description="Creative content generation",
                test_prompts=[
                    "Write a short story about a lost robot",
                    "Create a product slogan for eco-friendly water bottles",
                    "Write a poem about technology and nature",
                    "Create a social media post about coffee",
                    "Write a brief product description for wireless headphones"
                ],
                evaluation_criteria=["creativity", "clarity", "engagement"],
                weight=1.0
            ),

            TaskCategory(
                name="analysis_reasoning",
                description="Complex problem-solving and analysis",
                test_prompts=[
                    "Analyze the pros and cons of remote work",
                    "Explain blockchain technology simply",
                    "Compare renewable energy sources",
                    "Solve this logic puzzle: There are three boxes...",
                    "Explain the impact of AI on job markets"
                ],
                evaluation_criteria=["depth", "logic", "structure"],
                weight=1.8
            ),

            TaskCategory(
                name="summarization",
                description="Condensing and extracting key information",
                test_prompts=[
                    "Summarize the benefits of exercise in 3 points",
                    "What are the main features of Python?",
                    "Explain climate change in simple terms",
                    "List 5 key principles of good UX design",
                    "What makes a good team leader?"
                ],
                evaluation_criteria=["accuracy", "completeness", "brevity"],
                weight=1.3
            ),

            TaskCategory(
                name="conversation",
                description="Natural conversation and interaction",
                test_prompts=[
                    "How are you doing today?",
                    "Can you help me learn Python?",
                    "What do you think about AI ethics?",
                    "Tell me something interesting",
                    "How can I improve my productivity?"
                ],
                evaluation_criteria=["naturalness", "helpfulness", "engagement"],
                weight=1.0
            ),

            TaskCategory(
                name="data_processing",
                description="Working with structured data and formats",
                test_prompts=[
                    "Convert this to JSON: name: John, age: 30, city: NYC",
                    "Create a CSV structure for student grades",
                    "Format this data as a table: Product A - $10, Product B - $20",
                    "Generate a YAML configuration for a web server",
                    "Create a list of 5 programming languages with their paradigms"
                ],
                evaluation_criteria=["accuracy", "formatting", "completeness"],
                weight=1.4
            ),

            TaskCategory(
                name="debugging",
                description="Error analysis and problem-solving",
                test_prompts=[
                    "Fix this Python error: 'list index out of range'",
                    "Why is my CSS not applying to this element?",
                    "Debug this SQL query that returns no results",
                    "Find the issue in this JavaScript function",
                    "Troubleshoot: Python script runs but produces no output"
                ],
                evaluation_criteria=["accuracy", "explanation", "solution_quality"],
                weight=1.6
            )
        ]

    def _init_database(self):
        """Initialize SQLite database for storing results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT,
                task_category TEXT,
                success_rate REAL,
                avg_response_time REAL,
                avg_quality_score REAL,
                avg_tokens_per_second REAL,
                reliability_score REAL,
                resource_efficiency REAL,
                total_tests INTEGER,
                overall_score REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_model_task ON model_performance(model_name, task_category)
        ''')

        conn.commit()
        conn.close()

    def _test_model_single_query(self, model: str, prompt: str) -> Tuple[bool, float, str]:
        """Test a single model query"""
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
                self.base_url,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                duration = time.time() - start_time

                success = len(response_text) > 10
                return success, duration, response_text
            else:
                return False, time.time() - start_time, ""

        except Exception as e:
            return False, time.time() - start_time, ""

    def _evaluate_response_quality(self, prompt: str, response: str, task_category: str) -> float:
        """Evaluate response quality on a scale of 0-100"""
        if not response or len(response) < 10:
            return 0.0

        score = 50.0  # Base score for responding

        # Length scoring
        if len(response) > 50:
            score += 10
        if len(response) > 200:
            score += 10

        # Category-specific scoring
        if task_category == "quick_qa":
            # Check for direct answers
            if any(indicator in response.lower() for indicator in ["is", "are", "was", "were", "capital", "author", "year"]):
                score += 20
        elif task_category == "code_generation":
            # Check for code elements
            code_indicators = ["def ", "function", "class ", "import", "SELECT", "const", "let", "var"]
            if any(indicator in response for indicator in code_indicators):
                score += 25
        elif task_category == "data_processing":
            # Check for structured data formats
            format_indicators = ["json", "csv", "yaml", "xml", "{", "[", "|", "-"]
            if any(indicator in response.lower() for indicator in format_indicators):
                score += 25

        # Penalize very short responses
        if len(response) < 30:
            score -= 20

        # Penalize very long responses for quick tasks
        if task_category in ["quick_qa", "conversation"] and len(response) > 500:
            score -= 15

        return min(100.0, max(0.0, score))

    def _test_model_category(self, model: str, category: TaskCategory) -> ModelPerformance:
        """Test a model across a specific task category"""
        print(f"   Testing {model} on {category.name}...")

        results = []
        response_times = []
        quality_scores = []

        for i, prompt in enumerate(category.test_prompts):
            print(f"     Test {i+1}/{len(category.test_prompts)}: {prompt[:30]}...")

            success, duration, response_text = self._test_model_single_query(model, prompt)

            if success:
                quality_score = self._evaluate_response_quality(prompt, response_text, category.name)
                tokens_per_second = len(response_text.split()) / duration if duration > 0 else 0

                results.append({
                    'success': True,
                    'duration': duration,
                    'quality_score': quality_score,
                    'tokens_per_second': tokens_per_second,
                    'response_length': len(response_text)
                })

                response_times.append(duration)
                quality_scores.append(quality_score)
            else:
                results.append({
                    'success': False,
                    'duration': duration,
                    'quality_score': 0,
                    'tokens_per_second': 0,
                    'response_length': 0
                })

            time.sleep(0.5)  # Rate limiting

        # Calculate metrics
        successful_tests = [r for r in results if r['success']]
        success_rate = (len(successful_tests) / len(results)) * 100 if results else 0

        avg_response_time = statistics.mean(response_times) if response_times else 0
        avg_quality_score = statistics.mean(quality_scores) if quality_scores else 0
        avg_tokens_per_second = statistics.mean([r['tokens_per_second'] for r in successful_tests]) if successful_tests else 0

        # Calculate reliability (consistency of quality scores)
        reliability_score = 0
        if len(quality_scores) > 1:
            std_dev = statistics.stdev(quality_scores)
            reliability_score = max(0, 100 - (std_dev * 2))  # Lower std dev = higher reliability

        # Resource efficiency (inverse of average response time)
        resource_efficiency = max(0, 100 - (avg_response_time * 5))

        return ModelPerformance(
            model_name=model,
            task_category=category.name,
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            avg_quality_score=avg_quality_score,
            avg_tokens_per_second=avg_tokens_per_second,
            reliability_score=reliability_score,
            resource_efficiency=resource_efficiency,
            total_tests=len(results),
            last_updated=datetime.now()
        )

    def run_comprehensive_analysis(self) -> Dict:
        """Run comprehensive model analysis"""
        print("\n🚀 Starting Comprehensive Model Analysis")
        print("=" * 60)
        print(f"Models: {', '.join(self.models)}")
        print(f"Task Categories: {len(self.task_categories)}")
        print(f"Total Tests: {len(self.models) * sum(len(cat.test_prompts) for cat in self.task_categories)}")
        print()

        all_performances = []

        for category in self.task_categories:
            print(f"📋 Category: {category.name.upper()} - {category.description}")
            print(f"   Weight: {category.weight}, Tests: {len(category.test_prompts)}")
            print()

            category_performances = []

            for model in self.models:
                performance = self._test_model_category(model, category)
                category_performances.append(performance)
                all_performances.append(performance)

                # Save to database
                self._save_performance_to_db(performance)

            # Sort by overall score
            category_performances.sort(key=lambda x: x.get_overall_score(), reverse=True)

            print(f"   🏆 Results for {category.name}:")
            for i, perf in enumerate(category_performances, 1):
                print(f"      {i}. {perf.model_name}: {perf.get_overall_score():.1f}/100 "
                      f"(Quality: {perf.avg_quality_score:.1f}, Speed: {perf.avg_response_time:.2f}s)")
            print()

        # Generate comprehensive recommendations
        recommendations = self._generate_recommendations(all_performances)

        return {
            'performances': all_performances,
            'recommendations': recommendations,
            'summary': self._create_summary(all_performances)
        }

    def _generate_recommendations(self, performances: List[ModelPerformance]) -> Dict:
        """Generate actionable recommendations based on performance data"""
        recommendations = {
            'task_specific': {},
            'overall_rankings': {},
            'optimization_suggestions': []
        }

        # Group performances by task category
        task_groups = {}
        for perf in performances:
            if perf.task_category not in task_groups:
                task_groups[perf.task_category] = []
            task_groups[perf.task_category].append(perf)

        # Generate task-specific recommendations
        for task_name, task_perfs in task_groups.items():
            task_perfs.sort(key=lambda x: x.get_overall_score(), reverse=True)

            best = task_perfs[0]
            fastest = min(task_perfs, key=lambda x: x.avg_response_time)
            most_reliable = max(task_perfs, key=lambda x: x.reliability_score)

            recommendations['task_specific'][task_name] = {
                'best_overall': {
                    'model': best.model_name,
                    'score': best.get_overall_score(),
                    'reason': f"Highest overall score ({best.get_overall_score():.1f}/100)"
                },
                'fastest': {
                    'model': fastest.model_name,
                    'time': fastest.avg_response_time,
                    'reason': f"Fastest response time ({fastest.avg_response_time:.2f}s)"
                },
                'most_reliable': {
                    'model': most_reliable.model_name,
                    'reliability': most_reliable.reliability_score,
                    'reason': f"Most consistent quality ({most_reliable.reliability_score:.1f}/100)"
                }
            }

        # Generate overall rankings
        model_scores = {}
        for perf in performances:
            if perf.model_name not in model_scores:
                model_scores[perf.model_name] = []
            model_scores[perf.model_name].append(perf.get_overall_score())

        avg_scores = {model: statistics.mean(scores) for model, scores in model_scores.items()}
        sorted_models = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)

        recommendations['overall_rankings'] = {
            'by_average_score': [
                {'model': model, 'avg_score': score}
                for model, score in sorted_models
            ]
        }

        # Generate optimization suggestions
        top_model = sorted_models[0][0]
        fastest_model = min(performances, key=lambda x: x.avg_response_time).model_name
        most_reliable_model = max(performances, key=lambda x: x.reliability_score).model_name

        suggestions = [
            f"Use {top_model} for general-purpose tasks (highest overall performance)",
            f"Use {fastest_model} for quick interactions and real-time responses",
            f"Use {most_reliable_model} for critical applications requiring consistency"
        ]

        # Task-specific suggestions
        for task_name, recs in recommendations['task_specific'].items():
            best_model = recs['best_overall']['model']
            suggestions.append(f"Use {best_model} for {task_name.replace('_', ' ')} tasks")

        recommendations['optimization_suggestions'] = suggestions

        return recommendations

    def _create_summary(self, performances: List[ModelPerformance]) -> Dict:
        """Create executive summary of analysis"""
        total_tests = sum(p.total_tests for p in performances)
        avg_success_rate = statistics.mean([p.success_rate for p in performances])
        avg_response_time = statistics.mean([p.avg_response_time for p in performances])
        avg_quality_score = statistics.mean([p.avg_quality_score for p in performances])

        model_counts = {}
        for p in performances:
            model_counts[p.model_name] = model_counts.get(p.model_name, 0) + 1

        return {
            'total_tests_run': total_tests,
            'models_tested': len(model_counts),
            'task_categories': len(set(p.task_category for p in performances)),
            'average_success_rate': avg_success_rate,
            'average_response_time': avg_response_time,
            'average_quality_score': avg_quality_score,
            'analysis_duration': datetime.now().isoformat(),
            'recommendation_summary': self._get_top_recommendations(performances)
        }

    def _get_top_recommendations(self, performances: List[ModelPerformance]) -> str:
        """Get top-line recommendations"""
        # Find best overall model
        model_scores = {}
        for p in performances:
            if p.model_name not in model_scores:
                model_scores[p.model_name] = []
            model_scores[p.model_name].append(p.get_overall_score())

        avg_scores = {model: statistics.mean(scores) for model, scores in model_scores.items()}
        best_model = max(avg_scores.items(), key=lambda x: x[1])

        # Find fastest model
        avg_times = {}
        for p in performances:
            if p.model_name not in avg_times:
                avg_times[p.model_name] = []
            avg_times[p.model_name].append(p.avg_response_time)

        avg_time_scores = {model: statistics.mean(times) for model, times in avg_times.items()}
        fastest_model = min(avg_time_scores.items(), key=lambda x: x[1])

        return f"Best Overall: {best_model[0]} ({best_model[1]:.1f}/100), Fastest: {fastest_model[0]} ({fastest_model[1]:.2f}s avg)"

    def _save_performance_to_db(self, performance: ModelPerformance):
        """Save performance data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO model_performance (
                model_name, task_category, success_rate, avg_response_time,
                avg_quality_score, avg_tokens_per_second, reliability_score,
                resource_efficiency, total_tests, overall_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            performance.model_name,
            performance.task_category,
            performance.success_rate,
            performance.avg_response_time,
            performance.avg_quality_score,
            performance.avg_tokens_per_second,
            performance.reliability_score,
            performance.resource_efficiency,
            performance.total_tests,
            performance.get_overall_score()
        ))

        conn.commit()
        conn.close()

    def generate_report(self, analysis_results: Dict) -> str:
        """Generate comprehensive analysis report"""
        report = []
        report.append("# 🧠 Model Optimization Analysis Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Executive Summary
        summary = analysis_results['summary']
        report.append("## 📊 Executive Summary")
        report.append(f"- **Models Tested**: {summary['models_tested']}")
        report.append(f"- **Task Categories**: {summary['task_categories']}")
        report.append(f"- **Total Tests**: {summary['total_tests_run']}")
        report.append(f"- **Average Success Rate**: {summary['average_success_rate']:.1f}%")
        report.append(f"- **Average Response Time**: {summary['average_response_time']:.2f}s")
        report.append(f"- **Average Quality Score**: {summary['average_quality_score']:.1f}/100")
        report.append(f"- **Top Recommendation**: {summary['recommendation_summary']}")
        report.append("")

        # Task-Specific Recommendations
        report.append("## 🎯 Task-Specific Recommendations")
        recommendations = analysis_results['recommendations']

        for task, recs in recommendations['task_specific'].items():
            report.append(f"### {task.replace('_', ' ').title()}")
            report.append(f"- **Best Overall**: {recs['best_overall']['model']} ({recs['best_overall']['score']:.1f}/100)")
            report.append(f"- **Fastest**: {recs['fastest']['model']} ({recs['fastest']['time']:.2f}s)")
            report.append(f"- **Most Reliable**: {recs['most_reliable']['model']} ({recs['most_reliable']['reliability']:.1f}/100)")
            report.append("")

        # Overall Rankings
        report.append("## 🏆 Overall Model Rankings")
        for i, model_data in enumerate(recommendations['overall_rankings']['by_average_score'], 1):
            model = model_data['model']
            score = model_data['score']
            report.append(f"{i}. **{model}**: {score:.1f}/100")
        report.append("")

        # Optimization Suggestions
        report.append("## 💡 Optimization Suggestions")
        for suggestion in recommendations['optimization_suggestions']:
            report.append(f"- {suggestion}")
        report.append("")

        return "\n".join(report)

    def run_automated_analysis(self, iterations: int = 1, continuous: bool = False) -> str:
        """Run automated analysis with optional continuous mode"""
        print("🤖 Starting Automated Model Analysis")

        all_reports = []

        for iteration in range(iterations):
            print(f"\n🔄 Iteration {iteration + 1}/{iterations}")
            print("=" * 50)

            # Run analysis
            analysis_results = self.run_comprehensive_analysis()

            # Generate report
            report = self.generate_report(analysis_results)

            # Save report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"model_analysis_report_{timestamp}.md"

            with open(report_file, 'w') as f:
                f.write(report)

            all_reports.append(report_file)
            print(f"\n📄 Report saved: {report_file}")

            # Print key findings
            print("\n🎯 Key Findings:")
            recommendations = analysis_results['recommendations']
            for suggestion in recommendations['optimization_suggestions'][:3]:
                print(f"   • {suggestion}")

            if continuous and iteration < iterations - 1:
                print(f"\n⏳ Waiting 30 seconds before next iteration...")
                time.sleep(30)

        print(f"\n✅ Analysis complete! Reports generated: {', '.join(all_reports)}")
        return all_reports[0] if all_reports else None

def main():
    """Main execution function"""
    optimizer = ModelOptimizerSuite()

    print("🚀 Model Optimizer Suite - Running Quick Analysis")
    print("This will test all 5 models across 8 task categories")
    print("Estimated time: 15-20 minutes")
    print()

    try:
        # Run quick analysis automatically
        for category in optimizer.task_categories:
            category.test_prompts = category.test_prompts[:2]  # Only first 2 prompts for speed

        report_file = optimizer.run_automated_analysis(iterations=1)

        if report_file:
            print(f"\n🎉 Analysis complete! View report: {report_file}")
            return 0
        else:
            print("❌ Analysis failed")
            return 1

    except KeyboardInterrupt:
        print("\n⏹️  Analysis interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)