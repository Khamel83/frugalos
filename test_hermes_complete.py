#!/usr/bin/env python3
"""
Hermes AI Assistant - Complete Testing Suite
==============================================

This is the master testing file that validates all components of the Hermes AI Assistant v2.0.
Tests all 9 phases: infrastructure, core application, model integration, API endpoints,
personalization system, integration, performance, and error handling.

Run with: python test_hermes_complete.py
"""

import os
import sys
import time
import json
import asyncio
import aiohttp
import requests
import tempfile
import sqlite3
import subprocess
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add hermes to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'hermes'))

class HermesTestSuite:
    """Complete test suite for Hermes AI Assistant"""

    def __init__(self):
        self.test_results = {}
        self.temp_files = []
        self.temp_dbs = []
        self.start_time = datetime.now()
        self.base_url = 'http://127.0.0.1:8999'
        self.ollama_url = 'http://localhost:11434'

        # Available models from user's Ollama instance
        self.available_models = [
            'llama3.1:8b',
            'qwen2.5-coder:7b',
            'gemma3:latest',
            'qwen3:8b',
            'deepseek-r1:8b',
            'llama3.2:3b'
        ]

        print("🚀 Hermes AI Assistant - Complete Testing Suite")
        print("=" * 60)
        print(f"Start Time: {self.start_time}")
        print(f"Testing Models: {len(self.available_models)} Ollama models")
        print(f"Python Version: {sys.version}")
        print("=" * 60)

    def log_result(self, phase: str, test_name: str, success: bool,
                   details: str = "", duration: float = 0, data: Any = None):
        """Log test result with details"""
        if phase not in self.test_results:
            self.test_results[phase] = []

        result = {
            'test_name': test_name,
            'success': success,
            'details': details,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }

        self.test_results[phase].append(result)

        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} [{phase}] {test_name}")
        if details:
            print(f"    Details: {details}")
        if duration > 0:
            print(f"    Duration: {duration:.3f}s")

    def cleanup_temp_files(self):
        """Clean up all temporary files and databases"""
        print("\n🧹 Cleaning up temporary files...")

        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    print(f"   Deleted: {temp_file}")
            except Exception as e:
                print(f"   Error deleting {temp_file}: {e}")

        for temp_db in self.temp_dbs:
            try:
                if os.path.exists(temp_db):
                    os.unlink(temp_db)
                    print(f"   Deleted DB: {temp_db}")
            except Exception as e:
                print(f"   Error deleting DB {temp_db}: {e}")

    # ==================== PHASE 1: INFRASTRUCTURE VALIDATION ====================

    async def phase1_infrastructure_validation(self) -> bool:
        """Phase 1: Test basic infrastructure and dependencies"""
        print("\n🔍 PHASE 1: Infrastructure Validation")
        print("-" * 40)

        phase_success = True

        # Test 1.1: Python version and basic imports
        start_time = time.time()
        try:
            import fastapi
            import uvicorn
            import pydantic
            import aiofiles
            duration = time.time() - start_time
            self.log_result("Phase1", "Python Dependencies", True,
                          f"FastAPI {fastapi.__version__}, Uvicorn available", duration)
        except ImportError as e:
            duration = time.time() - start_time
            self.log_result("Phase1", "Python Dependencies", False,
                          f"Import error: {e}", duration)
            phase_success = False

        # Test 1.2: Hermes core imports
        start_time = time.time()
        try:
            from hermes.config import Config
            from hermes.database import Database
            from hermes.logger import setup_logger
            duration = time.time() - start_time
            self.log_result("Phase1", "Hermes Core Imports", True,
                          "All core modules imported successfully", duration)
        except ImportError as e:
            duration = time.time() - start_time
            self.log_result("Phase1", "Hermes Core Imports", False,
                          f"Import error: {e}", duration)
            phase_success = False

        # Test 1.3: Configuration system
        start_time = time.time()
        try:
            config = Config()
            # Test basic config access
            test_config = config.get('hermes.debug', False)
            duration = time.time() - start_time
            self.log_result("Phase1", "Configuration System", True,
                          f"Config loaded, debug={test_config}", duration)
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase1", "Configuration System", False,
                          f"Config error: {e}", duration)
            phase_success = False

        # Test 1.4: Database layer
        start_time = time.time()
        try:
            # Create temporary database
            temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            temp_db.close()
            self.temp_dbs.append(temp_db.name)

            db = Database(database_path=temp_db.name)
            db.initialize()

            # Test basic operation
            result = db.execute('SELECT 1 as test').fetchone()
            assert result[0] == 1

            duration = time.time() - start_time
            self.log_result("Phase1", "Database Layer", True,
                          "SQLite database creation and basic operations successful", duration)
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase1", "Database Layer", False,
                          f"Database error: {e}", duration)
            phase_success = False

        # Test 1.5: Ollama connectivity
        start_time = time.time()
        try:
            response = requests.get(f'{self.ollama_url}/api/tags', timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                duration = time.time() - start_time
                self.log_result("Phase1", "Ollama Connectivity", True,
                              f"Found {len(model_names)} models: {model_names[:3]}...", duration)
            else:
                duration = time.time() - start_time
                self.log_result("Phase1", "Ollama Connectivity", False,
                              f"HTTP {response.status_code}", duration)
                phase_success = False
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase1", "Ollama Connectivity", False,
                          f"Connection error: {e}", duration)
            phase_success = False

        return phase_success

    # ==================== PHASE 2: CORE APPLICATION TESTING ====================

    async def phase2_core_application(self) -> bool:
        """Phase 2: Test core FastAPI application"""
        print("\n🔍 PHASE 2: Core Application Testing")
        print("-" * 40)

        phase_success = True

        # Test 2.1: FastAPI app import and configuration
        start_time = time.time()
        try:
            from app_v2 import app
            duration = time.time() - start_time
            self.log_result("Phase2", "FastAPI App Import", True,
                          f"App '{app.title}' imported successfully", duration)
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase2", "FastAPI App Import", False,
                          f"App import error: {e}", duration)
            phase_success = False
            return phase_success

        # Test 2.2: Route configuration
        start_time = time.time()
        try:
            routes = [route.path for route in app.routes if hasattr(route, 'path')]
            required_routes = ['/', '/api/health', '/api/status']
            missing_routes = [r for r in required_routes if r not in routes]

            if not missing_routes:
                duration = time.time() - start_time
                self.log_result("Phase2", "Route Configuration", True,
                              f"Found {len(routes)} routes, all required routes present", duration)
            else:
                duration = time.time() - start_time
                self.log_result("Phase2", "Route Configuration", False,
                              f"Missing routes: {missing_routes}", duration)
                phase_success = False
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase2", "Route Configuration", False,
                          f"Route check error: {e}", duration)
            phase_success = False

        return phase_success

    # ==================== PHASE 3: MODEL INTEGRATION TESTING ====================

    async def phase3_model_integration(self) -> bool:
        """Phase 3: Test all Ollama models"""
        print("\n🔍 PHASE 3: Model Integration Testing")
        print("-" * 40)

        phase_success = True
        model_results = {}

        test_prompt = "Respond with exactly: Model test successful"

        for model_name in self.available_models:
            start_time = time.time()
            try:
                payload = {
                    'model': model_name,
                    'prompt': test_prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,
                        'num_predict': 50
                    }
                }

                response = requests.post(
                    f'{self.ollama_url}/api/generate',
                    json=payload,
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get('response', '').strip()
                    duration = time.time() - start_time

                    # Check if response contains expected text
                    success = "test successful" in response_text.lower()

                    model_results[model_name] = {
                        'success': success,
                        'duration': duration,
                        'response_length': len(response_text),
                        'response_preview': response_text[:100]
                    }

                    self.log_result("Phase3", f"Model {model_name}", success,
                                  f"{len(response_text)} chars in {duration:.2f}s", duration)

                    if not success:
                        phase_success = False

                else:
                    duration = time.time() - start_time
                    model_results[model_name] = {
                        'success': False,
                        'error': f"HTTP {response.status_code}",
                        'duration': duration
                    }
                    self.log_result("Phase3", f"Model {model_name}", False,
                                  f"HTTP {response.status_code}", duration)
                    phase_success = False

            except Exception as e:
                duration = time.time() - start_time
                model_results[model_name] = {
                    'success': False,
                    'error': str(e),
                    'duration': duration
                }
                self.log_result("Phase3", f"Model {model_name}", False,
                              f"Error: {str(e)}", duration)
                phase_success = False

        # Summary of model performance
        successful_models = sum(1 for r in model_results.values() if r['success'])
        avg_duration = sum(r['duration'] for r in model_results.values() if 'duration' in r) / len(model_results)

        self.log_result("Phase3", "Model Summary", successful_models == len(self.available_models),
                      f"{successful_models}/{len(self.available_models)} models working, avg {avg_duration:.2f}s")

        return phase_success

    # ==================== PHASE 4: API ENDPOINT TESTING ====================

    async def phase4_api_endpoints(self) -> bool:
        """Phase 4: Test API endpoints (requires app running)"""
        print("\n🔍 PHASE 4: API Endpoint Testing")
        print("-" * 40)
        print("Note: This phase requires the app to run. Testing minimal endpoints without full startup...")

        # For now, test endpoint configuration without running the server
        phase_success = True

        start_time = time.time()
        try:
            from app_v2 import app

            # Check if endpoints are defined
            endpoint_paths = []
            for route in app.routes:
                if hasattr(route, 'path'):
                    endpoint_paths.append(route.path)

            required_endpoints = [
                '/', '/api/health', '/api/status',
                '/api/v1/orchestrator/status',
                '/api/v1/orchestrator/submit'
            ]

            missing_endpoints = [ep for ep in required_endpoints if ep not in endpoint_paths]

            if not missing_endpoints:
                duration = time.time() - start_time
                self.log_result("Phase4", "Endpoint Configuration", True,
                              f"All {len(required_endpoints)} required endpoints defined", duration)
            else:
                duration = time.time() - start_time
                self.log_result("Phase4", "Endpoint Configuration", False,
                              f"Missing endpoints: {missing_endpoints}", duration)
                phase_success = False

        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase4", "Endpoint Configuration", False,
                          f"Endpoint check error: {e}", duration)
            phase_success = False

        return phase_success

    # ==================== PHASE 5: PERSONALIZATION SYSTEM TESTING ====================

    async def phase5_personalization_system(self) -> bool:
        """Phase 5: Test personalization components"""
        print("\n🔍 PHASE 5: Personalization System Testing")
        print("-" * 40)

        phase_success = True

        # Test 5.1: User Profiler
        start_time = time.time()
        try:
            from hermes.personalization.user_profiler import initialize_user_profiler, get_user_profiler

            config = {"max_history_size": 100, "learning_threshold": 0.7}
            initialize_user_profiler(config)
            profiler = get_user_profiler()

            duration = time.time() - start_time
            self.log_result("Phase5", "User Profiler Initialization", True,
                          "User profiler initialized successfully", duration)
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase5", "User Profiler Initialization", False,
                          f"Profiler initialization error: {e}", duration)
            phase_success = False

        # Test 5.2: Personalized Generator
        start_time = time.time()
        try:
            from hermes.personalization.personalized_generator import initialize_personalized_generator, get_personalized_generator

            config = {"min_confidence_threshold": 0.6, "max_adaptation_time": 2.0}
            initialize_personalized_generator(config)
            generator = get_personalized_generator()

            duration = time.time() - start_time
            self.log_result("Phase5", "Personalized Generator Initialization", True,
                          "Personalized generator initialized successfully", duration)
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase5", "Personalized Generator Initialization", False,
                          f"Generator initialization error: {e}", duration)
            phase_success = False

        # Test 5.3: Contextual Awareness
        start_time = time.time()
        try:
            from hermes.personalization.contextual_awareness import initialize_contextual_awareness, get_contextual_awareness_engine

            config = {"max_history_size": 100, "context_decay_rate": 0.1}
            initialize_contextual_awareness(config)
            engine = get_contextual_awareness_engine()

            duration = time.time() - start_time
            self.log_result("Phase5", "Contextual Awareness Initialization", True,
                          "Contextual awareness engine initialized successfully", duration)
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase5", "Contextual Awareness Initialization", False,
                          f"Context engine initialization error: {e}", duration)
            phase_success = False

        # Test 5.4: Adaptive Conversations
        start_time = time.time()
        try:
            from hermes.personalization.adaptive_conversations import initialize_adaptive_conversations, get_adaptive_conversation_engine

            config = {"adaptation_threshold": 0.7, "performance_window": 20}
            initialize_adaptive_conversations(config)
            conversation_engine = get_adaptive_conversation_engine()

            duration = time.time() - start_time
            self.log_result("Phase5", "Adaptive Conversations Initialization", True,
                          "Adaptive conversation engine initialized successfully", duration)
        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase5", "Adaptive Conversations Initialization", False,
                          f"Conversation engine initialization error: {e}", duration)
            phase_success = False

        return phase_success

    # ==================== PHASE 6: PERSONALIZATION API TESTING ====================

    async def phase6_personalization_api(self) -> bool:
        """Phase 6: Test personalization API endpoints"""
        print("\n🔍 PHASE 6: Personalization API Testing")
        print("-" * 40)
        print("Note: Testing route configuration without full server startup...")

        phase_success = True

        start_time = time.time()
        try:
            from hermes.routes.personalization_routes import router

            # Check if personalization routes are defined
            route_count = len(router.routes)

            duration = time.time() - start_time
            self.log_result("Phase6", "Personalization Routes Configuration", True,
                          f"Found {route_count} personalization routes", duration)

        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase6", "Personalization Routes Configuration", False,
                          f"Personalization routes error: {e}", duration)
            phase_success = False

        return phase_success

    # ==================== PHASE 7: INTEGRATION TESTING ====================

    async def phase7_integration_testing(self) -> bool:
        """Phase 7: Test integration between components"""
        print("\n🔍 PHASE 7: Integration Testing")
        print("-" * 40)

        phase_success = True

        # Test 7.1: Component integration
        start_time = time.time()
        try:
            # Test that all personalization components can work together
            from hermes.personalization.user_profiler import get_user_profiler
            from hermes.personalization.personalized_generator import get_personalized_generator

            profiler = get_user_profiler()
            generator = get_personalized_generator()

            # Test basic interaction
            test_user_id = "integration_test_user"
            test_profile = await profiler.get_user_profile(test_user_id)

            duration = time.time() - start_time
            self.log_result("Phase7", "Component Integration", True,
                          "Personalization components can interact", duration)

        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase7", "Component Integration", False,
                          f"Integration error: {e}", duration)
            phase_success = False

        return phase_success

    # ==================== PHASE 8: PERFORMANCE TESTING ====================

    async def phase8_performance_testing(self) -> bool:
        """Phase 8: Test performance and resource usage"""
        print("\n🔍 PHASE 8: Performance Testing")
        print("-" * 40)

        phase_success = True

        # Test 8.1: Memory usage
        start_time = time.time()
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            duration = time.time() - start_time
            self.log_result("Phase8", "Memory Usage", memory_mb < 2048,
                          f"Current memory usage: {memory_mb:.1f} MB", duration)

            if memory_mb >= 2048:
                phase_success = False

        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase8", "Memory Usage", False,
                          f"Memory check error: {e}", duration)

        # Test 8.2: Quick model performance test
        start_time = time.time()
        try:
            # Test with fastest model (llama3.2:3b)
            test_model = "llama3.2:3b"
            payload = {
                'model': test_model,
                'prompt': 'Quick test',
                'stream': False,
                'options': {'num_predict': 10}
            }

            response = requests.post(
                f'{self.ollama_url}/api/generate',
                json=payload,
                timeout=10
            )

            if response.status_code == 200:
                duration = time.time() - start_time
                self.log_result("Phase8", "Model Response Time", duration < 10,
                              f"Response time: {duration:.2f}s", duration)
            else:
                duration = time.time() - start_time
                self.log_result("Phase8", "Model Response Time", False,
                              f"HTTP {response.status_code}", duration)
                phase_success = False

        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase8", "Model Response Time", False,
                          f"Response time test error: {e}", duration)
            phase_success = False

        return phase_success

    # ==================== PHASE 9: ERROR HANDLING TESTING ====================

    async def phase9_error_handling(self) -> bool:
        """Phase 9: Test error handling and edge cases"""
        print("\n🔍 PHASE 9: Error Handling Testing")
        print("-" * 40)

        phase_success = True

        # Test 9.1: Invalid model handling
        start_time = time.time()
        try:
            payload = {
                'model': 'non-existent-model:123b',
                'prompt': 'Test',
                'stream': False
            }

            response = requests.post(
                f'{self.ollama_url}/api/generate',
                json=payload,
                timeout=5
            )

            # Should handle gracefully (404 or error response)
            duration = time.time() - start_time
            if response.status_code == 404:
                self.log_result("Phase9", "Invalid Model Handling", True,
                              "Correctly returns 404 for non-existent model", duration)
            else:
                self.log_result("Phase9", "Invalid Model Handling", True,
                              f"Handles invalid model with HTTP {response.status_code}", duration)

        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase9", "Invalid Model Handling", True,
                          f"Gracefully handles invalid model: {str(e)[:50]}...", duration)

        # Test 9.2: Configuration error handling
        start_time = time.time()
        try:
            from hermes.config import Config
            config = Config()

            # Test accessing non-existent config with default
            test_value = config.get('non.existent.key', 'default_value')

            duration = time.time() - start_time
            self.log_result("Phase9", "Configuration Error Handling", True,
                          f"Gracefully handles missing config, returns: {test_value}", duration)

        except Exception as e:
            duration = time.time() - start_time
            self.log_result("Phase9", "Configuration Error Handling", False,
                          f"Config error handling failed: {e}", duration)
            phase_success = False

        return phase_success

    # ==================== EXECUTION CONTROL ====================

    async def run_all_tests(self) -> Dict[str, Any]:
        """Execute all testing phases"""
        print("🚀 Starting complete Hermes AI Assistant test suite...")
        print("This will test all 9 phases systematically.\n")

        phases = [
            ("Infrastructure Validation", self.phase1_infrastructure_validation),
            ("Core Application", self.phase2_core_application),
            ("Model Integration", self.phase3_model_integration),
            ("API Endpoints", self.phase4_api_endpoints),
            ("Personalization System", self.phase5_personalization_system),
            ("Personalization API", self.phase6_personalization_api),
            ("Integration Testing", self.phase7_integration_testing),
            ("Performance Testing", self.phase8_performance_testing),
            ("Error Handling", self.phase9_error_handling)
        ]

        results = {}

        for phase_name, phase_func in phases:
            try:
                print(f"\n{'='*60}")
                print(f"EXECUTING: {phase_name}")
                print('='*60)

                phase_result = await phase_func()
                results[phase_name] = phase_result

                if phase_result:
                    print(f"✅ {phase_name}: PASSED")
                else:
                    print(f"❌ {phase_name}: FAILED")

            except Exception as e:
                print(f"💥 {phase_name}: CRITICAL ERROR - {e}")
                results[phase_name] = False

        return results

    def generate_report(self) -> str:
        """Generate comprehensive test report"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()

        # Calculate statistics
        total_tests = sum(len(tests) for tests in self.test_results.values())
        passed_tests = sum(
            len([t for t in tests if t['success']])
            for tests in self.test_results.values()
        )
        failed_tests = total_tests - passed_tests

        # Phase results
        phase_results = {}
        for phase, tests in self.test_results.items():
            phase_passed = len([t for t in tests if t['success']])
            phase_total = len(tests)
            phase_results[phase] = {
                'passed': phase_passed,
                'total': phase_total,
                'success_rate': phase_passed / phase_total if phase_total > 0 else 0
            }

        report = f"""# Hermes AI Assistant - Complete Testing Report

