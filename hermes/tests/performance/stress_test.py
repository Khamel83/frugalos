#!/usr/bin/env python3
"""
Stress testing script for Hermes AI Assistant

This script performs comprehensive stress testing including:
- Concurrent user simulation
- Resource usage monitoring
- Performance threshold validation
- Error rate tracking
- Memory leak detection

Usage: python tests/performance/stress_test.py [--host http://localhost:8080] [--duration 300] [--users 100]
"""

import asyncio
import aiohttp
import argparse
import json
import time
import psutil
import threading
import statistics
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any
import random

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

@dataclass
class TestMetrics:
    """Test metrics container"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: List[float] = None
    errors: Dict[str, int] = None

    def __post_init__(self):
        if self.response_times is None:
            self.response_times = []
        if self.errors is None:
            self.errors = {}

class StressTester:
    """Main stress testing class"""

    def __init__(self, base_url: str, duration: int = 300, max_users: int = 100):
        self.base_url = base_url.rstrip('/')
        self.duration = duration
        self.max_users = max_users
        self.metrics = TestMetrics()
        self.start_time = None
        self.end_time = None
        self.system_metrics = []
        self.active_users = 0
        self.running = True

    async def create_conversation(self, session: aiohttp.ClientSession, user_id: str) -> str:
        """Create a new conversation"""
        url = f"{self.base_url}/api/orchestrator/conversation"
        data = {
            "context": {
                "user_id": user_id,
                "session_type": random.choice(["general", "technical", "creative", "analytical"]),
                "domain": random.choice(["software_development", "business", "analytics", "research"]),
                "preferences": {
                    "response_style": random.choice(["concise", "detailed"]),
                    "language": "en"
                }
            }
        }

        try:
            async with session.post(url, json=data) as response:
                if response.status == 201:
                    result = await response.json()
                    return result["data"]["conversation_id"]
                else:
                    raise Exception(f"Failed to create conversation: {response.status}")
        except Exception as e:
            raise Exception(f"Conversation creation failed: {str(e)}")

    async def execute_task(self, session: aiohttp.ClientSession, conversation_id: str) -> Dict[str, Any]:
        """Execute a task"""
        url = f"{self.base_url}/api/orchestrator/execute"

        tasks = [
            "Analyze user behavior patterns",
            "Generate performance metrics report",
            "Optimize database queries",
            "Create security audit report",
            "Generate cost optimization suggestions",
            "Summarize system performance"
        ]

        data = {
            "conversation_id": conversation_id,
            "idea": random.choice(tasks),
            "context": {
                "domain": random.choice(["analytics", "monitoring", "security", "optimization"]),
                "priority": random.choice(["low", "normal", "high", "urgent"]),
                "constraints": {
                    "max_execution_time": random.choice([120, 300, 600]),
                    "budget_cents": random.choice([25, 50, 100, 200])
                }
            }
        }

        try:
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Task execution failed: {response.status}")
        except Exception as e:
            raise Exception(f"Task execution failed: {str(e)}")

    async def get_system_status(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Get system status"""
        url = f"{self.base_url}/api/orchestrator/status?include_metrics=true"

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"System status check failed: {response.status}")
        except Exception as e:
            raise Exception(f"System status check failed: {str(e)}")

    async def user_simulation(self, user_id: int, session: aiohttp.ClientSession):
        """Simulate a single user's behavior"""
        try:
            # Create conversation
            conversation_id = await self.create_conversation(session, f"stress_user_{user_id}")

            # Perform tasks until test duration is reached
            while self.running:
                start_time = time.time()

                try:
                    # Execute task
                    await self.execute_task(session, conversation_id)

                    response_time = (time.time() - start_time) * 1000
                    self.metrics.response_times.append(response_time)
                    self.metrics.successful_requests += 1

                except Exception as e:
                    self.metrics.failed_requests += 1
                    error_type = type(e).__name__
                    self.metrics.errors[error_type] = self.metrics.errors.get(error_type, 0) + 1

                self.metrics.total_requests += 1

                # Wait between requests
                await asyncio.sleep(random.uniform(1, 5))

        except Exception as e:
            print(f"User {user_id} simulation failed: {str(e)}")
            self.metrics.failed_requests += 1
            error_type = type(e).__name__
            self.metrics.errors[error_type] = self.metrics.errors.get(error_type, 0) + 1

    def monitor_system_resources(self):
        """Monitor system resources during stress test"""
        while self.running:
            try:
                # CPU and memory usage
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')

                # Network stats
                network = psutil.net_io_counters()

                system_metric = {
                    'timestamp': time.time(),
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_gb': memory.used / (1024**3),
                    'memory_total_gb': memory.total / (1024**3),
                    'disk_percent': (disk.used / disk.total) * 100,
                    'network_bytes_sent': network.bytes_sent,
                    'network_bytes_recv': network.bytes_recv,
                    'active_users': self.active_users
                }

                self.system_metrics.append(system_metric)

                # Check for resource thresholds
                if cpu_percent > 90:
                    print(f"WARNING: High CPU usage: {cpu_percent}%")

                if memory.percent > 85:
                    print(f"WARNING: High memory usage: {memory.percent}%")

                if (disk.used / disk.total) * 100 > 90:
                    print(f"WARNING: High disk usage: {(disk.used / disk.total) * 100}%")

            except Exception as e:
                print(f"System monitoring error: {str(e)}")

            time.sleep(5)

    async def run_stress_test(self):
        """Run the main stress test"""
        print(f"Starting stress test: {self.max_users} users for {self.duration} seconds")
        print(f"Target URL: {self.base_url}")

        self.start_time = time.time()
        self.running = True

        # Start system monitoring
        monitor_thread = threading.Thread(target=self.monitor_system_resources)
        monitor_thread.daemon = True
        monitor_thread.start()

        # Create aiohttp session
        timeout = aiohttp.ClientTimeout(total=60)
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)

        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            # Start user simulations gradually
            tasks = []

            for i in range(self.max_users):
                # Ramp up users gradually
                if i > 0:
                    await asyncio.sleep(0.1)

                self.active_users += 1
                task = asyncio.create_task(self.user_simulation(i + 1, session))
                tasks.append(task)

            # Run for specified duration
            await asyncio.sleep(self.duration)

            # Stop the test
            self.running = False
            self.end_time = time.time()

            # Wait for tasks to complete
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=30)
            except asyncio.TimeoutError:
                print("Warning: Some tasks did not complete within timeout")

            self.active_users = 0

    def generate_report(self):
        """Generate comprehensive stress test report"""
        if not self.start_time or not self.end_time:
            print("No test data available")
            return

        duration = self.end_time - self.start_time

        print("\n" + "="*60)
        print("STRESS TEST REPORT")
        print("="*60)

        # Basic metrics
        print(f"\nTest Duration: {duration:.2f} seconds")
        print(f"Max Concurrent Users: {self.max_users}")
        print(f"Total Requests: {self.metrics.total_requests}")
        print(f"Successful Requests: {self.metrics.successful_requests}")
        print(f"Failed Requests: {self.metrics.failed_requests}")

        if self.metrics.total_requests > 0:
            success_rate = (self.metrics.successful_requests / self.metrics.total_requests) * 100
            print(f"Success Rate: {success_rate:.2f}%")

            # Request rate
            requests_per_second = self.metrics.total_requests / duration
            print(f"Requests per Second: {requests_per_second:.2f}")

            # Response time statistics
            if self.metrics.response_times:
                avg_response_time = statistics.mean(self.metrics.response_times)
                median_response_time = statistics.median(self.metrics.response_times)
                p95_response_time = sorted(self.metrics.response_times)[int(len(self.metrics.response_times) * 0.95)]
                max_response_time = max(self.metrics.response_times)

                print(f"\nResponse Time Statistics:")
                print(f"  Average: {avg_response_time:.2f}ms")
                print(f"  Median: {median_response_time:.2f}ms")
                print(f"  95th Percentile: {p95_response_time:.2f}ms")
                print(f"  Maximum: {max_response_time:.2f}ms")

                # Response time distribution
                under_1s = len([t for t in self.metrics.response_times if t < 1000])
                under_2s = len([t for t in self.metrics.response_times if t < 2000])
                under_5s = len([t for t in self.metrics.response_times if t < 5000])

                print(f"\nResponse Time Distribution:")
                print(f"  < 1s: {under_1s} ({(under_1s/len(self.metrics.response_times))*100:.1f}%)")
                print(f"  < 2s: {under_2s} ({(under_2s/len(self.metrics.response_times))*100:.1f}%)")
                print(f"  < 5s: {under_5s} ({(under_5s/len(self.metrics.response_times))*100:.1f}%)")

        # Error analysis
        if self.metrics.errors:
            print(f"\nError Analysis:")
            for error_type, count in self.metrics.errors.items():
                error_rate = (count / self.metrics.total_requests) * 100
                print(f"  {error_type}: {count} ({error_rate:.2f}%)")

        # System resource metrics
        if self.system_metrics:
            print(f"\nSystem Resource Metrics:")

            cpu_values = [m['cpu_percent'] for m in self.system_metrics]
            memory_values = [m['memory_percent'] for m in self.system_metrics]

            print(f"  CPU Usage:")
            print(f"    Average: {statistics.mean(cpu_values):.2f}%")
            print(f"    Maximum: {max(cpu_values):.2f}%")
            print(f"    Minimum: {min(cpu_values):.2f}%")

            print(f"  Memory Usage:")
            print(f"    Average: {statistics.mean(memory_values):.2f}%")
            print(f"    Maximum: {max(memory_values):.2f}%")
            print(f"    Minimum: {min(memory_values):.2f}%")

            # Peak concurrent users
            peak_users = max([m['active_users'] for m in self.system_metrics])
            print(f"  Peak Concurrent Users: {peak_users}")

        # Performance assessment
        print(f"\nPerformance Assessment:")

        if self.metrics.total_requests > 0:
            success_rate = (self.metrics.successful_requests / self.metrics.total_requests) * 100

            if success_rate >= 99:
                print("  ✓ Excellent reliability (>99% success rate)")
            elif success_rate >= 95:
                print("  ✓ Good reliability (>95% success rate)")
            elif success_rate >= 90:
                print("  ⚠ Acceptable reliability (>90% success rate)")
            else:
                print("  ✗ Poor reliability (<90% success rate)")

            if self.metrics.response_times:
                avg_response_time = statistics.mean(self.metrics.response_times)

                if avg_response_time < 1000:
                    print("  ✓ Excellent response time (<1s average)")
                elif avg_response_time < 2000:
                    print("  ✓ Good response time (<2s average)")
                elif avg_response_time < 5000:
                    print("  ⚠ Acceptable response time (<5s average)")
                else:
                    print("  ✗ Poor response time (>5s average)")

            requests_per_second = self.metrics.total_requests / duration
            if requests_per_second > 50:
                print("  ✓ Excellent throughput (>50 RPS)")
            elif requests_per_second > 20:
                print("  ✓ Good throughput (>20 RPS)")
            elif requests_per_second > 10:
                print("  ⚠ Acceptable throughput (>10 RPS)")
            else:
                print("  ✗ Poor throughput (<10 RPS)")

        # Recommendations
        print(f"\nRecommendations:")

        if self.metrics.errors:
            most_common_error = max(self.metrics.errors.items(), key=lambda x: x[1])
            print(f"  - Investigate {most_common_error[0]} errors ({most_common_error[1]} occurrences)")

        if self.system_metrics:
            avg_cpu = statistics.mean([m['cpu_percent'] for m in self.system_metrics])
            avg_memory = statistics.mean([m['memory_percent'] for m in self.system_metrics])

            if avg_cpu > 80:
                print("  - Consider scaling CPU resources")

            if avg_memory > 80:
                print("  - Consider scaling memory resources or investigating memory leaks")

        if self.metrics.response_times:
            p95_response_time = sorted(self.metrics.response_times)[int(len(self.metrics.response_times) * 0.95)]
            if p95_response_time > 5000:
                print("  - Optimize slow endpoints to improve 95th percentile response time")

        if self.metrics.total_requests > 0 and (self.metrics.successful_requests / self.metrics.total_requests) < 95:
            print("  - Improve error handling and retry mechanisms")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Hermes AI Assistant Stress Test')
    parser.add_argument('--host', default='http://localhost:8080',
                       help='Target host URL (default: http://localhost:8080)')
    parser.add_argument('--duration', type=int, default=300,
                       help='Test duration in seconds (default: 300)')
    parser.add_argument('--users', type=int, default=100,
                       help='Maximum concurrent users (default: 100)')

    args = parser.parse_args()

    # Validate target URL
    if not args.host.startswith('http'):
        print("Error: Host URL must start with http:// or https://")
        sys.exit(1)

    print("Hermes AI Assistant Stress Testing Tool")
    print("=======================================")

    # Create and run stress test
    tester = StressTester(args.host, args.duration, args.users)

    try:
        asyncio.run(tester.run_stress_test())
        tester.generate_report()
    except KeyboardInterrupt:
        print("\nStress test interrupted by user")
        tester.running = False
        tester.end_time = time.time()
        tester.generate_report()
    except Exception as e:
        print(f"Stress test failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()