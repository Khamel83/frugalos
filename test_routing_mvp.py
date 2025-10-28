#!/usr/bin/env python3
"""
Test script for Local-First Routing MVP
Tests basic functionality before full integration
"""
import sys
import os

# Add hermes to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hermes.routing.router import LocalFirstRouter


def test_local_success():
    """Test case where local model should succeed"""

    print("\n" + "=" * 60)
    print("TEST 1: Local Success (Simple Task)")
    print("=" * 60)

    router = LocalFirstRouter()

    # Simple task that should work well locally
    prompt = "Write a Python function to reverse a string"

    result = router.process_prompt(prompt)

    print(f"\nStatus: {result['status']}")

    if result['status'] == 'local_success':
        print(f"✅ Model: {result['model']}")
        print(f"✅ Quality: {result['quality']:.1f}/10")
        print(f"✅ Cost: ${result['cost']}")
        print(f"\nResponse preview:")
        print(result['response'][:200] + "...")
        return True
    else:
        print(f"❌ Expected local_success, got {result['status']}")
        return False


def test_upgrade_needed():
    """Test case where upgrade should be needed"""

    print("\n" + "=" * 60)
    print("TEST 2: Upgrade Needed (Complex Task)")
    print("=" * 60)

    router = LocalFirstRouter()

    # Complex task that will likely need upgrade
    prompt = "Design a comprehensive microservices architecture for a global e-commerce platform with multi-region deployment, event sourcing, CQRS pattern, and real-time inventory synchronization"

    result = router.process_prompt(prompt)

    print(f"\nStatus: {result['status']}")

    if result['status'] == 'local_limited':
        local = result['local_result']
        print(f"✅ Local Quality: {local['quality']:.1f}/10 (below threshold)")
        print(f"✅ Upgrade Options: {len(result['upgrade_options'])}")

        if result['upgrade_options']:
            best_option = result['upgrade_options'][0]
            print(f"✅ Best Upgrade: {best_option['model']}")
            print(f"✅ Estimated Cost: ${best_option['estimated_cost']:.6f}")
            print(f"✅ Quality Gain: +{best_option['quality_gain']:.1f}")

        # Check session analysis
        if 'session_analysis' in result:
            analysis = result['session_analysis']
            if analysis.get('status') == 'considering_upgrade':
                print(f"\n📊 Session Analysis:")
                print(f"   Single Task: ${analysis['single_task_cost']:.6f}")
                print(f"   Full Session: ${analysis['total_session_cost']:.4f}")
                print(f"   Premium: {analysis['session_premium']:.1f}x")

        return True
    elif result['status'] == 'local_success':
        print(f"⚠️  Local succeeded (quality {result['quality']:.1f}/10) - task easier than expected")
        return True
    else:
        print(f"❌ Unexpected status: {result['status']}")
        return False


def test_session_continuity():
    """Test session continuity"""

    print("\n" + "=" * 60)
    print("TEST 3: Session Continuity")
    print("=" * 60)

    router = LocalFirstRouter()

    # First task
    result1 = router.process_prompt("What is Python?")
    session_id = result1['session']['session_id']

    print(f"\n✅ First task - Session ID: {session_id}")
    print(f"   Task count: {result1['session']['task_count']}")

    # Second task in same session
    result2 = router.process_prompt("Give me an example", session_id=session_id)

    print(f"✅ Second task - Same session")
    print(f"   Task count: {result2['session']['task_count']}")
    print(f"   Session tier: {result2['session']['tier']}")

    if result2['session']['task_count'] == 2:
        print("✅ Session continuity working")
        return True
    else:
        print(f"❌ Expected 2 tasks, got {result2['session']['task_count']}")
        return False


def test_database():
    """Test database persistence"""

    print("\n" + "=" * 60)
    print("TEST 4: Database Persistence")
    print("=" * 60)

    router = LocalFirstRouter()

    # Process a task
    result = router.process_prompt("Hello world")

    # Check if saved to database
    session_id = result['session']['session_id']
    db_session = router.database.get_session(session_id)

    if db_session:
        print(f"✅ Session saved to database")
        print(f"   Session ID: {db_session['session_id']}")
        print(f"   Tier: {db_session['tier']}")

        # Check tasks
        tasks = router.database.get_session_tasks(session_id)
        print(f"✅ Tasks in database: {len(tasks)}")

        return True
    else:
        print("❌ Session not found in database")
        return False


def test_cost_stats():
    """Test cost statistics"""

    print("\n" + "=" * 60)
    print("TEST 5: Cost Statistics")
    print("=" * 60)

    router = LocalFirstRouter()

    # Process a few tasks
    for i in range(3):
        router.process_prompt(f"Test task {i+1}")

    # Get stats
    stats = router.database.get_cost_stats(days=1)

    print(f"✅ Total tasks: {stats.get('total_tasks', 0)}")
    print(f"✅ Total cost: ${stats.get('total_cost', 0):.6f}")
    print(f"✅ Local tasks: {stats.get('local_tasks', 0)}")
    print(f"✅ Cloud tasks: {stats.get('cloud_tasks', 0)}")

    return True


def main():
    """Run all tests"""

    print("\n" + "=" * 60)
    print("🚀 LOCAL-FIRST ROUTING MVP TEST SUITE")
    print("=" * 60)

    tests = [
        ("Local Success", test_local_success),
        ("Upgrade Needed", test_upgrade_needed),
        ("Session Continuity", test_session_continuity),
        ("Database Persistence", test_database),
        ("Cost Statistics", test_cost_stats)
    ]

    results = []

    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! MVP is ready to use.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review output above.")

    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