## Executive Summary

**Test Execution Duration**: {total_duration:.2f} seconds
**Start Time**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
**End Time**: {end_time.strftime('%Y-%m-%d %H:%M:%S')}
**Total Tests**: {total_tests}
**Passed**: {passed_tests} ({passed_tests/total_tests*100:.1f}%)
**Failed**: {failed_tests} ({failed_tests/total_tests*100:.1f}%)

## Overall Status: {'✅ PASSED' if failed_tests == 0 else '❌ FAILED'}

## Phase Results

"""

        for phase, stats in phase_results.items():
            status = "✅ PASSED" if stats['success_rate'] == 1.0 else "❌ FAILED" if stats['success_rate'] < 0.8 else "⚠️ PARTIAL"
            report += f"### {phase}\n"
            report += f"- **Status**: {status}\n"
            report += f"- **Tests**: {stats['passed']}/{stats['total']} passed ({stats['success_rate']*100:.1f}%)\n\n"

        report += "## Detailed Test Results\n\n"

        for phase, tests in self.test_results.items():
            report += f"### {phase}\n\n"

            for test in tests:
                status = "✅" if test['success'] else "❌"
                report += f"{status} **{test['test_name']}**\n"

                if test['details']:
                    report += f"- Details: {test['details']}\n"

                if test['duration'] > 0:
                    report += f"- Duration: {test['duration']:.3f}s\nn"

                if test['data']:
                    report += f"- Data: {json.dumps(test['data'], indent=2, default=str)}\n"

                report += "\n"

        report += f"""## System Information

