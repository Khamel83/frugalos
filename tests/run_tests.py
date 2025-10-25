#!/usr/bin/env python3
"""
Hermes Test Runner
Runs all test suites and provides comprehensive test reporting
"""

import unittest
import sys
import time
import argparse
from io import StringIO

# Add hermes to path
sys.path.insert(0, '..')

def run_test_suite(test_module, verbose=False):
    """Run a specific test module and return results"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_module)

    # Capture output
    stream = StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2 if verbose else 1,
        buffer=True
    )

    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()

    output = stream.getvalue()

    return {
        'module': test_module.__name__,
        'tests_run': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
        'time_taken': end_time - start_time,
        'success': result.wasSuccessful(),
        'output': output
    }

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description='Hermes Test Runner')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--module', '-m', help='Run specific test module')
    parser.add_argument('--pattern', '-p', help='Run tests matching pattern')
    args = parser.parse_args()

    print("🤖 Hermes Test Suite")
    print("=" * 50)

    # Import test modules
    test_modules = []

    if args.module:
        # Run specific module
        if args.module == 'orchestrator':
            from test_orchestrator import *
            import test_orchestrator
            test_modules.append(test_orchestrator)
        elif args.module == 'metalearning':
            from test_metalearning import *
            import test_metalearning
            test_modules.append(test_metalearning)
        elif args.module == 'autonomous':
            from test_autonomous import *
            import test_autonomous
            test_modules.append(test_autonomous)
        else:
            print(f"Unknown module: {args.module}")
            return 1
    else:
        # Run all modules
        try:
            from test_orchestrator import *
            import test_orchestrator
            test_modules.append(test_orchestrator)
        except ImportError:
            print("⚠️  Could not import orchestrator tests")

        try:
            from test_metalearning import *
            import test_metalearning
            test_modules.append(test_metalearning)
        except ImportError:
            print("⚠️  Could not import metalearning tests")

        try:
            from test_autonomous import *
            import test_autonomous
            test_modules.append(test_autonomous)
        except ImportError:
            print("⚠️  Could not import autonomous tests")

    if not test_modules:
        print("❌ No test modules found")
        return 1

    # Run tests
    all_results = []
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    total_time = 0

    for module in test_modules:
        print(f"\n📋 Running {module.__name__}...")
        print("-" * 40)

        result = run_test_suite(module, args.verbose)
        all_results.append(result)

        total_tests += result['tests_run']
        total_failures += result['failures']
        total_errors += result['errors']
        total_skipped += result['skipped']
        total_time += result['time_taken']

        # Show summary for module
        if result['success']:
            print(f"✅ {result['module']}: {result['tests_run']} tests passed")
        else:
            print(f"❌ {result['module']}: {result['tests_run']} tests, "
                  f"{result['failures']} failures, {result['errors']} errors")

        if args.verbose and not result['success']:
            print("\nDetailed output:")
            print(result['output'])

    # Overall summary
    print("\n" + "=" * 50)
    print("📊 Test Summary")
    print("=" * 50)

    print(f"Total tests run: {total_tests}")
    print(f"Passed: {total_tests - total_failures - total_errors}")
    print(f"Failures: {total_failures}")
    print(f"Errors: {total_errors}")
    print(f"Skipped: {total_skipped}")
    print(f"Time taken: {total_time:.2f}s")

    success_rate = ((total_tests - total_failures - total_errors) / total_tests) * 100 if total_tests > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")

    # Module breakdown
    print("\n📋 Module Breakdown:")
    for result in all_results:
        status = "✅" if result['success'] else "❌"
        print(f"{status} {result['module']}: {result['tests_run']} tests "
              f"({result['time_taken']:.2f}s)")

    # Detailed failures if any
    if total_failures > 0 or total_errors > 0:
        print("\n❌ Failed Tests Details:")
        print("-" * 30)

        for result in all_results:
            if not result['success']:
                print(f"\n📦 {result['module']}:")
                # Parse output to extract failures
                lines = result['output'].split('\n')
                for line in lines:
                    if 'FAIL:' in line or 'ERROR:' in line:
                        print(f"  {line.strip()}")

    # Return exit code
    return 0 if (total_failures == 0 and total_errors == 0) else 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)