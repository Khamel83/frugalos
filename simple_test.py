#!/usr/bin/env python3
"""
Simple Hermes Test - Focus on what actually works
Tests only the core functionality without complex dependencies
"""

import sys
import os
import requests
import json
import time
from datetime import datetime

# Add hermes to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hermes'))

def test_ollama_models():
    """Test only the working Ollama models"""
    print("🚀 Testing Ollama Models")
    print("=" * 50)

    # Your working models
    models = [
        'llama3.2:3b',
        'llama3.1:8b',
        'gemma3:latest',
        'qwen2.5-coder:7b',
        'deepseek-r1:8b'
    ]

    test_prompt = "Respond with exactly: Working perfectly"
    results = []

    for model in models:
        print(f"\n🧪 Testing {model}...")
        start_time = time.time()

        try:
            payload = {
                'model': model,
                'prompt': test_prompt,
                'stream': False,
                'options': {
                    'temperature': 0.1,
                    'num_predict': 50
                }
            }

            response = requests.post(
                'http://localhost:11434/api/generate',
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                duration = time.time() - start_time

                success = len(response_text) > 0
                status = "✅ WORKING" if success else "❌ FAILED"

                print(f"   {status} - {len(response_text)} chars in {duration:.2f}s")
                print(f"   Response: {response_text}")

                results.append({
                    'model': model,
                    'success': success,
                    'duration': duration,
                    'response_length': len(response_text),
                    'response_preview': response_text[:100]
                })
            else:
                print(f"   ❌ HTTP {response.status_code}")
                results.append({
                    'model': model,
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                })

        except Exception as e:
            print(f"   ❌ Error: {str(e)[:50]}...")
            results.append({
                'model': model,
                'success': False,
                'error': str(e)
            })

    return results

def test_personalization():
    """Test personalization system only"""
    print("\n🧠 Testing Personalization System")
    print("=" * 50)

    try:
        from hermes.personalization.user_profiler import initialize_user_profiler, get_user_profiler

        # Initialize with minimal config
        initialize_user_profiler({'max_history_size': 50})
        profiler = get_user_profiler()

        print("✅ User profiler initialized successfully")

        # Test basic profile creation
        test_user_id = "simple_test_user"
        test_message = "I prefer simple explanations"
        test_response = "Here is a simple explanation..."

        result = profiler.process_interaction(
            user_id=test_user_id,
            message=test_message,
            response=test_response,
            metadata={'test': True}
        )

        print("✅ Interaction processed successfully")

        # Test profile retrieval
        profile = profiler.get_user_profile(test_user_id)
        print(f"✅ Profile retrieved with confidence: {result.learning_confidence:.2f}")

        return True

    except Exception as e:
        print(f"❌ Personalization test failed: {e}")
        return False

def generate_report(results, personalization_works):
    """Generate simple report"""
    print("\n" + "=" * 60)
    print("📊 SIMPLE HERMES TEST REPORT")
    print("=" * 60)

    working_models = [r for r in results if r['success']]
    total_models = len(results)

    print(f"\n🎯 Model Performance:")
    print(f"   Working Models: {len(working_models)}/{total_models}")

    # Sort by speed
    working_models.sort(key=lambda x: x['duration'])

    print(f"\n🏆 Performance Rankings:")
    for i, model in enumerate(working_models, 1):
        print(f"   {i}. {model['model']}: {model['duration']:.2f}s")

    print(f"\n🧠 Personalization: {'✅ WORKING' if personalization_works else '❌ FAILED'}")

    # Best and worst
    if working_models:
        fastest = working_models[0]
        slowest = working_models[-1]

        print(f"\n⚡ Fastest: {fastest['model']} ({fastest['duration']:.2f}s)")
        print(f"🐌 Slowest: {slowest['model']} ({slowest['duration']:.2f}s)")

        # Recommendation
        print(f"\n💡 Recommendation: Use {fastest['model']} for quick responses")
        print(f"💡 Use {slowest['model']} for detailed analysis")

    overall_success = len(working_models) >= 4 and personalization_works
    print(f"\n🎉 Overall Status: {'✅ READY FOR USE' if overall_success else '❌ NEEDS FIXES'}")

    return overall_success

def main():
    """Run simple tests"""
    print("🚀 Simple Hermes AI Assistant Test")
    print(f"Start Time: {datetime.now()}")
    print("Testing only what actually works...\n")

    # Test models
    model_results = test_ollama_models()

    # Test personalization
    personalization_works = test_personalization()

    # Generate report
    success = generate_report(model_results, personalization_works)

    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)