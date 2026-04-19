#!/usr/bin/env python3
"""
Cost-Optimization Model Testing Suite
Comprehensive testing for local vs cloud model cost-performance analysis
Autonomous execution with detailed cost analysis and optimization recommendations
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
from decimal import Decimal, ROUND_HALF_UP

# Add hermes to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hermes'))

@dataclass
class CostMetrics:
    """Detailed cost metrics for models"""
    model_name: str
    model_id: str
    input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    context_limit: int
    provider: str
    is_free: bool

@dataclass
class TestCostData:
    """Token and cost data from actual tests"""
    input_tokens: int
    output_tokens: int
    total_cost: Decimal
    cost_per_test: Decimal
    tokens_per_dollar: Decimal

@dataclass
class CloudModelPerformance:
    """Cloud model performance with cost analysis"""
    model_name: str
    model_id: str
    task_category: str
    success_rate: float
    avg_response_time: float
    avg_quality_score: float
    cost_data: TestCostData
    cost_effectiveness_score: float  # quality per dollar
    provider: str
    context_limit: int

class CostOptimizationTester:
    """Comprehensive cost-performance testing for local vs cloud models"""

    def __init__(self):
        self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        self.base_url = 'https://openrouter.ai/api/v1/chat/completions'
        self.ollama_url = 'http://localhost:11434/api/generate'

        # Cost data for all models
        self.cost_metrics = self._initialize_cost_metrics()

        # Task categories (same as before)
        self.task_categories = self._define_task_categories()

        # Results storage
        self.cloud_results: List[CloudModelPerformance] = []
        self.local_results = {}  # Load from previous test

        # Database for cost analysis
        self.db_path = 'cost_optimization_results.db'
        self._init_database()

        print("💰 Cost-Optimization Tester Initialized")
        print(f"   Testing {len(self.cost_metrics)} cloud models")
        print(f"   Task Categories: {len(self.task_categories)}")
        print(f"   Cost Analysis: Full token-level tracking")

    def _initialize_cost_metrics(self) -> List[CostMetrics]:
        """Initialize cost metrics for all models including local ones"""
        return [
            # Cloud Models - Free Tier
            CostMetrics("DeepSeek R1T2 Chimera", "tngtech/deepseek-r1t2-chimera:free",
                       Decimal('0.00'), Decimal('0.00'), 163840, "TNG", True),
            CostMetrics("DeepSeek R1T Chimera", "tngtech/deepseek-r1t-chimera:free",
                       Decimal('0.00'), Decimal('0.00'), 163840, "TNG", True),
            CostMetrics("GLM 4.5 Air", "z-ai/glm-4.5-air:free",
                       Decimal('0.00'), Decimal('0.00'), 131072, "Z.AI", True),
            CostMetrics("MiniMax M2", "minimax/minimax-m2:free",
                       Decimal('0.00'), Decimal('0.00'), 204800, "MiniMax", True),

            # Cloud Models - Budget Tier
            CostMetrics("Mistral Nemo", "mistralai/mistral-nemo",
                       Decimal('0.02'), Decimal('0.04'), 131072, "Mistral", False),
            CostMetrics("GPT-oss-20b", "openai/gpt-oss-20b",
                       Decimal('0.03'), Decimal('0.14'), 131072, "OpenAI", False),
            CostMetrics("Gemma 3 12B", "google/gemma-3-12b-it",
                       Decimal('0.03'), Decimal('0.10'), 131072, "Google", False),
            CostMetrics("GPT-5 Nano", "openai/gpt-5-nano",
                       Decimal('0.05'), Decimal('0.40'), 400000, "OpenAI", False),
            CostMetrics("GPT-oss-120b", "openai/gpt-oss-120b",
                       Decimal('0.04'), Decimal('0.40'), 131072, "OpenAI", False),
            CostMetrics("Qwen3 235B", "qwen/qwen3-235b-a22b-2507",
                       Decimal('0.08'), Decimal('0.55'), 262144, "Qwen", False),
            CostMetrics("Gemma 3 27B", "google/gemma-3-27b-it",
                       Decimal('0.09'), Decimal('0.16'), 131072, "Google", False),
            CostMetrics("Gemini 2.0 Flash Lite", "google/gemini-2.0-flash-lite-001",
                       Decimal('0.075'), Decimal('0.30'), 1048576, "Google", False),
            CostMetrics("Mistral Small 3.2", "mistralai/mistral-small-3.2-24b-instruct",
                       Decimal('0.06'), Decimal('0.18'), 131072, "Mistral", False),
            CostMetrics("Qwen3 Next 80B", "qwen/qwen3-next-80b-a3b-instruct",
                       Decimal('0.10'), Decimal('0.80'), 262144, "Qwen", False),

            # Cloud Models - Performance Tier
            CostMetrics("Gemini 2.0 Flash", "google/gemini-2.0-flash-001",
                       Decimal('0.10'), Decimal('0.40'), 1048576, "Google", False),
            CostMetrics("Gemini 2.5 Flash Lite", "google/gemini-2.5-flash-lite",
                       Decimal('0.10'), Decimal('0.40'), 1048576, "Google", False),
            CostMetrics("Gemini 2.5 Flash Lite Preview", "google/gemini-2.5-flash-lite-preview-09-2025",
                       Decimal('0.10'), Decimal('0.40'), 1048576, "Google", False),
        ]

    def _define_task_categories(self) -> List[Dict]:
        """Define task categories with prompts for token counting"""
        return [
            {
                'name': 'quick_qa',
                'description': 'Quick questions and factual answers',
                'prompts': [
                    "What is the capital of France?",
                    "Who wrote Romeo and Juliet?",
                    "What year did World War II end?",
                    "What is photosynthesis?",
                    "Define 'artificial intelligence'"
                ]
            },
            {
                'name': 'code_generation',
                'description': 'Writing code snippets and functions',
                'prompts': [
                    "Write a Python function to reverse a string",
                    "Create a JavaScript function to validate email",
                    "Write a simple REST API endpoint in Python",
                    "Generate a SQL query to find users over 18",
                    "Create a React component for a button"
                ]
            },
            {
                'name': 'creative_writing',
                'description': 'Creative content generation',
                'prompts': [
                    "Write a short story about a lost robot",
                    "Create a product slogan for eco-friendly water bottles",
                    "Write a poem about technology and nature",
                    "Create a social media post about coffee",
                    "Write a brief product description for wireless headphones"
                ]
            },
            {
                'name': 'analysis_reasoning',
                'description': 'Complex problem-solving and analysis',
                'prompts': [
                    "Analyze the pros and cons of remote work",
                    "Explain blockchain technology simply",
                    "Compare renewable energy sources",
                    "Solve this logic puzzle: There are three boxes...",
                    "Explain the impact of AI on job markets"
                ]
            },
            {
                'name': 'summarization',
                'description': 'Condensing and extracting key information',
                'prompts': [
                    "Summarize the benefits of exercise in 3 points",
                    "What are the main features of Python?",
                    "Explain climate change in simple terms",
                    "List 5 key principles of good UX design",
                    "What makes a good team leader?"
                ]
            },
            {
                'name': 'conversation',
                'description': 'Natural conversation and interaction',
                'prompts': [
                    "How are you doing today?",
                    "Can you help me learn Python?",
                    "What do you think about AI ethics?",
                    "Tell me something interesting",
                    "How can I improve my productivity?"
                ]
            },
            {
                'name': 'data_processing',
                'description': 'Working with structured data and formats',
                'prompts': [
                    "Convert this to JSON: name: John, age: 30, city: NYC",
                    "Create a CSV structure for student grades",
                    "Format this data as a table: Product A - $10, Product B - $20",
                    "Generate a YAML configuration for a web server",
                    "Create a list of 5 programming languages with their paradigms"
                ]
            },
            {
                'name': 'debugging',
                'description': 'Error analysis and problem-solving',
                'prompts': [
                    "Fix this Python error: 'list index out of range'",
                    "Why is my CSS not applying to this element?",
                    "Debug this SQL query that returns no results",
                    "Find the issue in this JavaScript function",
                    "Troubleshoot: Python script runs but produces no output"
                ]
            }
        ]

    def _init_database(self):
        """Initialize database for cost analysis results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cloud_model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT,
                model_id TEXT,
                task_category TEXT,
                success_rate REAL,
                avg_response_time REAL,
                avg_quality_score REAL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_cost DECIMAL(10,6),
                cost_per_test DECIMAL(10,6),
                tokens_per_dollar DECIMAL(10,2),
                cost_effectiveness_score REAL,
                provider TEXT,
                context_limit INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cost_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT,
                model_id TEXT,
                weighted_cost_per_million DECIMAL(10,6),
                avg_project_cost DECIMAL(10,6),
                tokens_per_test_avg INTEGER,
                cost_effectiveness_rank INTEGER,
                recommendation TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def estimate_tokens_from_text(self, text: str) -> int:
        """Rough token estimation (approx 4 chars per token)"""
        return max(1, len(text) // 4)

    def calculate_test_cost(self, cost_metric: CostMetrics, input_text: str, output_text: str) -> TestCostData:
        """Calculate actual cost for a single test"""
        input_tokens = self.estimate_tokens_from_text(input_text)
        output_tokens = self.estimate_tokens_from_text(output_text)

        if cost_metric.is_free:
            total_cost = Decimal('0.00')
        else:
            input_cost = (Decimal(input_tokens) / Decimal('1000000')) * cost_metric.input_cost_per_million
            output_cost = (Decimal(output_tokens) / Decimal('1000000')) * cost_metric.output_cost_per_million
            total_cost = input_cost + output_cost

        # Calculate cost metrics
        total_tokens = input_tokens + output_tokens
        cost_per_test = total_cost
        tokens_per_dollar = Decimal('0.00') if total_cost == 0 else Decimal(total_tokens) / total_cost if total_cost > 0 else Decimal('inf')

        return TestCostData(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_cost=total_cost,
            cost_per_test=cost_per_test,
            tokens_per_dollar=tokens_per_dollar
        )

    def test_cloud_model_single_query(self, cost_metric: CostMetrics, prompt: str) -> Tuple[bool, float, str, TestCostData]:
        """Test a single cloud model query with cost tracking"""
        start_time = time.time()

        try:
            headers = {
                "Authorization": f"Bearer {self.openrouter_api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": cost_metric.model_id,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }

            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result['choices'][0]['message']['content'].strip()
                duration = time.time() - start_time

                success = len(response_text) > 10

                # Calculate actual cost
                cost_data = self.calculate_test_cost(cost_metric, prompt, response_text)

                return success, duration, response_text, cost_data
            else:
                duration = time.time() - start_time
                cost_data = TestCostData(0, 0, Decimal('0.00'), Decimal('0.00'), Decimal('0.00'))
                return False, duration, "", cost_data

        except Exception as e:
            duration = time.time() - start_time
            cost_data = TestCostData(0, 0, Decimal('0.00'), Decimal('0.00'), Decimal('0.00'))
            return False, duration, "", cost_data

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
            if any(indicator in response.lower() for indicator in ["is", "are", "was", "were", "capital", "author", "year"]):
                score += 20
        elif task_category == "code_generation":
            code_indicators = ["def ", "function", "class ", "import", "SELECT", "const", "let", "var"]
            if any(indicator in response for indicator in code_indicators):
                score += 25
        elif task_category == "data_processing":
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

    def test_cloud_model_category(self, cost_metric: CostMetrics, category: Dict) -> CloudModelPerformance:
        """Test a cloud model across a specific task category"""
        print(f"   Testing {cost_metric.model_name} on {category['name']}...")

        results = []
        response_times = []
        quality_scores = []
        cost_data_list = []

        for i, prompt in enumerate(category['prompts']):
            print(f"     Test {i+1}/{len(category['prompts'])}: {prompt[:30]}...")

            success, duration, response_text, test_cost_data = self.test_cloud_model_single_query(cost_metric, prompt)

            if success:
                quality_score = self._evaluate_response_quality(prompt, response_text, category['name'])

                results.append({
                    'success': True,
                    'duration': duration,
                    'quality_score': quality_score,
                    'cost_data': test_cost_data
                })

                response_times.append(duration)
                quality_scores.append(quality_score)
                cost_data_list.append(test_cost_data)
            else:
                results.append({
                    'success': False,
                    'duration': duration,
                    'quality_score': 0,
                    'cost_data': test_cost_data
                })

            time.sleep(1)  # Rate limiting for cloud APIs

        # Calculate metrics
        successful_tests = [r for r in results if r['success']]
        success_rate = (len(successful_tests) / len(results)) * 100 if results else 0

        avg_response_time = statistics.mean(response_times) if response_times else 0
        avg_quality_score = statistics.mean(quality_scores) if quality_scores else 0

        # Aggregate cost data
        total_input_tokens = sum(cd.input_tokens for cd in cost_data_list)
        total_output_tokens = sum(cd.output_tokens for cd in cost_data_list)
        total_cost = sum(cd.total_cost for cd in cost_data_list)
        avg_cost_per_test = total_cost / len(cost_data_list) if cost_data_list else Decimal('0.00')
        avg_tokens_per_dollar = statistics.mean([cd.tokens_per_dollar for cd in cost_data_list]) if cost_data_list else 0

        aggregated_cost_data = TestCostData(
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            total_cost=total_cost,
            cost_per_test=avg_cost_per_test,
            tokens_per_dollar=avg_tokens_per_dollar
        )

        # Calculate cost-effectiveness score (quality per dollar)
        if avg_cost_per_test > 0:
            cost_effectiveness_score = avg_quality_score / float(avg_cost_per_test)
        else:
            cost_effectiveness_score = avg_quality_score * 100  # Free models get bonus

        return CloudModelPerformance(
            model_name=cost_metric.model_name,
            model_id=cost_metric.model_id,
            task_category=category['name'],
            success_rate=success_rate,
            avg_response_time=avg_response_time,
            avg_quality_score=avg_quality_score,
            cost_data=aggregated_cost_data,
            cost_effectiveness_score=cost_effectiveness_score,
            provider=cost_metric.provider,
            context_limit=cost_metric.context_limit
        )

    def run_comprehensive_cloud_analysis(self) -> Dict:
        """Run comprehensive cloud model analysis"""
        print("\n🚀 Starting Comprehensive Cloud Model Analysis")
        print("=" * 70)
        print(f"Models: {len(self.cost_metrics)}")
        print(f"Task Categories: {len(self.task_categories)}")
        print(f"Total Tests: {len(self.cost_metrics) * len(self.task_categories)}")
        print()

        all_performances = []

        for category in self.task_categories:
            print(f"📋 Category: {category['name'].upper()} - {category['description']}")
            print()

            category_performances = []

            for cost_metric in self.cost_metrics:
                performance = self.test_cloud_model_category(cost_metric, category)
                category_performances.append(performance)
                all_performances.append(performance)

                # Save to database
                self._save_cloud_performance_to_db(performance)

            # Sort by cost-effectiveness score
            category_performances.sort(key=lambda x: x.cost_effectiveness_score, reverse=True)

            print(f"   🏆 Results for {category['name']} (by cost-effectiveness):")
            for i, perf in enumerate(category_performances[:5], 1):  # Top 5 only
                cost_str = "FREE" if perf.cost_data.total_cost == 0 else f"${perf.cost_data.total_cost:.6f}"
                print(f"      {i}. {perf.model_name}: {perf.cost_effectiveness_score:.1f} score "
                      f"(Quality: {perf.avg_quality_score:.1f}, Cost: {cost_str})")
            print()

        # Generate cost analysis
        cost_analysis = self._generate_cost_analysis(all_performances)

        return {
            'performances': all_performances,
            'cost_analysis': cost_analysis
        }

    def _generate_cost_analysis(self, performances: List[CloudModelPerformance]) -> Dict:
        """Generate detailed cost analysis and recommendations"""
        print("💰 Generating Cost Analysis...")

        # Group performances by model
        model_groups = {}
        for perf in performances:
            if perf.model_name not in model_groups:
                model_groups[perf.model_name] = []
            model_groups[perf.model_name].append(perf)

        model_analysis = {}

        for model_name, model_perfs in model_groups.items():
            # Calculate weighted averages
            total_input_tokens = sum(p.cost_data.input_tokens for p in model_perfs)
            total_output_tokens = sum(p.cost_data.output_tokens for p in model_perfs)
            total_cost = sum(p.cost_data.total_cost for p in model_perfs)
            total_tests = len(model_perfs)

            if total_cost > 0:
                # Calculate real cost per million tokens
                total_tokens = total_input_tokens + total_output_tokens
                weighted_cost_per_million = (total_cost / Decimal(total_tokens)) * Decimal('1000000')
            else:
                weighted_cost_per_million = Decimal('0.00')

            # Average project cost (all 8 categories)
            avg_project_cost = total_cost / len(model_perfs) if model_perfs else Decimal('0.00')

            # Average tokens per test
            avg_tokens_per_test = (total_input_tokens + total_output_tokens) // total_tests if total_tests > 0 else 0

            # Average quality score
            avg_quality = statistics.mean([p.avg_quality_score for p in model_perfs]) if model_perfs else 0

            model_analysis[model_name] = {
                'model_id': model_perfs[0].model_id,
                'provider': model_perfs[0].provider,
                'context_limit': model_perfs[0].context_limit,
                'weighted_cost_per_million': float(weighted_cost_per_million),
                'avg_project_cost': float(avg_project_cost),
                'avg_tokens_per_test': avg_tokens_per_test,
                'avg_quality_score': avg_quality,
                'total_tests': total_tests,
                'is_free': all(p.cost_data.total_cost == 0 for p in model_perfs)
            }

            # Save to database
            self._save_cost_analysis_to_db(model_name, model_analysis[model_name])

        # Generate optimization recommendations
        recommendations = self._generate_optimization_recommendations(model_analysis)

        return {
            'model_analysis': model_analysis,
            'recommendations': recommendations
        }

    def _generate_optimization_recommendations(self, model_analysis: Dict) -> Dict:
        """Generate cost optimization recommendations"""
        print("🎯 Generating Optimization Recommendations...")

        # Separate free and paid models
        free_models = {name: data for name, data in model_analysis.items() if data['is_free']}
        paid_models = {name: data for name, data in model_analysis.items() if not data['is_free']}

        # Best paid models by quality
        best_paid_by_quality = sorted(paid_models.items(),
                                    key=lambda x: x[1]['avg_quality_score'],
                                    reverse=True)

        # Best paid models by cost-effectiveness
        best_paid_by_cost = sorted(paid_models.items(),
                                 key=lambda x: x[1]['avg_quality_score'] / max(0.01, x[1]['avg_project_cost']),
                                 reverse=True)

        recommendations = {
            'budget_allocation': {},
            'task_routing': {},
            'cost_thresholds': {},
            'optimization_rules': []
        }

        # Task-specific routing based on our previous local results
        # Local best performers: llama3.2:3b, qwen2.5-coder:7b
        local_benchmarks = {
            'quick_qa': {'quality': 75.0, 'cost': 0.0},
            'code_generation': {'quality': 90.0, 'cost': 0.0},
            'creative_writing': {'quality': 60.0, 'cost': 0.0},
            'data_processing': {'quality': 90.0, 'cost': 0.0},
            'conversation': {'quality': 70.0, 'cost': 0.0},
            'summarization': {'quality': 70.0, 'cost': 0.0}
        }

        # Generate rules for each task type
        for task, benchmark in local_benchmarks.items():
            best_paid_option = best_paid_by_quality[0] if best_paid_by_quality else None

            if best_paid_option:
                paid_model, paid_data = best_paid_option
                quality_improvement = paid_data['avg_quality_score'] - benchmark['quality']
                cost_difference = paid_data['avg_project_cost']

                # Decision rule
                if cost_difference <= 0.01 and quality_improvement > 15:
                    recommendation = f"Use {paid_model} (significant improvement for low cost)"
                elif cost_difference <= 0.01 and quality_improvement > 5:
                    recommendation = f"Consider {paid_model} (moderate improvement for low cost)"
                elif quality_improvement > 30 and cost_difference <= 0.10:
                    recommendation = f"Use {paid_model} (major improvement worth cost)"
                else:
                    recommendation = f"Use local model (cost outweighs benefit)"

                recommendations['task_routing'][task] = {
                    'local_quality': benchmark['quality'],
                    'cloud_option': paid_model,
                    'cloud_quality': paid_data['avg_quality_score'],
                    'quality_improvement': quality_improvement,
                    'project_cost': cost_difference,
                    'recommendation': recommendation
                }

        # Budget allocation recommendations
        recommendations['budget_allocation'] = {
            'free_tier_usage': 'Use for all non-critical tasks',
            'project_budget_under_01': 'Consider cloud upgrades for high-value tasks',
            'project_budget_01_to_10': 'Use cloud for complex analysis and code generation',
            'sensitive_data': 'Always use local models regardless of cost'
        }

        # Cost thresholds for automated decisions
        recommendations['cost_thresholds'] = {
            'free_threshold': 0.00,
            'low_cost_threshold': 0.01,
            'medium_cost_threshold': 0.10,
            'high_cost_threshold': 1.00
        }

        # Optimization rules for implementation
        recommendations['optimization_rules'] = [
            {
                'rule': 'Free tier优先',
                'condition': 'data_sensitivity == "low" AND task_complexity <= "medium"',
                'action': 'use_best_free_model',
                'reasoning': 'Maximize value while minimizing cost'
            },
            {
                'rule': '质量提升阈值',
                'condition': 'quality_improvement > 20% AND project_cost < 0.01',
                'action': 'upgrade_to_cloud',
                'reasoning': 'Significant quality improvement justifies minimal cost'
            },
            {
                'rule': '复杂任务云处理',
                'condition': 'task_complexity == "high" AND data_sensitivity == "low"',
                'action': 'use_best_cloud_model',
                'reasoning': 'Complex tasks benefit from superior cloud capabilities'
            },
            {
                'rule': '敏感数据本地处理',
                'condition': 'data_sensitivity == "high"',
                'action': 'use_local_model_only',
                'reasoning': 'Security and privacy requirements override cost considerations'
            }
        ]

        return recommendations

    def _save_cloud_performance_to_db(self, performance: CloudModelPerformance):
        """Save cloud performance data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO cloud_model_performance (
                model_name, model_id, task_category, success_rate, avg_response_time,
                avg_quality_score, input_tokens, output_tokens, total_cost,
                cost_per_test, tokens_per_dollar, cost_effectiveness_score,
                provider, context_limit
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            performance.model_name,
            performance.model_id,
            performance.task_category,
            performance.success_rate,
            performance.avg_response_time,
            performance.avg_quality_score,
            performance.cost_data.input_tokens,
            performance.cost_data.output_tokens,
            float(performance.cost_data.total_cost),
            float(performance.cost_data.cost_per_test),
            float(performance.cost_data.tokens_per_dollar),
            performance.cost_effectiveness_score,
            performance.provider,
            performance.context_limit
        ))

        conn.commit()
        conn.close()

    def _save_cost_analysis_to_db(self, model_name: str, analysis: Dict):
        """Save cost analysis to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO cost_analysis (
                model_name, model_id, weighted_cost_per_million, avg_project_cost,
                tokens_per_test_avg, recommendation
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            model_name,
            analysis['model_id'],
            analysis['weighted_cost_per_million'],
            analysis['avg_project_cost'],
            analysis['avg_tokens_per_test'],
            json.dumps(analysis)
        ))

        conn.commit()
        conn.close()

    def generate_comprehensive_report(self, analysis_results: Dict) -> str:
        """Generate comprehensive cost-optimization report"""
        report = []
        report.append("# 💰 Cost-Optimization Model Analysis Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Executive Summary
        cost_analysis = analysis_results['cost_analysis']
        model_analysis = cost_analysis['model_analysis']
        recommendations = cost_analysis['recommendations']

        report.append("## 📊 Executive Summary")
        report.append(f"- **Models Analyzed**: {len(model_analysis)}")
        report.append(f"- **Free Models Available**: {len([m for m in model_analysis.values() if m['is_free']])}")
        report.append(f"- **Task Categories**: {len(self.task_categories)}")
        report.append("")

        # Cost Analysis Table
        report.append("## 💰 Real Cost Analysis (Based on Test Data)")
        report.append("| Model | Provider | Cost/M Tokens | Avg Project Cost | Quality Score | Free? |")
        report.append("|-------|----------|---------------|------------------|--------------|-------|")

        # Sort by cost-effectiveness
        sorted_models = sorted(model_analysis.items(),
                             key=lambda x: x[1]['avg_quality_score'] / max(0.01, x[1]['avg_project_cost']),
                             reverse=True)

        for model_name, data in sorted_models:
            cost_str = "FREE" if data['is_free'] else f"${data['weighted_cost_per_million']:.6f}"
            project_cost_str = "FREE" if data['is_free'] else f"${data['avg_project_cost']:.6f}"
            free_str = "✅" if data['is_free'] else "❌"

            report.append(f"| {model_name} | {data['provider']} | {cost_str} | {project_cost_str} | {data['avg_quality_score']:.1f} | {free_str} |")

        report.append("")

        # Task-Specific Recommendations
        report.append("## 🎯 Task-Specific Routing Recommendations")
        for task, rec in recommendations['task_routing'].items():
            report.append(f"### {task.replace('_', ' ').title()}")
            report.append(f"- **Local Quality**: {rec['local_quality']:.1f}/100 (Free)")
            report.append(f"- **Cloud Option**: {rec['cloud_option']} ({rec['cloud_quality']:.1f}/100)")
            report.append(f"- **Quality Improvement**: +{rec['quality_improvement']:.1f}%")
            report.append(f"- **Project Cost**: ${rec['project_cost']:.4f}")
            report.append(f"- **Recommendation**: {rec['recommendation']}")
            report.append("")

        # Optimization Rules
        report.append("## ⚙️ Optimization Rules for Implementation")
        for i, rule in enumerate(recommendations['optimization_rules'], 1):
            report.append(f"### Rule {i}: {rule['rule']}")
            report.append(f"- **Condition**: `{rule['condition']}`")
            report.append(f"- **Action**: {rule['action']}")
            report.append(f"- **Reasoning**: {rule['reasoning']}")
            report.append("")

        # Budget Guidelines
        report.append("## 💡 Budget Guidelines")
        for category, guideline in recommendations['budget_allocation'].items():
            report.append(f"- **{category.replace('_', ' ').title()}**: {guideline}")
        report.append("")

        # Cost Thresholds
        report.append("## 📈 Cost Thresholds for Automated Decisions")
        for threshold, value in recommendations['cost_thresholds'].items():
            threshold_name = threshold.replace('_', ' ').title()
            report.append(f"- **{threshold_name}**: ${value}")
        report.append("")

        return "\n".join(report)

    def run_autonomous_cost_analysis(self) -> str:
        """Run complete autonomous cost analysis"""
        print("🤖 Starting Autonomous Cost-Optimization Analysis")
        print("This will analyze all cloud models and generate cost-optimized routing recommendations")
        print("Estimated time: 45-60 minutes")
        print()

        # Run comprehensive analysis
        analysis_results = self.run_comprehensive_cloud_analysis()

        # Generate report
        report = self.generate_comprehensive_report(analysis_results)

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"cost_optimization_report_{timestamp}.md"

        with open(report_file, 'w') as f:
            f.write(report)

        print(f"\n✅ Cost-Optimization Analysis Complete!")
        print(f"📄 Report saved: {report_file}")
        print(f"💰 Database: {self.db_path}")

        # Print key findings
        print(f"\n🎯 Key Findings:")
        cost_analysis = analysis_results['cost_analysis']
        recommendations = cost_analysis['recommendations']

        # Best cost-effective model
        sorted_models = sorted(cost_analysis['model_analysis'].items(),
                             key=lambda x: x[1]['avg_quality_score'] / max(0.01, x[1]['avg_project_cost']),
                             reverse=True)

        if sorted_models:
            best_model, best_data = sorted_models[0]
            if best_data['is_free']:
                print(f"   🏆 Best Value: {best_model} (FREE, {best_data['avg_quality_score']:.1f} quality)")
            else:
                print(f"   🏆 Best Value: {best_model} (${best_data['avg_project_cost']:.6f} per project, {best_data['avg_quality_score']:.1f} quality)")

        # Budget recommendations
        print(f"   💰 Budget Rule: Use cloud models when project cost < $0.01 AND quality improvement > 20%")
        print(f"   🔒 Security Rule: Always use local models for sensitive data")

        return report_file

def main():
    """Main execution function"""
    try:
        tester = CostOptimizationTester()
        report_file = tester.run_autonomous_cost_analysis()

        print(f"\n🎉 Cost-Optimization Analysis Complete!")
        print(f"📄 View detailed report: {report_file}")
        return 0

    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)