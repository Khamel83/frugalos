#!/usr/bin/env python3
"""
Quick Cost-Performance Test
Tests a few key models to get cost data fast
"""

import os
import requests
import json
import time
from decimal import Decimal
from datetime import datetime

def test_model_cost(model_id, model_name, prompt):
    """Test a single model and return cost data"""
    api_key = os.getenv('OPENROUTER_API_KEY')

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_id,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 200,
        "temperature": 0.7
    }

    try:
        start_time = time.time()
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        duration = time.time() - start_time

        if response.status_code == 200:
            result = response.json()

            # Extract response and token usage
            response_text = result['choices'][0]['message']['content'].strip()
            usage = result.get('usage', {})

            input_tokens = usage.get('prompt_tokens', 0)
            output_tokens = usage.get('completion_tokens', 0)

            # Calculate cost
            cost_per_million_input = Decimal('0.00')  # Will set per model
            cost_per_million_output = Decimal('0.00')  # Will set per model

            # Set costs based on model
            if "free" in model_id:
                cost_per_million_input = Decimal('0.00')
                cost_per_million_output = Decimal('0.00')
            elif "mistral-nemo" in model_id:
                cost_per_million_input = Decimal('0.02')
                cost_per_million_output = Decimal('0.04')
            elif "gemini-2.0-flash" in model_id:
                cost_per_million_input = Decimal('0.10')
                cost_per_million_output = Decimal('0.40')
            elif "qwen3-235b" in model_id:
                cost_per_million_input = Decimal('0.08')
                cost_per_million_output = Decimal('0.55')
            else:
                cost_per_million_input = Decimal('0.05')
                cost_per_million_output = Decimal('0.30')

            input_cost = (Decimal(input_tokens) / Decimal('1000000')) * cost_per_million_input
            output_cost = (Decimal(output_tokens) / Decimal('1000000')) * cost_per_million_output
            total_cost = input_cost + output_cost

            return {
                'success': True,
                'model_name': model_name,
                'model_id': model_id,
                'response_text': response_text,
                'duration': duration,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_cost': float(total_cost),
                'response_length': len(response_text)
            }
        else:
            return {
                'success': False,
                'model_name': model_name,
                'model_id': model_id,
                'error': f"HTTP {response.status_code}: {response.text}",
                'duration': duration
            }

    except Exception as e:
        return {
            'success': False,
            'model_name': model_name,
            'model_id': model_id,
            'error': str(e),
            'duration': 0
        }

def main():
    print("🚀 Quick Cost-Performance Test")
    print("=" * 50)
    print(f"Time: {datetime.now()}")
    print()

    # Test models - mix of free and paid
    test_models = [
        ("tngtech/deepseek-r1t2-chimera:free", "DeepSeek R1T2 (Free)"),
        ("mistralai/mistral-nemo", "Mistral Nemo ($0.02/$0.04)"),
        ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash ($0.10/$0.40)"),
        ("qwen/qwen3-235b-a22b-2507", "Qwen3 235B ($0.08/$0.55)"),
        ("google/gemma-3-12b-it", "Gemma 3 12B ($0.03/$0.10)")
    ]

    # Test prompts for different tasks
    test_prompts = {
        'quick_qa': "What is the capital of France?",
        'code_generation': "Write a Python function to reverse a string",
        'creative_writing': "Write a short slogan for eco-friendly water bottles",
        'analysis': "Explain the pros and cons of remote work in 3 points"
    }

    results = []

    for task_name, prompt in test_prompts.items():
        print(f"📋 Task: {task_name.replace('_', ' ').title()}")
        print(f"   Prompt: {prompt}")
        print()

        task_results = []

        for model_id, model_name in test_models:
            print(f"   🧪 Testing {model_name}...")

            result = test_model_cost(model_id, model_name, prompt)
            result['task_category'] = task_name
            task_results.append(result)

            if result['success']:
                cost_str = "FREE" if result['total_cost'] == 0 else f"${result['total_cost']:.6f}"
                print(f"      ✅ Success - {len(result['response_text'])} chars, {result['duration']:.2f}s, Cost: {cost_str}")
                print(f"      📝 Response: {result['response_text'][:100]}...")
            else:
                print(f"      ❌ Failed - {result['error']}")

            time.sleep(1)  # Rate limiting

        print()
        results.extend(task_results)

    # Generate analysis
    print("💰 Cost Analysis Results")
    print("=" * 50)

    successful_results = [r for r in results if r['success']]
    failed_results = [r for r in results if not r['success']]

    print(f"Total Tests: {len(results)}")
    print(f"Successful: {len(successful_results)}")
    print(f"Failed: {len(failed_results)}")
    print()

    if successful_results:
        # Calculate total costs
        total_cost = sum(r['total_cost'] for r in successful_results)
        total_input_tokens = sum(r['input_tokens'] for r in successful_results)
        total_output_tokens = sum(r['output_tokens'] for r in successful_results)

        print(f"💸 Total Cost: ${total_cost:.6f}")
        print(f"📊 Total Input Tokens: {total_input_tokens}")
        print(f"📊 Total Output Tokens: {total_output_tokens}")
        print(f"📊 Total Tokens: {total_input_tokens + total_output_tokens}")

        if total_cost > 0:
            avg_cost_per_million = (total_cost / (total_input_tokens + total_output_tokens)) * 1000000
            print(f"💰 Average Cost per 1M Tokens: ${avg_cost_per_million:.6f}")

        print()

        # Cost per project estimate (8 categories)
        avg_cost_per_project = total_cost / len(test_prompts)
        print(f"📈 Average Cost per Project (8 tasks): ${avg_cost_per_project:.6f}")
        print(f"📈 Cost for 100 Projects: ${avg_cost_per_project * 100:.2f}")
        print()

        # Best value models
        print("🏆 Best Value Models (Cost per 100 chars):")
        model_costs = {}
        for r in successful_results:
            if r['model_name'] not in model_costs:
                model_costs[r['model_name']] = []
            if r['total_cost'] > 0:
                cost_per_char = r['total_cost'] / r['response_length'] * 100
                model_costs[r['model_name']].append(cost_per_char)

        for model_name, costs in model_costs.items():
            if costs:
                avg_cost = sum(costs) / len(costs)
                print(f"   {model_name}: ${avg_cost:.6f} per 100 chars")

    print()
    print("🎯 Key Findings:")
    if successful_results:
        free_models = [r for r in successful_results if r['total_cost'] == 0]
        paid_models = [r for r in successful_results if r['total_cost'] > 0]

        if free_models:
            print(f"   ✅ {len(free_models)} free models working - use for non-critical tasks")

        if paid_models:
            avg_paid_cost = sum(r['total_cost'] for r in paid_models) / len(paid_models)
            print(f"   💰 Average paid model cost: ${avg_paid_cost:.6f} per task")

            if avg_paid_cost <= 0.01:
                print(f"   ✅ Paid models under $0.01 threshold - consider for quality improvement")
            else:
                print(f"   ⚠️  Paid models above $0.01 threshold - use strategically")

    return len(successful_results) > 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)