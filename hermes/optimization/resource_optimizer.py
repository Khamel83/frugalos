"""
Resource optimization and auto-scaling system for the Hermes AI Assistant.

This module provides intelligent resource management including:
- Dynamic resource allocation and deallocation
- Auto-scaling policies and thresholds
- Resource usage prediction and optimization
- Cost optimization strategies
- Performance vs resource trade-off analysis
"""

import asyncio
import time
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import logging
from enum import Enum

import psutil
import numpy as np
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
import redis.asyncio as redis
import boto3
from prometheus_client import CollectorRegistry, Gauge

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources that can be optimized."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"


class ScalingDirection(Enum):
    """Scaling direction."""
    UP = "up"
    DOWN = "down"
    NONE = "none"


@dataclass
class ResourceMetrics:
    """Current resource usage metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    gpu_utilization: Optional[float] = None
    gpu_memory_used: Optional[float] = None
    pod_count: Optional[int] = None
    node_count: Optional[int] = None


@dataclass
class ScalingDecision:
    """Auto-scaling decision."""
    resource_type: ResourceType
    direction: ScalingDirection
    current_value: float
    threshold_value: float
    target_replicas: Optional[int] = None
    target_resources: Optional[Dict[str, str]] = None
    reason: str = ""
    confidence: float = 0.0
    estimated_cost_impact: float = 0.0


@dataclass
class OptimizationPolicy:
    """Resource optimization policy."""
    name: str
    resource_type: ResourceType
    min_threshold: float
    max_threshold: float
    target_utilization: float
    scale_up_cooldown: int  # seconds
    scale_down_cooldown: int  # seconds
    max_replicas: int
    min_replicas: int
    cost_weight: float = 1.0
    performance_weight: float = 1.0


class ResourceMonitor:
    """Monitors system and application resource usage."""

    def __init__(self, kubernetes_enabled: bool = False):
        self.kubernetes_enabled = kubernetes_enabled
        self.metrics_history: deque = deque(maxlen=1440)  # 24 hours at 1-minute intervals
        self.collection_interval = 60  # seconds
        self.is_collecting = False
        self._collection_task: Optional[asyncio.Task] = None

        # Initialize Kubernetes client if enabled
        if kubernetes_enabled:
            try:
                config.load_incluster_config()
                self.k8s_apps = client.AppsV1Api()
                self.k8s_core = client.CoreV1Api()
                self.k8s_autoscaling = client.AutoscalingV2Api()
            except Exception as e:
                logger.warning(f"Could not initialize Kubernetes client: {e}")
                self.kubernetes_enabled = False

    async def start_monitoring(self):
        """Start continuous resource monitoring."""
        if self.is_collecting:
            return

        self.is_collecting = True
        self._collection_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started resource monitoring")

    async def stop_monitoring(self):
        """Stop resource monitoring."""
        self.is_collecting = False
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped resource monitoring")

    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_collecting:
            try:
                metrics = await self.collect_metrics()
                self.metrics_history.append(metrics)
            except Exception as e:
                logger.error(f"Error collecting resource metrics: {e}")
            await asyncio.sleep(self.collection_interval)

    async def collect_metrics(self) -> ResourceMetrics:
        """Collect current resource metrics."""
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()

        # GPU metrics (if available)
        gpu_utilization = None
        gpu_memory_used = None
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_utilization = gpus[0].load * 100
                gpu_memory_used = gpus[0].memoryUsed
        except ImportError:
            pass

        # Kubernetes metrics (if available)
        pod_count = None
        node_count = None
        if self.kubernetes_enabled:
            try:
                # Get pod count for this namespace
                pods = self.k8s_core.list_namespaced_pod(namespace="default")
                pod_count = len(pods.items)

                # Get node count
                nodes = self.k8s_core.list_node()
                node_count = len(nodes.items)
            except Exception as e:
                logger.error(f"Error collecting Kubernetes metrics: {e}")

        return ResourceMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / 1024 / 1024,
            disk_usage_percent=disk.percent,
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            gpu_utilization=gpu_utilization,
            gpu_memory_used=gpu_memory_used,
            pod_count=pod_count,
            node_count=node_count
        )

    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get metrics summary for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {}

        # Calculate statistics
        cpu_values = [m.cpu_percent for m in recent_metrics]
        memory_values = [m.memory_percent for m in recent_metrics]

        return {
            'period_hours': hours,
            'sample_count': len(recent_metrics),
            'cpu': {
                'avg': statistics.mean(cpu_values),
                'min': min(cpu_values),
                'max': max(cpu_values),
                'p95': np.percentile(cpu_values, 95)
            },
            'memory': {
                'avg': statistics.mean(memory_values),
                'min': min(memory_values),
                'max': max(memory_values),
                'p95': np.percentile(memory_values, 95)
            },
            'timestamps': {
                'start': recent_metrics[0].timestamp.isoformat(),
                'end': recent_metrics[-1].timestamp.isoformat()
            }
        }


class ResourcePredictor:
    """Predicts future resource usage based on historical data."""

    def __init__(self, prediction_window: int = 60):
        self.prediction_window = prediction_window  # minutes
        self.min_data_points = 10

    def predict_resource_usage(self, metrics_history: deque,
                             resource_type: ResourceType) -> Dict[str, Any]:
        """Predict resource usage for the specified window."""
        if len(metrics_history) < self.min_data_points:
            return {'error': 'Insufficient data for prediction'}

        # Extract time series data
        timestamps = [m.timestamp for m in metrics_history]
        if resource_type == ResourceType.CPU:
            values = [m.cpu_percent for m in metrics_history]
        elif resource_type == ResourceType.MEMORY:
            values = [m.memory_percent for m in metrics_history]
        else:
            return {'error': f'Prediction not supported for {resource_type}'}

        # Simple linear regression for trend prediction
        try:
            # Convert timestamps to numeric values (minutes from start)
            start_time = timestamps[0]
            x_values = [(t - start_time).total_seconds() / 60 for t in timestamps]  # minutes

            # Linear regression
            coeffs = np.polyfit(x_values, values, 1)
            slope, intercept = coeffs

            # Predict future values
            future_x = np.arange(x_values[-1], x_values[-1] + self.prediction_window, 1)
            predicted_values = slope * future_x + intercept

            # Calculate confidence bounds (simple standard error)
            residuals = values - (slope * np.array(x_values) + intercept)
            std_error = np.std(residuals)

            return {
                'current_value': values[-1],
                'predicted_mean': np.mean(predicted_values),
                'predicted_max': np.max(predicted_values),
                'predicted_min': np.min(predicted_values),
                'trend_slope': slope,
                'confidence_interval': std_error * 2,
                'prediction_minutes': self.prediction_window,
                'data_points_used': len(values)
            }

        except Exception as e:
            logger.error(f"Error in resource prediction: {e}")
            return {'error': f'Prediction failed: {str(e)}'}


class AutoScaler:
    """Intelligent auto-scaling engine."""

    def __init__(self, policies: List[OptimizationPolicy], kubernetes_enabled: bool = False):
        self.policies = policies
        self.kubernetes_enabled = kubernetes_enabled
        self.scaling_history: deque = deque(maxlen=100)
        self.last_scale_time: Dict[str, datetime] = {}
        self.predictor = ResourcePredictor()

        # Initialize Kubernetes client if enabled
        if kubernetes_enabled:
            try:
                config.load_incluster_config()
                self.k8s_apps = client.AppsV1Api()
                self.k8s_autoscaling = client.AutoscalingV2Api()
            except Exception as e:
                logger.warning(f"Could not initialize Kubernetes client: {e}")
                self.kubernetes_enabled = False

    async def evaluate_scaling(self, current_metrics: ResourceMetrics,
                             metrics_history: deque) -> List[ScalingDecision]:
        """Evaluate if scaling is needed and return decisions."""
        decisions = []

        for policy in self.policies:
            try:
                decision = await self._evaluate_policy(policy, current_metrics, metrics_history)
                if decision:
                    decisions.append(decision)
            except Exception as e:
                logger.error(f"Error evaluating policy {policy.name}: {e}")

        return decisions

    async def _evaluate_policy(self, policy: OptimizationPolicy,
                             current_metrics: ResourceMetrics,
                             metrics_history: deque) -> Optional[ScalingDecision]:
        """Evaluate a single scaling policy."""
        # Get current value for this resource type
        if policy.resource_type == ResourceType.CPU:
            current_value = current_metrics.cpu_percent
        elif policy.resource_type == ResourceType.MEMORY:
            current_value = current_metrics.memory_percent
        elif policy.resource_type == ResourceType.DISK:
            current_value = current_metrics.disk_usage_percent
        else:
            return None

        # Check cooldown period
        now = datetime.utcnow()
        last_scale = self.last_scale_time.get(policy.name)
        if last_scale:
            cooldown = policy.scale_up_cooldown if current_value > policy.max_threshold else policy.scale_down_cooldown
            if (now - last_scale).total_seconds() < cooldown:
                return None

        # Get prediction
        prediction = self.predictor.predict_resource_usage(metrics_history, policy.resource_type)
        predicted_value = prediction.get('predicted_mean', current_value)

        # Evaluate scaling decision
        direction = ScalingDirection.NONE
        target_replicas = None
        reason = ""

        # Scale up conditions
        if (current_value > policy.max_threshold or
            predicted_value > policy.max_threshold):
            direction = ScalingDirection.UP
            reason = f"Current {current_value:.1f}% or predicted {predicted_value:.1f}% exceeds max threshold {policy.max_threshold}%"

        # Scale down conditions
        elif (current_value < policy.min_threshold and
              predicted_value < policy.min_threshold):
            direction = ScalingDirection.DOWN
            reason = f"Current {current_value:.1f}% and predicted {predicted_value:.1f}% below min threshold {policy.min_threshold}%"

        if direction != ScalingDirection.NONE and self.kubernetes_enabled:
            # Calculate target replicas (simplified logic)
            current_replicas = current_metrics.pod_count or 1
            if direction == ScalingDirection.UP:
                target_replicas = min(current_replicas + 1, policy.max_replicas)
            else:
                target_replicas = max(current_replicas - 1, policy.min_replicas)

            if target_replicas == current_replicas:
                return None

        # Calculate confidence
        confidence = self._calculate_confidence(current_value, predicted_value, policy)

        # Estimate cost impact
        cost_impact = self._estimate_cost_impact(direction, current_metrics.pod_count or 1, target_replicas)

        return ScalingDecision(
            resource_type=policy.resource_type,
            direction=direction,
            current_value=current_value,
            threshold_value=policy.max_threshold if direction == ScalingDirection.UP else policy.min_threshold,
            target_replicas=target_replicas,
            reason=reason,
            confidence=confidence,
            estimated_cost_impact=cost_impact
        )

    def _calculate_confidence(self, current_value: float, predicted_value: float,
                            policy: OptimizationPolicy) -> float:
        """Calculate confidence in scaling decision."""
        # Higher confidence when current and predicted values align
        alignment = 1.0 - abs(current_value - predicted_value) / 100.0

        # Higher confidence when further from target
        distance_from_target = abs(current_value - policy.target_utilization) / 100.0

        return min(1.0, alignment * 0.5 + distance_from_target * 0.5)

    def _estimate_cost_impact(self, direction: ScalingDirection,
                            current_replicas: int, target_replicas: Optional[int]) -> float:
        """Estimate cost impact of scaling decision."""
        if not target_replicas or target_replicas == current_replicas:
            return 0.0

        # Simplified cost estimation (would use actual cloud pricing in production)
        replica_cost_per_hour = 0.05  # $0.05 per replica per hour
        hours_in_month = 730

        replica_change = target_replicas - current_replicas
        monthly_cost_change = replica_change * replica_cost_per_hour * hours_in_month

        return monthly_cost_change

    async def execute_scaling(self, decisions: List[ScalingDecision],
                            deployment_name: str, namespace: str = "default") -> bool:
        """Execute scaling decisions."""
        if not decisions or not self.kubernetes_enabled:
            return False

        success = True
        for decision in decisions:
            if decision.target_replicas and decision.direction != ScalingDirection.NONE:
                try:
                    # Scale deployment
                    body = {'spec': {'replicas': decision.target_replicas}}
                    self.k8s_apps.patch_namespaced_deployment(
                        name=deployment_name,
                        namespace=namespace,
                        body=body
                    )

                    # Record scaling action
                    self.last_scale_time[decision.resource_type.value] = datetime.utcnow()
                    self.scaling_history.append({
                        'timestamp': datetime.utcnow(),
                        'decision': decision,
                        'deployment': deployment_name,
                        'namespace': namespace
                    })

                    logger.info(f"Scaled {deployment_name} to {decision.target_replicas} replicas: {decision.reason}")

                except ApiException as e:
                    logger.error(f"Failed to scale {deployment_name}: {e}")
                    success = False

        return success


class CostOptimizer:
    """Optimizes resource costs while maintaining performance."""

    def __init__(self, cost_per_cpu_hour: float = 0.05,
                 cost_per_gb_memory_hour: float = 0.01,
                 cost_per_gb_disk_hour: float = 0.001):
        self.cost_per_cpu_hour = cost_per_cpu_hour
        self.cost_per_gb_memory_hour = cost_per_gb_memory_hour
        self.cost_per_gb_disk_hour = cost_per_gb_disk_hour

    def calculate_resource_cost(self, metrics: ResourceMetrics,
                              duration_hours: float = 1.0) -> Dict[str, float]:
        """Calculate cost for current resource usage."""
        # CPU cost (assuming 1 core = 100%)
        cpu_cores = metrics.cpu_percent / 100.0
        cpu_cost = cpu_cores * self.cost_per_cpu_hour * duration_hours

        # Memory cost
        memory_gb = metrics.memory_used_mb / 1024.0
        memory_cost = memory_gb * self.cost_per_gb_memory_hour * duration_hours

        # Disk cost
        if hasattr(metrics, 'disk_used_gb'):
            disk_gb = metrics.disk_used_gb
        else:
            # Estimate disk usage from percentage (assuming 100GB total)
            disk_gb = (metrics.disk_usage_percent / 100.0) * 100

        disk_cost = disk_gb * self.cost_per_gb_disk_hour * duration_hours

        total_cost = cpu_cost + memory_cost + disk_cost

        return {
            'cpu_cost': cpu_cost,
            'memory_cost': memory_cost,
            'disk_cost': disk_cost,
            'total_cost': total_cost,
            'duration_hours': duration_hours
        }

    def suggest_cost_optimizations(self, metrics_history: deque,
                                 performance_requirements: Dict[str, float]) -> List[Dict[str, Any]]:
        """Suggest cost optimization strategies."""
        suggestions = []
        if len(metrics_history) < 10:
            return suggestions

        # Analyze resource utilization patterns
        cpu_values = [m.cpu_percent for m in metrics_history]
        memory_values = [m.memory_percent for m in metrics_history]

        avg_cpu = statistics.mean(cpu_values)
        avg_memory = statistics.mean(memory_values)
        max_cpu = max(cpu_values)
        max_memory = max(memory_values)

        # Over-provisioning suggestions
        if avg_cpu < 30 and max_cpu < 50:
            suggestions.append({
                'type': 'cpu_right_sizing',
                'potential_savings': f"{(50 - avg_cpu):.1f}%",
                'description': "CPU is underutilized - consider reducing CPU allocation",
                'impact': 'low',
                'implementation': 'reduce_cpu_limits'
            })

        if avg_memory < 40 and max_memory < 60:
            suggestions.append({
                'type': 'memory_right_sizing',
                'potential_savings': f"{(60 - avg_memory):.1f}%",
                'description': "Memory is underutilized - consider reducing memory allocation",
                'impact': 'low',
                'implementation': 'reduce_memory_limits'
            })

        # Spot instance suggestions
        if avg_cpu < 70 and avg_memory < 70:
            suggestions.append({
                'type': 'spot_instances',
                'potential_savings': '60-90%',
                'description': "Workload is suitable for spot instances",
                'impact': 'medium',
                'implementation': 'use_spot_instances'
            })

        # Scheduling optimization
        if max_cpu < 80 and max_memory < 80:
            suggestions.append({
                'type': 'pod_bin_packing',
                'potential_savings': '10-20%',
                'description': "Consider better pod packing to improve node utilization",
                'impact': 'low',
                'implementation': 'optimize_pod_scheduling'
            })

        return suggestions


class PerformanceOptimizer:
    """Optimizes performance by adjusting resource allocation."""

    def __init__(self, resource_monitor: ResourceMonitor):
        self.resource_monitor = resource_monitor
        self.optimization_rules = [
            self._optimize_cpu_allocation,
            self._optimize_memory_allocation,
            self._optimize_io_performance,
            self._optimize_network_settings
        ]

    async def analyze_and_optimize(self) -> List[Dict[str, Any]]:
        """Analyze current performance and provide optimization recommendations."""
        current_metrics = await self.resource_monitor.collect_metrics()
        recommendations = []

        for rule in self.optimization_rules:
            try:
                rule_recommendations = await rule(current_metrics)
                recommendations.extend(rule_recommendations)
            except Exception as e:
                logger.error(f"Error in optimization rule {rule.__name__}: {e}")

        return recommendations

    async def _optimize_cpu_allocation(self, metrics: ResourceMetrics) -> List[Dict[str, Any]]:
        """Analyze CPU usage and suggest optimizations."""
        recommendations = []

        if metrics.cpu_percent > 90:
            recommendations.append({
                'type': 'cpu_optimization',
                'priority': 'high',
                'description': f"High CPU usage ({metrics.cpu_percent:.1f}%) detected",
                'recommendations': [
                    "Consider increasing CPU allocation",
                    "Profile CPU-intensive operations",
                    "Implement request queuing or rate limiting",
                    "Optimize algorithms and data structures"
                ]
            })

        elif metrics.cpu_percent < 20:
            recommendations.append({
                'type': 'cpu_optimization',
                'priority': 'low',
                'description': f"Low CPU usage ({metrics.cpu_percent:.1f}%) - potential for cost optimization",
                'recommendations': [
                    "Consider reducing CPU allocation",
                    "Consolidate workloads for better efficiency"
                ]
            })

        return recommendations

    async def _optimize_memory_allocation(self, metrics: ResourceMetrics) -> List[Dict[str, Any]]:
        """Analyze memory usage and suggest optimizations."""
        recommendations = []

        if metrics.memory_percent > 85:
            recommendations.append({
                'type': 'memory_optimization',
                'priority': 'high',
                'description': f"High memory usage ({metrics.memory_percent:.1f}%) detected",
                'recommendations': [
                    "Investigate potential memory leaks",
                    "Implement memory caching strategies",
                    "Optimize data structures and algorithms",
                    "Consider increasing memory allocation"
                ]
            })

        elif metrics.memory_percent < 30:
            recommendations.append({
                'type': 'memory_optimization',
                'priority': 'low',
                'description': f"Low memory usage ({metrics.memory_percent:.1f}%) - potential for optimization",
                'recommendations': [
                    "Consider reducing memory allocation",
                    "Implement more aggressive caching if memory is available"
                ]
            })

        return recommendations

    async def _optimize_io_performance(self, metrics: ResourceMetrics) -> List[Dict[str, Any]]:
        """Analyze I/O performance and suggest optimizations."""
        recommendations = []

        # This would require additional I/O metrics
        # For now, provide general recommendations based on disk usage
        if metrics.disk_usage_percent > 85:
            recommendations.append({
                'type': 'io_optimization',
                'priority': 'medium',
                'description': f"High disk usage ({metrics.disk_usage_percent:.1f}%)",
                'recommendations': [
                    "Implement log rotation and cleanup",
                    "Archive old data to object storage",
                    "Consider using faster storage (SSD)",
                    "Optimize database queries and indexing"
                ]
            })

        return recommendations

    async def _optimize_network_settings(self, metrics: ResourceMetrics) -> List[Dict[str, Any]]:
        """Analyze network performance and suggest optimizations."""
        recommendations = []

        # Network optimization would require additional metrics
        # For now, provide general recommendations
        recommendations.append({
            'type': 'network_optimization',
            'priority': 'info',
            'description': "Network performance monitoring",
            'recommendations': [
                "Monitor network latency and bandwidth",
                "Implement connection pooling",
                "Use CDN for static content",
                "Compress responses when appropriate"
            ]
        })

        return recommendations


# Default optimization policies
DEFAULT_POLICIES = [
    OptimizationPolicy(
        name="cpu_scaling",
        resource_type=ResourceType.CPU,
        min_threshold=30.0,
        max_threshold=80.0,
        target_utilization=60.0,
        scale_up_cooldown=300,
        scale_down_cooldown=600,
        max_replicas=10,
        min_replicas=2
    ),
    OptimizationPolicy(
        name="memory_scaling",
        resource_type=ResourceType.MEMORY,
        min_threshold=40.0,
        max_threshold=85.0,
        target_utilization=70.0,
        scale_up_cooldown=300,
        scale_down_cooldown=600,
        max_replicas=10,
        min_replicas=2
    )
]


# Global resource optimization instances
resource_monitor: Optional[ResourceMonitor] = None
auto_scaler: Optional[AutoScaler] = None
cost_optimizer: Optional[CostOptimizer] = None
performance_optimizer: Optional[PerformanceOptimizer] = None