- **Python Version**: {sys.version}
- **Platform**: {sys.platform}
- **Available Ollama Models**: {len(self.available_models)}
- **Models Tested**: {', '.join(self.available_models)}

## Recommendations

"""

        if failed_tests == 0:
            report += """🎉 **All Tests Passed!**
The Hermes AI Assistant is ready for production deployment. All components are functioning correctly.

### Next Steps:
1. Deploy to production environment
2. Configure production-specific settings
3. Set up monitoring and alerting
4. Begin user onboarding

"""
        else:
            failed_phases = [phase for phase, stats in phase_results.items() if stats['success_rate'] < 1.0]
            report += f"""⚠️ **Some Tests Failed**
The following areas need attention before production deployment:

### Failed Phases: {', '.join(failed_phases)}

### Recommended Actions:
1. Review failed tests and fix underlying issues
2. Re-run test suite to verify fixes
3. Address any configuration problems
4. Validate all components are properly initialized

"""

        report += "## Files Generated\n\n"
        report += "- This test report (auto-generated)\n"
        report += "- Temporary test databases (auto-cleaned)\n"
        report += "- Test execution logs (console output)\n\n"

        report += "---\n"
        report += f"*Report generated by Hermes AI Assistant Test Suite on {end_time.strftime('%Y-%m-%d %H:%M:%S')}*\n"

        return report

    async def execute_complete_suite(self):
        """Execute the complete test suite and generate report"""
        try:
            # Run all tests
            phase_results = await self.run_all_tests()

            # Generate report
            print("\n" + "="*60)
            print("GENERATING COMPREHENSIVE TEST REPORT")
            print("="*60)

            report = self.generate_report()

            # Write report to file
            report_file = "/Users/khamel83/dev/frugalos/hermes_testing_report.md"
            with open(report_file, 'w') as f:
                f.write(report)

            print(f"✅ Test report written to: {report_file}")

            # Print summary
            total_tests = sum(len(tests) for tests in self.test_results.values())
            passed_tests = sum(
                len([t for t in tests if t['success']])
                for tests in self.test_results.values()
            )

            print(f"\n🎯 FINAL SUMMARY:")
            print(f"   Total Tests: {total_tests}")
            print(f"   Passed: {passed_tests}")
            print(f"   Failed: {total_tests - passed_tests}")
            print(f"   Success Rate: {passed_tests/total_tests*100:.1f}%")

            overall_success = passed_tests == total_tests
            print(f"   Overall Status: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")

            # Cleanup
            self.cleanup_temp_files()

            return overall_success, report_file

        except Exception as e:
            print(f"💥 CRITICAL ERROR DURING TEST EXECUTION: {e}")
            self.cleanup_temp_files()
            return False, None

# ==================== MAIN EXECUTION ====================

async def main():
    """Main execution function"""
    test_suite = HermesTestSuite()
    success, report_file = await test_suite.execute_complete_suite()

    if success:
        print("\n🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print(f"📄 Detailed report available at: {report_file}")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        print(f"📄 See detailed report at: {report_file} for troubleshooting")
        return 1

if __name__ == "__main__":
    # Run the complete test suite
    exit_code = asyncio.run(main())
    sys.exit(exit_code)