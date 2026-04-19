"""
Advanced load testing framework for the Hermes AI Assistant.

This module provides comprehensive load testing capabilities including:
- Multi-scenario testing with realistic user behavior
- Progressive load ramping and stress testing
- Performance metrics collection and analysis
- Automated bottleneck identification
- Comparative testing and regression detection
"""

import asyncio
import time
import json
import random
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path

import aiohttp
import httpx
import psutil
import numpy as np
from locust import HttpUser, task, between, events
import matplotlib.pyplot as plt
import seaborn as sns
from prometheus_client import CollectorRegistry, Gauge, Histogram

logger = logging.getLogger(__name__)


@dataclass
class LoadTestScenario:
    """Load test scenario definition."""
    name: str
    description: str
    weight: float = 1.0
    think_time_range: Tuple[float, float] = (1.0, 3.0)
    requests: List[Dict[str, Any]] = field(default_factory=list)
    ramp_up_time: int = 60
    duration: int = 300
    cooldown_time: int = 30


@dataclass
class RequestMetrics:
    """Individual request performance metrics."""
    url: str
    method: str
    status_code: int
    response_time: float
    response_size: int
    timestamp: datetime
    user_id: str
    scenario: str
    error: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class TestResults:
    """Load test results summary."""
    scenario_name: str
    test_duration: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    requests_per_second: float
    average_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    errors: List[Dict[str, Any]]
    throughput_by_endpoint: Dict[str, float]
    error_rate_by_endpoint: Dict[str, float]
    cpu_usage: List[float]
    memory_usage: List[float]
    concurrent_users: int


class LoadTestUser:
    """Simulated load test user with realistic behavior."""

    def __init__(self, user_id: str, session: httpx.AsyncClient,
                 scenarios: List[LoadTestScenario], base_url: str):
        self.user_id = user_id
        self.session = session
        self.scenarios = scenarios
        self.base_url = base_url
        self.request_history: List[RequestMetrics] = []
        self.is_running = False

    async def run_scenario(self, scenario: LoadTestScenario):
        """Execute a single test scenario."""
        start_time = time.time()
        while time.time() - start_time < scenario.duration and self.is_running:
            # Choose request based on weights
            request_spec = self._choose_request(scenario)

            # Execute request
            metrics = await self._execute_request(request_spec, scenario.name)
            if metrics:
                self.request_history.append(metrics)

            # Think time
            think_time = random.uniform(*scenario.think_time_range)
            await asyncio.sleep(think_time)

    def _choose_request(self, scenario: LoadTestScenario) -> Dict[str, Any]:
        """Choose a request based on scenario weights."""
        requests = scenario.requests
        weights = [req.get('weight', 1.0) for req in requests]
        return random.choices(requests, weights=weights)[0]

    async def _execute_request(self, request_spec: Dict[str, Any], scenario_name: str) -> Optional[RequestMetrics]:
        """Execute a single HTTP request."""
        url = self.base_url + request_spec['path']
        method = request_spec.get('method', 'GET')
        headers = request_spec.get('headers', {})
        params = request_spec.get('params', {})
        data = request_spec.get('data', {})
        json_data = request_spec.get('json', {})

        start_time = time.time()
        error = None
        status_code = 0
        response_size = 0
        response_headers = {}

        try:
            if method.upper() == 'GET':
                response = await self.session.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == 'POST':
                if json_data:
                    response = await self.session.post(url, headers=headers, json=json_data, timeout=30)
                else:
                    response = await self.session.post(url, headers=headers, data=data, timeout=30)
            elif method.upper() == 'PUT':
                response = await self.session.put(url, headers=headers, json=json_data, timeout=30)
            elif method.upper() == 'DELETE':
                response = await self.session.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            status_code = response.status_code
            response_size = len(response.content)
            response_headers = dict(response.headers)

            # Check for HTTP errors
            if 400 <= status_code < 600:
                error = f"HTTP {status_code}: {response.text[:200]}"

        except Exception as e:
            error = str(e)
            logger.error(f"Request failed: {error}")

        response_time = time.time() - start_time

        return RequestMetrics(
            url=url,
            method=method,
            status_code=status_code,
            response_time=response_time,
            response_size=response_size,
            timestamp=datetime.utcnow(),
            user_id=self.user_id,
            scenario=scenario_name,
            error=error,
            headers=response_headers
        )


