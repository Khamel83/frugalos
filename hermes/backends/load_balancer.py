"""
Backend Load Balancing
Intelligent backend selection and load distribution
"""

import logging
import random
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict

from ..config import Config
from ..database import Database
from ..logger import get_logger
from .health_monitor import BackendHealthMonitor, HealthStatus

logger = get_logger('backends.load_balancer')

class LoadBalancingStrategy(Enum):
    """Load balancing strategies"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    FASTEST_RESPONSE = "fastest_response"
    WEIGHTED_RANDOM = "weighted_random"
    COST_OPTIMIZED = "cost_optimized"
    QUALITY_OPTIMIZED = "quality_optimized"

@dataclass
class BackendLoad:
    """Current load information for a backend"""
    backend_name: str
    active_requests: int
    total_requests: int
    avg_response_time_ms: float
    success_rate: float
    estimated_cost_per_request: float
    capacity_percentage: float

class BackendLoadBalancer:
    """Intelligent load balancing across backends"""

    def __init__(
        self,
        health_monitor: BackendHealthMonitor,
        config: Optional[Config] = None
    ):
        self.config = config or Config()
        self.db = Database()
        self.health_monitor = health_monitor
        self.logger = get_logger('load_balancer')

        # Load state tracking
        self._backend_loads = {}  # backend_name -> BackendLoad
        self._round_robin_index = {}  # strategy -> index
        self._request_counts = defaultdict(int)

        # Configuration
        self.max_concurrent_per_backend = self.config.get('backends.max_concurrent', 10)
        self.default_strategy = LoadBalancingStrategy[
            self.config.get('backends.load_balancing_strategy', 'FASTEST_RESPONSE')
        ]

        self._initialize_loads()

    def _initialize_loads(self):
        """Initialize load tracking for all backends"""
        for backend_name, health in self.health_monitor.get_all_health_status().items():
            self._backend_loads[backend_name] = BackendLoad(
                backend_name=backend_name,
                active_requests=0,
                total_requests=0,
                avg_response_time_ms=health.response_time_ms,
                success_rate=health.success_rate,
                estimated_cost_per_request=self._estimate_backend_cost(backend_name),
                capacity_percentage=0.0
            )

    def _estimate_backend_cost(self, backend_name: str) -> float:
        """Estimate cost per request for a backend"""
        # Local backends (Ollama) are free
        if backend_name.startswith('ollama:'):
            return 0.0

        # Remote backends have costs
        if 'claude' in backend_name.lower():
            return 1.0  # cents per request
        elif 'gpt-4' in backend_name.lower():
            return 0.8
        elif 'gpt-3.5' in backend_name.lower():
            return 0.1

        return 0.5  # default estimate

    def select_backend(
        self,
        available_backends: List[str],
        strategy: Optional[LoadBalancingStrategy] = None,
        constraints: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Select optimal backend using load balancing strategy

        Args:
            available_backends: List of candidate backends
            strategy: Load balancing strategy to use
            constraints: Additional constraints (cost, latency, etc.)

        Returns:
            Selected backend name or None if none available
        """
        strategy = strategy or self.default_strategy
        constraints = constraints or {}

        try:
            # Filter to healthy backends
            healthy_backends = [
                b for b in available_backends
                if self.health_monitor.is_backend_available(b)
            ]

            if not healthy_backends:
                self.logger.warning("No healthy backends available")
                return None

            # Apply constraints
            filtered = self._apply_constraints(healthy_backends, constraints)

            if not filtered:
                self.logger.warning("No backends match constraints")
                return None

            # Apply strategy
            if strategy == LoadBalancingStrategy.ROUND_ROBIN:
                selected = self._round_robin_select(filtered)
            elif strategy == LoadBalancingStrategy.LEAST_LOADED:
                selected = self._least_loaded_select(filtered)
            elif strategy == LoadBalancingStrategy.FASTEST_RESPONSE:
                selected = self._fastest_response_select(filtered)
            elif strategy == LoadBalancingStrategy.WEIGHTED_RANDOM:
                selected = self._weighted_random_select(filtered)
            elif strategy == LoadBalancingStrategy.COST_OPTIMIZED:
                selected = self._cost_optimized_select(filtered)
            elif strategy == LoadBalancingStrategy.QUALITY_OPTIMIZED:
                selected = self._quality_optimized_select(filtered)
            else:
                selected = self._fastest_response_select(filtered)

            if selected:
                self.logger.info(
                    f"Selected backend {selected} using {strategy.value} strategy"
                )

            return selected

        except Exception as e:
            self.logger.error(f"Error selecting backend: {e}")
            # Fallback to first available
            return healthy_backends[0] if healthy_backends else None

    def _apply_constraints(
        self,
        backends: List[str],
        constraints: Dict[str, Any]
    ) -> List[str]:
        """Apply constraints to backend list"""
        filtered = backends

        # Max cost constraint
        if 'max_cost_cents' in constraints:
            max_cost = constraints['max_cost_cents']
            filtered = [
                b for b in filtered
                if self._backend_loads[b].estimated_cost_per_request <= max_cost
            ]

        # Max latency constraint
        if 'max_latency_ms' in constraints:
            max_latency = constraints['max_latency_ms']
            filtered = [
                b for b in filtered
                if self._backend_loads[b].avg_response_time_ms <= max_latency
            ]

        # Min success rate constraint
        if 'min_success_rate' in constraints:
            min_success = constraints['min_success_rate']
            filtered = [
                b for b in filtered
                if self._backend_loads[b].success_rate >= min_success
            ]

        # Privacy constraint (local only)
        if constraints.get('require_local', False):
            filtered = [b for b in filtered if b.startswith('ollama:')]

        # Exclude overloaded backends
        filtered = [
            b for b in filtered
            if self._backend_loads[b].active_requests < self.max_concurrent_per_backend
        ]

        return filtered

    def _round_robin_select(self, backends: List[str]) -> Optional[str]:
        """Round-robin selection"""
        if not backends:
            return None

        # Get or initialize index
        key = 'round_robin'
        if key not in self._round_robin_index:
            self._round_robin_index[key] = 0

        # Select and increment
        index = self._round_robin_index[key] % len(backends)
        self._round_robin_index[key] += 1

        return backends[index]

    def _least_loaded_select(self, backends: List[str]) -> Optional[str]:
        """Select backend with least active requests"""
        if not backends:
            return None

        return min(
            backends,
            key=lambda b: self._backend_loads[b].active_requests
        )

    def _fastest_response_select(self, backends: List[str]) -> Optional[str]:
        """Select backend with fastest response time"""
        if not backends:
            return None

        return min(
            backends,
            key=lambda b: self._backend_loads[b].avg_response_time_ms
        )

    def _weighted_random_select(self, backends: List[str]) -> Optional[str]:
        """Weighted random selection based on success rate and speed"""
        if not backends:
            return None

        # Calculate weights (higher is better)
        weights = []
        for backend in backends:
            load = self._backend_loads[backend]

            # Success rate component
            success_weight = load.success_rate

            # Speed component (inverse of response time, normalized)
            speed_weight = 1.0 / (1.0 + load.avg_response_time_ms / 1000)

            # Load component (inverse of active requests)
            load_weight = 1.0 / (1.0 + load.active_requests)

            # Combined weight
            weight = success_weight * 0.4 + speed_weight * 0.4 + load_weight * 0.2
            weights.append(weight)

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(backends)

        weights = [w / total_weight for w in weights]

        # Weighted random selection
        return random.choices(backends, weights=weights)[0]

    def _cost_optimized_select(self, backends: List[str]) -> Optional[str]:
        """Select lowest cost backend"""
        if not backends:
            return None

        # Prefer free backends
        free_backends = [b for b in backends if self._backend_loads[b].estimated_cost_per_request == 0]
        if free_backends:
            # Among free backends, select fastest
            return min(
                free_backends,
                key=lambda b: self._backend_loads[b].avg_response_time_ms
            )

        # Otherwise select cheapest
        return min(
            backends,
            key=lambda b: self._backend_loads[b].estimated_cost_per_request
        )

    def _quality_optimized_select(self, backends: List[str]) -> Optional[str]:
        """Select highest quality backend"""
        if not backends:
            return None

        # Quality score = success_rate * speed_factor
        def quality_score(backend):
            load = self._backend_loads[backend]
            speed_factor = 1.0 / (1.0 + load.avg_response_time_ms / 1000)
            return load.success_rate * 0.7 + speed_factor * 0.3

        return max(backends, key=quality_score)

    def start_request(self, backend_name: str):
        """Record that a request is starting on a backend"""
        if backend_name in self._backend_loads:
            load = self._backend_loads[backend_name]
            load.active_requests += 1
            load.total_requests += 1
            load.capacity_percentage = (
                load.active_requests / self.max_concurrent_per_backend
            )

            self.logger.debug(
                f"Backend {backend_name} now handling {load.active_requests} requests "
                f"({load.capacity_percentage:.0%} capacity)"
            )

    def end_request(
        self,
        backend_name: str,
        success: bool,
        response_time_ms: float
    ):
        """Record that a request has completed"""
        if backend_name in self._backend_loads:
            load = self._backend_loads[backend_name]
            load.active_requests = max(0, load.active_requests - 1)
            load.capacity_percentage = (
                load.active_requests / self.max_concurrent_per_backend
            )

            # Update average response time (exponential moving average)
            alpha = 0.3
            load.avg_response_time_ms = (
                (1 - alpha) * load.avg_response_time_ms +
                alpha * response_time_ms
            )

            # Record with health monitor
            self.health_monitor.record_backend_usage(
                backend_name,
                success,
                response_time_ms
            )

            self.logger.debug(
                f"Request completed on {backend_name}: {response_time_ms:.1f}ms, "
                f"success={success}"
            )

    def get_load_distribution(self) -> Dict[str, Any]:
        """Get current load distribution across backends"""
        return {
            'backends': {
                name: {
                    'active_requests': load.active_requests,
                    'total_requests': load.total_requests,
                    'capacity': load.capacity_percentage,
                    'avg_response_ms': load.avg_response_time_ms,
                    'success_rate': load.success_rate,
                    'estimated_cost': load.estimated_cost_per_request
                }
                for name, load in self._backend_loads.items()
            },
            'total_active': sum(l.active_requests for l in self._backend_loads.values()),
            'total_requests': sum(l.total_requests for l in self._backend_loads.values())
        }

    def get_recommended_backend(
        self,
        backends: List[str],
        task_type: str = 'general',
        max_cost_cents: float = float('inf')
    ) -> Optional[str]:
        """
        Get recommended backend for a task

        Args:
            backends: Available backends
            task_type: Type of task (code, creative, data, general)
            max_cost_cents: Maximum cost constraint

        Returns:
            Recommended backend name
        """
        constraints = {'max_cost_cents': max_cost_cents}

        # Select strategy based on task type
        if task_type == 'code':
            # Code tasks prefer quality
            strategy = LoadBalancingStrategy.QUALITY_OPTIMIZED
        elif task_type == 'creative':
            # Creative tasks can use remote if budget allows
            if max_cost_cents > 0:
                strategy = LoadBalancingStrategy.QUALITY_OPTIMIZED
            else:
                strategy = LoadBalancingStrategy.COST_OPTIMIZED
        elif task_type == 'data':
            # Data tasks prefer speed
            strategy = LoadBalancingStrategy.FASTEST_RESPONSE
        else:
            # General tasks balance all factors
            strategy = LoadBalancingStrategy.WEIGHTED_RANDOM

        return self.select_backend(backends, strategy, constraints)

    def rebalance_load(self):
        """Trigger load rebalancing if needed"""
        # Check if any backend is overloaded
        overloaded = [
            name for name, load in self._backend_loads.items()
            if load.capacity_percentage > 0.8
        ]

        if overloaded:
            self.logger.warning(
                f"Backends overloaded: {', '.join(overloaded)}"
            )
            # In a production system, this would trigger rebalancing actions
            # For now, just log the condition

    def get_load_stats(self) -> Dict[str, Any]:
        """Get load balancing statistics"""
        loads = list(self._backend_loads.values())

        return {
            'total_backends': len(loads),
            'active_backends': sum(1 for l in loads if l.active_requests > 0),
            'total_active_requests': sum(l.active_requests for l in loads),
            'total_completed_requests': sum(l.total_requests for l in loads),
            'avg_capacity': sum(l.capacity_percentage for l in loads) / len(loads) if loads else 0,
            'overloaded_backends': sum(1 for l in loads if l.capacity_percentage > 0.8),
            'avg_response_time_ms': sum(l.avg_response_time_ms for l in loads) / len(loads) if loads else 0
        }
