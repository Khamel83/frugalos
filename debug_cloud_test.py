#!/usr/bin/env python3
"""
Debug script to test OpenRouter API connection
"""

import os
import requests
import json

def test_openrouter_api():
    print("🔍 Testing OpenRouter API Connection...")

    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("❌ OPENROUTER_API_KEY not set")
        return False

    print(f"✅ API Key found: {api_key[:10]}...")

    # Test API connection
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Test with a simple free model
    payload = {
        "model": "tngtech/deepseek-r1t2-chimera:free",
        "messages": [
            {"role": "user", "content": "Hello, respond with just 'API working'"}
        ],
        "max_tokens": 10,
        "temperature": 0.1
    }

    try:
        print("📡 Sending test request...")
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        print(f"📊 Status Code: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            response_text = result['choices'][0]['message']['content']
            print(f"✅ API Response: {response_text}")
            return True
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_model_list():
    print("\n📋 Testing model list...")

    api_key = os.getenv('OPENROUTER_API_KEY')
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            models = response.json()
            print(f"✅ Found {len(models['data'])} models")

            # Check if our test models exist
            test_models = [
                "tngtech/deepseek-r1t2-chimera:free",
                "mistralai/mistral-nemo",
                "google/gemini-2.0-flash-001"
            ]

            for model_id in test_models:
                found = any(m['id'] == model_id for m in models['data'])
                status = "✅" if found else "❌"
                print(f"   {status} {model_id}")

            return True
        else:
            print(f"❌ Failed to get models: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Exception getting models: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 OpenRouter API Debug Test")
    print("=" * 40)

    # Test basic connection
    api_works = test_openrouter_api()

    # Test model list
    models_work = test_model_list()

    if api_works and models_work:
        print("\n🎉 All tests passed! Ready for comprehensive testing.")
    else:
        print("\n❌ Some tests failed. Check configuration.")