class ProgressiveLoadTester:
    """Progressive load testing with automatic ramp-up and bottleneck detection."""

    def __init__(self, base_url: str, max_users: int = 100):
        self.base_url = base_url
        self.max_users = max_users
        self.active_users: List[LoadTestUser] = []
        self.test_results: List[TestResults] = []
        self.system_metrics: Dict[str, List[float]] = defaultdict(list)
        self.is_testing = False

    async def run_progressive_test(self, scenarios: List[LoadTestScenario],
                                  step_users: int = 10, step_duration: int = 120) -> List[TestResults]:
        """Run progressive load test with increasing user counts."""
        self.is_testing = True
        results = []

        try:
            for current_users in range(step_users, self.max_users + 1, step_users):
                logger.info(f"Running test with {current_users} concurrent users")

                # Run test for current user count
                result = await self.run_test_with_users(scenarios, current_users, step_duration)
                results.append(result)
                self.test_results.append(result)

                # Check if we've hit performance degradation
                if self._should_stop_testing(result, results):
                    logger.warning(f"Performance degradation detected at {current_users} users. Stopping test.")
                    break

                # Cooldown period
                logger.info(f"Cooldown period for {step_duration // 2} seconds")
                await asyncio.sleep(step_duration // 2)

        finally:
            self.is_testing = False
            await self.cleanup_users()

        return results

    async def run_test_with_users(self, scenarios: List[LoadTestScenario],
                                 user_count: int, duration: int) -> TestResults:
        """Run test with specific number of users."""
        start_time = time.time()

        # Create users
        users = []
        for i in range(user_count):
            session = httpx.AsyncClient(timeout=httpx.Timeout(30.0))
            user = LoadTestUser(f"user_{i}", session, scenarios, self.base_url)
            users.append(user)
            self.active_users.append(user)

        # Start system metrics collection
        metrics_task = asyncio.create_task(self._collect_system_metrics(duration))

        # Start users
        user_tasks = []
        for user in users:
            user.is_running = True
            # Choose scenario based on weights
            scenario_weights = [s.weight for s in scenarios]
            chosen_scenario = random.choices(scenarios, weights=scenario_weights)[0]
            task = asyncio.create_task(user.run_scenario(chosen_scenario))
            user_tasks.append(task)

        # Wait for test duration
        await asyncio.sleep(duration)

        # Stop users
        for user in users:
            user.is_running = False

        # Wait for all user tasks to complete
        await asyncio.gather(*user_tasks, return_exceptions=True)

        # Stop metrics collection
        metrics_task.cancel()
        try:
            await metrics_task
        except asyncio.CancelledError:
            pass

        test_duration = time.time() - start_time

        # Collect all request metrics
        all_metrics = []
        for user in users:
            all_metrics.extend(user.request_history)

        # Analyze results
        result = self._analyze_results(all_metrics, scenarios[0].name, test_duration, user_count)
        result.cpu_usage = self.system_metrics['cpu']
        result.memory_usage = self.system_metrics['memory']

        # Cleanup users
        await self.cleanup_users()

        return result

    async def _collect_system_metrics(self, duration: int):
        """Collect system performance metrics during test."""
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.system_metrics['cpu'].append(cpu_percent)

                # Memory usage
                memory = psutil.virtual_memory()
                self.system_metrics['memory'].append(memory.percent)

                # Network I/O
                network = psutil.net_io_counters()
                self.system_metrics['network_bytes_sent'].append(network.bytes_sent)
                self.system_metrics['network_bytes_recv'].append(network.bytes_recv)

            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")

            await asyncio.sleep(1)

    def _analyze_results(self, metrics: List[RequestMetrics], scenario_name: str,
                        test_duration: float, concurrent_users: int) -> TestResults:
        """Analyze load test results."""
        if not metrics:
            return TestResults(
                scenario_name=scenario_name,
                test_duration=test_duration,
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                requests_per_second=0.0,
                average_response_time=0.0,
                p50_response_time=0.0,
                p95_response_time=0.0,
                p99_response_time=0.0,
                min_response_time=0.0,
                max_response_time=0.0,
                errors=[],
                throughput_by_endpoint={},
                error_rate_by_endpoint={},
                cpu_usage=[],
                memory_usage=[],
                concurrent_users=concurrent_users
            )

        # Separate successful and failed requests
        successful = [m for m in metrics if not m.error and 200 <= m.status_code < 400]
        failed = [m for m in metrics if m.error or 400 <= m.status_code]

        # Response time statistics
        response_times = [m.response_time for m in successful]
        if response_times:
            avg_response_time = statistics.mean(response_times)
            p50_response_time = np.percentile(response_times, 50)
            p95_response_time = np.percentile(response_times, 95)
            p99_response_time = np.percentile(response_times, 99)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
        else:
            avg_response_time = p50_response_time = p95_response_time = p99_response_time = 0.0
            min_response_time = max_response_time = 0.0

        # Calculate throughput
        requests_per_second = len(successful) / test_duration

        # Throughput by endpoint
        endpoint_stats = defaultdict(list)
        for m in successful:
            endpoint = f"{m.method} {m.url}"
            endpoint_stats[endpoint].append(m.response_time)

        throughput_by_endpoint = {}
        for endpoint, times in endpoint_stats.items():
            throughput_by_endpoint[endpoint] = len(times) / test_duration

        # Error analysis
        error_counts = defaultdict(int)
        error_details = []
        for m in failed:
            error_key = f"{m.method} {m.url}"
            error_counts[error_key] += 1
            if m.error:
                error_details.append({
                    'url': m.url,
                    'method': m.method,
                    'error': m.error,
                    'status_code': m.status_code,
                    'timestamp': m.timestamp.isoformat()
                })

        # Error rate by endpoint
        total_requests_by_endpoint = defaultdict(int)
        for m in metrics:
            endpoint = f"{m.method} {m.url}"
            total_requests_by_endpoint[endpoint] += 1

        error_rate_by_endpoint = {}
        for endpoint, total in total_requests_by_endpoint.items():
            errors = error_counts.get(endpoint, 0)
            error_rate_by_endpoint[endpoint] = (errors / total * 100) if total > 0 else 0

        return TestResults(
            scenario_name=scenario_name,
            test_duration=test_duration,
            total_requests=len(metrics),
            successful_requests=len(successful),
            failed_requests=len(failed),
            requests_per_second=requests_per_second,
            average_response_time=avg_response_time,
            p50_response_time=p50_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            errors=error_details,
            throughput_by_endpoint=throughput_by_endpoint,
            error_rate_by_endpoint=error_rate_by_endpoint,
            cpu_usage=[],
            memory_usage=[],
            concurrent_users=concurrent_users
        )

    def _should_stop_testing(self, current_result: TestResults, all_results: List[TestResults]) -> bool:
        """Determine if testing should stop due to performance degradation."""
        if len(all_results) < 2:
            return False

        # Check response time degradation
        prev_result = all_results[-2]
        if (current_result.p95_response_time > prev_result.p95_response_time * 1.5 and
            current_result.p95_response_time > 2.0):
            return True

        # Check error rate increase
        if (current_result.failed_requests / current_result.total_requests > 0.05 and
            current_result.failed_requests / current_result.total_requests >
            prev_result.failed_requests / prev_result.total_requests * 2):
            return True

        # Check resource saturation
        if current_result.cpu_usage and statistics.mean(current_result.cpu_usage) > 90:
            return True

        if current_result.memory_usage and statistics.mean(current_result.memory_usage) > 90:
            return True

        return False

    async def cleanup_users(self):
        """Clean up active users and sessions."""
        for user in self.active_users:
            try:
                await user.session.aclose()
            except Exception as e:
                logger.error(f"Error closing user session: {e}")
        self.active_users.clear()


class LoadTestAnalyzer:
    """Analyzes load test results and generates reports."""

    def __init__(self, output_dir: Path = Path("load_test_results")):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

    def generate_comprehensive_report(self, results: List[TestResults]) -> Dict[str, Any]:
        """Generate comprehensive load test report."""
        if not results:
            return {}

        # Performance trends
        performance_trends = self._analyze_performance_trends(results)

        # Bottleneck analysis
        bottlenecks = self._identify_bottlenecks(results)

        # Capacity analysis
        capacity_analysis = self._analyze_capacity(results)

        # Generate visualizations
        self._generate_visualizations(results)

        # Create summary
        summary = {
            'test_summary': {
                'total_scenarios': len(set(r.scenario_name for r in results)),
                'max_users_tested': max(r.concurrent_users for r in results),
                'max_rps_achieved': max(r.requests_per_second for r in results),
                'best_p95_response_time': min(r.p95_response_time for r in results),
                'average_error_rate': statistics.mean([r.failed_requests / r.total_requests for r in results if r.total_requests > 0])
            },
            'performance_trends': performance_trends,
            'bottlenecks': bottlenecks,
            'capacity_analysis': capacity_analysis,
            'detailed_results': [self._result_to_dict(r) for r in results],
            'recommendations': self._generate_recommendations(results)
        }

        # Save report
        report_path = self.output_dir / f"load_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        return summary

    def _analyze_performance_trends(self, results: List[TestResults]) -> Dict[str, Any]:
        """Analyze performance trends across different user loads."""
        # Sort by concurrent users
        sorted_results = sorted(results, key=lambda r: r.concurrent_users)

        user_counts = [r.concurrent_users for r in sorted_results]
        rps_values = [r.requests_per_second for r in sorted_results]
        p95_response_times = [r.p95_response_time for r in sorted_results]
        error_rates = [r.failed_requests / r.total_requests if r.total_requests > 0 else 0 for r in sorted_results]

        return {
            'throughput_scaling': {
                'user_counts': user_counts,
                'rps_values': rps_values,
                'scaling_efficiency': self._calculate_scaling_efficiency(user_counts, rps_values)
            },
            'response_time_degradation': {
                'user_counts': user_counts,
                'p95_response_times': p95_response_times,
                'degradation_point': self._find_degradation_point(user_counts, p95_response_times)
            },
            'error_rate_trends': {
                'user_counts': user_counts,
                'error_rates': error_rates,
                'reliability_threshold': self._find_reliability_threshold(user_counts, error_rates)
            }
        }

    def _identify_bottlenecks(self, results: List[TestResults]) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks."""
        bottlenecks = []

        for result in results:
            # Response time bottlenecks
            if result.p95_response_time > 2.0:
                bottlenecks.append({
                    'type': 'response_time',
                    'severity': 'high' if result.p95_response_time > 5.0 else 'medium',
                    'users': result.concurrent_users,
                    'metric': f"P95 response time: {result.p95_response_time:.3f}s",
                    'recommendation': "Investigate slow endpoints and database queries"
                })

            # Error rate bottlenecks
            error_rate = result.failed_requests / result.total_requests if result.total_requests > 0 else 0
            if error_rate > 0.05:
                bottlenecks.append({
                    'type': 'error_rate',
                    'severity': 'high' if error_rate > 0.1 else 'medium',
                    'users': result.concurrent_users,
                    'metric': f"Error rate: {error_rate:.2%}",
                    'recommendation': "Investigate application errors and resource limits"
                })

            # CPU bottlenecks
            if result.cpu_usage and statistics.mean(result.cpu_usage) > 85:
                bottlenecks.append({
                    'type': 'cpu_utilization',
                    'severity': 'high' if statistics.mean(result.cpu_usage) > 95 else 'medium',
                    'users': result.concurrent_users,
                    'metric': f"Average CPU: {statistics.mean(result.cpu_usage):.1f}%",
                    'recommendation': "Scale horizontally or optimize CPU-intensive operations"
                })

            # Memory bottlenecks
            if result.memory_usage and statistics.mean(result.memory_usage) > 85:
                bottlenecks.append({
                    'type': 'memory_utilization',
                    'severity': 'high' if statistics.mean(result.memory_usage) > 95 else 'medium',
                    'users': result.concurrent_users,
                    'metric': f"Average memory: {statistics.mean(result.memory_usage):.1f}%",
                    'recommendation': "Investigate memory leaks or increase memory allocation"
                })

        return bottlenecks

    def _analyze_capacity(self, results: List[TestResults]) -> Dict[str, Any]:
        """Analyze system capacity and limits."""
        if not results:
            return {}

        # Find maximum sustainable load
        sustainable_results = [r for r in results if r.failed_requests / r.total_requests < 0.01 if r.total_requests > 0]
        max_sustainable_users = max([r.concurrent_users for r in sustainable_results]) if sustainable_results else 0

        # Calculate performance at different loads
        performance_by_load = {}
        for result in results:
            performance_by_load[result.concurrent_users] = {
                'rps': result.requests_per_second,
                'p95_response_time': result.p95_response_time,
                'error_rate': result.failed_requests / result.total_requests if result.total_requests > 0 else 0
            }

        return {
            'max_sustainable_users': max_sustainable_users,
            'max_sustainable_rps': max([r.requests_per_second for r in sustainable_results]) if sustainable_results else 0,
            'performance_by_load': performance_by_load,
            'recommended_capacity': int(max_sustainable_users * 0.8) if max_sustainable_users > 0 else 0
        }

    def _generate_visualizations(self, results: List[TestResults]):
        """Generate performance visualization charts."""
        if not results:
            return

        # Sort by concurrent users
        sorted_results = sorted(results, key=lambda r: r.concurrent_users)
        user_counts = [r.concurrent_users for r in sorted_results]

        # Create subplots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        # Requests per second
        rps_values = [r.requests_per_second for r in sorted_results]
        ax1.plot(user_counts, rps_values, 'b-o')
        ax1.set_xlabel('Concurrent Users')
        ax1.set_ylabel('Requests per Second')
        ax1.set_title('Throughput Scaling')
        ax1.grid(True)

        # P95 Response time
        p95_times = [r.p95_response_time for r in sorted_results]
        ax2.plot(user_counts, p95_times, 'r-o')
        ax2.set_xlabel('Concurrent Users')
        ax2.set_ylabel('P95 Response Time (s)')
        ax2.set_title('Response Time Trend')
        ax2.grid(True)

        # Error rate
        error_rates = [r.failed_requests / r.total_requests if r.total_requests > 0 else 0 for r in sorted_results]
        ax3.plot(user_counts, [e * 100 for e in error_rates], 'g-o')
        ax3.set_xlabel('Concurrent Users')
        ax3.set_ylabel('Error Rate (%)')
        ax3.set_title('Error Rate Trend')
        ax3.grid(True)

        # System resource usage
        if results[0].cpu_usage:
            avg_cpu = [statistics.mean(r.cpu_usage) if r.cpu_usage else 0 for r in sorted_results]
            avg_memory = [statistics.mean(r.memory_usage) if r.memory_usage else 0 for r in sorted_results]
            ax4.plot(user_counts, avg_cpu, 'm-o', label='CPU %')
            ax4.plot(user_counts, avg_memory, 'c-o', label='Memory %')
            ax4.set_xlabel('Concurrent Users')
            ax4.set_ylabel('Resource Usage (%)')
            ax4.set_title('System Resource Usage')
            ax4.legend()
            ax4.grid(True)

        plt.tight_layout()
        chart_path = self.output_dir / f"performance_charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()

    def _calculate_scaling_efficiency(self, user_counts: List[int], rps_values: List[float]) -> float:
        """Calculate scaling efficiency percentage."""
        if len(user_counts) < 2:
            return 100.0

        # Calculate theoretical linear scaling
        theoretical_rps = [rps_values[0] * (user_counts[i] / user_counts[0]) for i in range(len(user_counts))]

        # Calculate actual vs theoretical ratio
        efficiency_ratios = [rps_values[i] / theoretical_rps[i] for i in range(len(user_counts)) if theoretical_rps[i] > 0]

        return statistics.mean(efficiency_ratios) * 100 if efficiency_ratios else 100.0

    def _find_degradation_point(self, user_counts: List[int], response_times: List[float]) -> Optional[int]:
        """Find the point where response times start degrading significantly."""
        if len(response_times) < 3:
            return None

        # Look for significant increase in response time
        for i in range(1, len(response_times)):
            if response_times[i] > response_times[0] * 2:  # 2x degradation
                return user_counts[i]

        return None

    def _find_reliability_threshold(self, user_counts: List[int], error_rates: List[float]) -> Optional[int]:
        """Find the point where error rates become unacceptable."""
        for i, error_rate in enumerate(error_rates):
            if error_rate > 0.01:  # 1% error rate threshold
                return user_counts[i]
        return None

    def _result_to_dict(self, result: TestResults) -> Dict[str, Any]:
        """Convert TestResults to dictionary."""
        return {
            'scenario_name': result.scenario_name,
            'test_duration': result.test_duration,
            'total_requests': result.total_requests,
            'successful_requests': result.successful_requests,
            'failed_requests': result.failed_requests,
            'requests_per_second': result.requests_per_second,
            'average_response_time': result.average_response_time,
            'p50_response_time': result.p50_response_time,
            'p95_response_time': result.p95_response_time,
            'p99_response_time': result.p99_response_time,
            'min_response_time': result.min_response_time,
            'max_response_time': result.max_response_time,
            'error_rate_percent': (result.failed_requests / result.total_requests * 100) if result.total_requests > 0 else 0,
            'concurrent_users': result.concurrent_users,
            'top_errors': result.errors[:5] if result.errors else []
        }

    def _generate_recommendations(self, results: List[TestResults]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []

        if not results:
            return recommendations

        # Analyze overall performance
        avg_p95 = statistics.mean([r.p95_response_time for r in results])
        max_rps = max([r.requests_per_second for r in results])
        avg_error_rate = statistics.mean([r.failed_requests / r.total_requests for r in results if r.total_requests > 0])

        # Response time recommendations
        if avg_p95 > 1.0:
            recommendations.append("Consider optimizing database queries and implementing caching to reduce response times")

        # Throughput recommendations
        if max_rps < 100:
            recommendations.append("Consider horizontal scaling to improve throughput capacity")

        # Error rate recommendations
        if avg_error_rate > 0.02:
            recommendations.append("Investigate and fix application errors to improve reliability")

        # Resource usage recommendations
        high_cpu_results = [r for r in results if r.cpu_usage and statistics.mean(r.cpu_usage) > 80]
        if high_cpu_results:
            recommendations.append("Optimize CPU-intensive operations or scale horizontally")

        high_memory_results = [r for r in results if r.memory_usage and statistics.mean(r.memory_usage) > 80]
        if high_memory_results:
            recommendations.append("Investigate memory usage patterns and optimize memory management")

        return recommendations


# Predefined load test scenarios
DEFAULT_SCENARIOS = [
    LoadTestScenario(
        name="api_health_check",
        description="Basic health check endpoint",
        weight=0.1,
        think_time_range=(0.5, 1.0),
        requests=[
            {"path": "/health", "method": "GET", "weight": 1.0}
        ]
    ),
    LoadTestScenario(
        name="chat_completion",
        description="AI chat completion requests",
        weight=0.6,
        think_time_range=(2.0, 5.0),
        requests=[
            {
                "path": "/api/v1/chat/completions",
                "method": "POST",
                "weight": 1.0,
                "json": {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Hello, how are you?"}],
                    "max_tokens": 100
                }
            }
        ]
    ),
    LoadTestScenario(
        name="authentication",
        description="User authentication flows",
        weight=0.2,
        think_time_range=(1.0, 3.0),
        requests=[
            {"path": "/api/v1/auth/login", "method": "POST", "weight": 0.7},
            {"path": "/api/v1/auth/refresh", "method": "POST", "weight": 0.3}
        ]
    ),
    LoadTestScenario(
        name="file_operations",
        description="File upload and download operations",
        weight=0.1,
        think_time_range=(3.0, 8.0),
        requests=[
            {"path": "/api/v1/files/upload", "method": "POST", "weight": 0.6},
            {"path": "/api/v1/files/list", "method": "GET", "weight": 0.4}
        ]
    )
]


# Global load testing instances
progressive_tester: Optional[ProgressiveLoadTester] = None
test_analyzer: Optional[LoadTestAnalyzer] = None