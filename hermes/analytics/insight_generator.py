"""
Advanced Insight Generator
AI-powered insights and recommendations from system data
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import statistics

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('analytics.insight_generator')

class InsightType(Enum):
    """Types of insights"""
    PERFORMANCE = "performance"
    COST_OPTIMIZATION = "cost_optimization"
    SECURITY = "security"
    USAGE_PATTERN = "usage_pattern"
    EFFICIENCY = "efficiency"
    ANOMALY = "anomaly"

class InsightPriority(Enum):
    """Insight priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class Insight:
    """Generated insight"""
    insight_id: str
    insight_type: InsightType
    priority: InsightPriority
    title: str
    description: str
    evidence: Dict[str, Any]
    recommendations: List[str]
    impact_score: float
    confidence: float
    created_at: datetime
    expires_at: Optional[datetime]

class InsightGenerator:
    """AI-powered insight generation system"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('insight_generator')

        # Configuration
        self.enabled = self.config.get('analytics.insights.enabled', True)
        self.confidence_threshold = self.config.get('analytics.insights.confidence_threshold', 0.7)

        # Insight cache
        self._insight_cache = {}  # insight_id -> Insight
        self._generated_patterns = {}

    def generate_insights(
        self,
        time_range_hours: int = 24,
        insight_types: Optional[List[InsightType]] = None
    ) -> List[Insight]:
        """
        Generate insights from system data

        Args:
            time_range_hours: Time window for analysis
            insight_types: Types of insights to generate

        Returns:
            List of generated insights
        """
        if not self.enabled:
            return []

        insights = []
        time_range = TimeRange(
            start=datetime.now() - timedelta(hours=time_range_hours),
            end=datetime.now()
        )

        # Generate different types of insights
        if insight_types is None:
            insight_types = list(InsightType)

        if InsightType.PERFORMANCE in insight_types:
            insights.extend(self._generate_performance_insights(time_range))

        if InsightType.COST_OPTIMIZATION in insight_types:
            insights.extend(self._generate_cost_insights(time_range))

        if InsightType.SECURITY in insight_types:
            insights.extend(self._generate_security_insights(time_range))

        if InsightType.USAGE_PATTERN in insight_types:
            insights.extend(self._generate_usage_insights(time_range))

        if InsightType.EFFICIENCY in insight_types:
            insights.extend(self._generate_efficiency_insights(time_range))

        if InsightType.ANOMALY in insight_types:
            insights.extend(self._generate_anomaly_insights(time_range))

        # Filter by confidence
        insights = [i for i in insights if i.confidence >= self.confidence_threshold]

        # Sort by impact and priority
        insights.sort(
            key=lambda i: (
                {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}[i.priority.value],
                i.impact_score
            ),
            reverse=True
        )

        # Cache insights
        for insight in insights:
            self._insight_cache[insight.insight_id] = insight

        self.logger.info(f"Generated {len(insights)} insights for {time_range_hours}h window")

        return insights

    def _generate_performance_insights(self, time_range: 'TimeRange') -> List[Insight]:
        """Generate performance-related insights"""
        insights = []

        try:
            with self.db.get_connection() as conn:
                # Analyze execution time trends
                cursor = conn.execute("""
                    SELECT
                        AVG(execution_time_ms) as avg_time,
                        MIN(execution_time_ms) as min_time,
                        MAX(execution_time_ms) as max_time,
                        COUNT(*) as total_jobs
                    FROM jobs
                    WHERE created_at BETWEEN ? AND ?
                    AND status = 'completed'
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                row = cursor.fetchone()
                if row and row['total_jobs'] > 0:
                    avg_time = row['avg_time']

                    # Compare with historical baseline
                    baseline_avg = self._get_performance_baseline()
                    if baseline_avg > 0:
                        improvement = (baseline_avg - avg_time) / baseline_avg

                        if improvement > 0.2:  # 20% improvement
                            insights.append(Insight(
                                insight_id=self._generate_insight_id(),
                                insight_type=InsightType.PERFORMANCE,
                                priority=InsightPriority.HIGH,
                                title="Performance Improvement Detected",
                                description=f"Average execution time has improved by {improvement:.1%} compared to baseline",
                                evidence={
                                    'current_avg_time': avg_time,
                                    'baseline_avg_time': baseline_avg,
                                    'improvement_pct': improvement
                                },
                                recommendations=[
                                    "Continue using current backend configuration",
                                    "Monitor if improvement sustains",
                                    "Consider applying successful patterns to other tasks"
                                ],
                                impact_score=0.8,
                                confidence=0.9,
                                created_at=datetime.now(),
                                expires_at=datetime.now() + timedelta(days=7)
                            ))

                        elif improvement < -0.1:  # 10% degradation
                            insights.append(Insight(
                                insight_id=self._generate_insight_id(),
                                insight_type=InsightType.PERFORMANCE,
                                priority=InsightPriority.MEDIUM,
                                title="Performance Degradation Detected",
                                description=f"Average execution time has degraded by {abs(improvement):.1%} compared to baseline",
                                evidence={
                                    'current_avg_time': avg_time,
                                    'baseline_avg_time': baseline_avg,
                                    'degradation_pct': abs(improvement)
                                },
                                recommendations=[
                                    "Investigate backend performance issues",
                                    "Check for resource contention",
                                    "Consider switching backends for affected tasks"
                                ],
                                impact_score=0.6,
                                confidence=0.8,
                                created_at=datetime.now(),
                                expires_at=datetime.now() + timedelta(days=3)
                            ))

                # Analyze slow jobs
                cursor = conn.execute("""
                    SELECT idea, execution_time_ms, backend_id
                    FROM jobs
                    WHERE created_at BETWEEN ? AND ?
                    AND status = 'completed'
                    AND execution_time_ms > 10000
                    ORDER BY execution_time_ms DESC
                    LIMIT 5
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                slow_jobs = cursor.fetchall()
                if len(slow_jobs) >= 3:
                    insights.append(Insight(
                        insight_id=self._generate_insight_id(),
                        insight_type=InsightType.PERFORMANCE,
                        priority=InsightPriority.MEDIUM,
                        title=f"{len(slow_jobs)} Slow Jobs Detected",
                        description=f"Found {len(slow_jobs)} jobs taking over 10 seconds",
                        evidence={
                            'slow_jobs': [
                                {'idea': job['idea'][:50], 'time_ms': job['execution_time_ms']}
                                for job in slow_jobs
                            ]
                        },
                        recommendations=[
                            "Review slow job patterns",
                            "Consider backend optimization",
                            "Implement job timeouts for very slow jobs"
                        ],
                        impact_score=0.5,
                        confidence=0.7,
                        created_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(days=5)
                    ))

        except Exception as e:
            self.logger.error(f"Error generating performance insights: {e}")

        return insights

    def _generate_cost_insights(self, time_range: 'TimeRange') -> List[Insight]:
        """Generate cost optimization insights"""
        insights = []

        try:
            with self.db.get_connection() as conn:
                # Analyze cost trends
                cursor = conn.execute("""
                    SELECT
                        SUM(cost_cents) as total_cost,
                        AVG(cost_cents) as avg_cost,
                        COUNT(*) as total_jobs
                    FROM jobs
                    WHERE created_at BETWEEN ? AND ?
                    AND cost_cents > 0
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                row = cursor.fetchone()
                if row and row['total_jobs'] > 0:
                    total_cost = row['total_cost'] / 100  # Convert to dollars
                    avg_cost = row['avg_cost']

                    # Check budget utilization
                    daily_budget = self.config.get('backends.daily_budget_cents', 100) / 100
                    if total_cost > daily_budget * 0.8:
                        insights.append(Insight(
                            insight_id=self._generate_insight_id(),
                            insight_type=InsightType.COST_OPTIMIZATION,
                            priority=InsightPriority.HIGH,
                            title="High Budget Utilization",
                            description=f"Spent ${total_cost:.2f}, which is {(total_cost/daily_budget)*100:.0f}% of daily budget",
                            evidence={
                                'total_cost_usd': total_cost,
                                'daily_budget_usd': daily_budget,
                                'utilization_pct': (total_cost/daily_budget)*100
                            },
                            recommendations=[
                                "Use more local backends to reduce costs",
                                "Implement cost-aware scheduling",
                                "Set up cost alerts for budget management"
                            ],
                            impact_score=0.7,
                            confidence=0.9,
                            created_at=datetime.now(),
                            expires_at=datetime.now() + timedelta(days=1)
                        ))

                    # Analyze expensive backends
                    cursor = conn.execute("""
                        SELECT
                            b.name as backend_name,
                            AVG(j.cost_cents) as avg_cost,
                            COUNT(*) as job_count
                        FROM jobs j
                        JOIN backends b ON j.backend_id = b.id
                        WHERE j.created_at BETWEEN ? AND ?
                        AND j.cost_cents > 0
                        GROUP BY b.name
                        ORDER BY avg_cost DESC
                    """, (time_range.start.isoformat(), time_range.end.isoformat()))

                    expensive_backends = cursor.fetchall()
                    if len(expensive_backends) > 0:
                        most_expensive = expensive_backends[0]
                        if most_expensive['avg_cost'] > 2.0:  # More than $0.02 per job
                            insights.append(Insight(
                                insight_id=self._generate_insight_id(),
                                insight_type=InsightType.COST_OPTIMIZATION,
                                priority=InsightPriority.MEDIUM,
                                title="Expensive Backend Detected",
                                description=f"{most_expensive['backend_name']} costs ${most_expensive['avg_cost']/100:.3f} per job on average",
                                evidence={
                                    'backend_name': most_expensive['backend_name'],
                                    'avg_cost_cents': most_expensive['avg_cost'],
                                    'job_count': most_expensive['job_count']
                                },
                                recommendations=[
                                    f"Consider switching to free local backends when possible",
                                    f"Reserve {most_expensive['backend_name']} for complex tasks only",
                                    "Enable automatic cost optimization"
                                ],
                                impact_score=0.6,
                                confidence=0.8,
                                created_at=datetime.now(),
                                expires_at=datetime.now() + timedelta(days=3)
                            ))

        except Exception as e:
            self.logger.error(f"Error generating cost insights: {e}")

        return insights

    def _generate_security_insights(self, time_range: 'TimeRange') -> List[Insight]:
        """Generate security-related insights"""
        insights = []

        try:
            with self.db.get_connection() as conn:
                # Analyze security events
                cursor = conn.execute("""
                    SELECT
                        threat_type,
                        threat_level,
                        COUNT(*) as count
                    FROM security_events
                    WHERE created_at BETWEEN ? AND ?
                    GROUP BY threat_type, threat_level
                    ORDER BY count DESC
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                threats = cursor.fetchall()
                if threats:
                    high_threats = [t for t in threats if t['threat_level'] in ['high', 'critical']]
                    if high_threats:
                        insights.append(Insight(
                            insight_id=self._generate_insight_id(),
                            insight_type=InsightType.SECURITY,
                            priority=InsightPriority.HIGH,
                            title=f"{len(high_threats)} High-Severity Threats Detected",
                            description=f"Security system detected {len(high_threats)} high or critical severity threats",
                            evidence={
                                'threats': [
                                    {'type': t['threat_type'], 'level': t['threat_level'], 'count': t['count']}
                                    for t in high_threats
                                ]
                            },
                            recommendations=[
                                "Review security logs for details",
                                "Strengthen security policies if needed",
                                "Monitor for repeated attack patterns"
                            ],
                            impact_score=0.8,
                            confidence=0.9,
                            created_at=datetime.now(),
                            expires_at=datetime.now() + timedelta(hours=12)
                        ))

                # Analyze failed login attempts
                cursor = conn.execute("""
                    SELECT COUNT(*) as failed_attempts,
                           COUNT(DISTINCT source_ip) as unique_ips
                    FROM security_events
                    WHERE created_at BETWEEN ? AND ?
                    AND response_status = 401
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                row = cursor.fetchone()
                if row and row['failed_attempts'] > 50:
                    insights.append(Insight(
                        insight_id=self._generate_insight_id(),
                        insight_type=InsightType.SECURITY,
                        priority=InsightPriority.MEDIUM,
                        title="Elevated Failed Login Attempts",
                        description=f"Detected {row['failed_attempts']} failed login attempts from {row['unique_ips']} unique IPs",
                        evidence={
                            'failed_attempts': row['failed_attempts'],
                            'unique_ips': row['unique_ips']
                        },
                        recommendations=[
                            "Enable account lockout policies",
                            "Implement IP-based rate limiting",
                            "Consider requiring additional authentication"
                        ],
                        impact_score=0.5,
                        confidence=0.7,
                        created_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(days=1)
                    ))

        except Exception as e:
            self.logger.error(f"Error generating security insights: {e}")

        return insights

    def _generate_usage_insights(self, time_range: 'TimeRange') -> List[Insight]:
        """Generate usage pattern insights"""
        insights = []

        try:
            with self.db.get_connection() as conn:
                # Analyze peak usage hours
                cursor = conn.execute("""
                    SELECT
                        strftime('%H', created_at) as hour,
                        COUNT(*) as job_count
                    FROM jobs
                    WHERE created_at BETWEEN ? AND ?
                    GROUP BY hour
                    ORDER BY job_count DESC
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                hourly_data = {int(row['hour']): row['job_count'] for row in cursor.fetchall()}

                if hourly_data:
                    peak_hour = max(hourly_data, key=hourly_data.get)
                    peak_count = hourly_data[peak_hour]

                    # Check if usage is concentrated
                    total_jobs = sum(hourly_data.values())
                    peak_concentration = peak_count / total_jobs

                    if peak_concentration > 0.15:  # More than 15% in one hour
                        insights.append(Insight(
                            insight_id=self._generate_insight_id(),
                            insight_type=InsightType.USAGE_PATTERN,
                            priority=InsightPriority.MEDIUM,
                            title=f"Peak Usage Concentrated at {peak_hour:02d}:00",
                            description=f"{peak_concentration:.1%} of jobs are processed during {peak_hour:02d}:00 hour",
                            evidence={
                                'peak_hour': peak_hour,
                                'peak_count': peak_count,
                                'total_jobs': total_jobs,
                                'concentration_pct': peak_concentration
                            },
                            recommendations=[
                                "Consider load balancing across more hours",
                                "Implement queue prioritization for peak hours",
                                "Scale resources during peak usage periods"
                            ],
                            impact_score=0.4,
                            confidence=0.8,
                            created_at=datetime.now(),
                            expires_at=datetime.now() + timedelta(days=7)
                        ))

                # Analyze task types
                cursor = conn.execute("""
                    SELECT idea, COUNT(*) as count
                    FROM jobs
                    WHERE created_at BETWEEN ? AND ?
                    GROUP BY idea
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                    LIMIT 5
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                repeated_tasks = cursor.fetchall()
                if repeated_tasks:
                    most_common = repeated_tasks[0]
                    if most_common['count'] > 5:
                        insights.append(Insight(
                            insight_id=self._generate_insight_id(),
                            insight_type=InsightType.USAGE_PATTERN,
                            priority=InsightPriority.LOW,
                            title=f"Repeated Task Pattern Detected",
                            description=f"'{most_common['idea'][:50]}...' has been executed {most_common['count']} times",
                            evidence={
                                'task': most_common['idea'],
                                'execution_count': most_common['count']
                            },
                            recommendations=[
                                "Consider automating this recurring task",
                                "Create a template or shortcut for this task",
                                "Evaluate if this pattern suggests a workflow optimization opportunity"
                            ],
                            impact_score=0.3,
                            confidence=0.6,
                            created_at=datetime.now(),
                            expires_at=datetime.now() + timedelta(days=5)
                        ))

        except Exception as e:
            self.logger.error(f"Error generating usage insights: {e}")

        return insights

    def _generate_efficiency_insights(self, time_range: 'TimeRange') -> List[Insight]:
        """Generate efficiency insights"""
        insights = []

        try:
            with self.db.get_connection() as conn:
                # Analyze success rate by backend
                cursor = conn.execute("""
                    SELECT
                        b.name as backend_name,
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN j.status = 'completed' THEN 1 ELSE 0 END) as successful_jobs
                    FROM jobs j
                    JOIN backends b ON j.backend_id = b.id
                    WHERE j.created_at BETWEEN ? AND ?
                    GROUP BY b.name
                    HAVING COUNT(*) >= 5
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                backend_stats = []
                for row in cursor.fetchall():
                    success_rate = row['successful_jobs'] / row['total_jobs']
                    backend_stats.append({
                        'backend': row['backend_name'],
                        'success_rate': success_rate,
                        'total_jobs': row['total_jobs']
                    })

                # Find underperforming backends
                underperforming = [
                    stat for stat in backend_stats
                    if stat['success_rate'] < 0.8
                ]

                if underperforming:
                    insights.append(Insight(
                        insight_id=self._generate_insight_id(),
                        insight_type=InsightType.EFFICIENCY,
                        priority=InsightPriority.MEDIUM,
                        title=f"{len(underperforming)} Underperforming Backends",
                        description="Some backends have success rates below 80%",
                        evidence={
                            'backend_stats': underperforming
                        },
                        recommendations=[
                            "Review backend configuration and health",
                            "Consider switching to more reliable backends",
                            "Investigate root causes of failures"
                        ],
                        impact_score=0.6,
                        confidence=0.8,
                        created_at=datetime.now(),
                        expires_at=datetime.now() + timedelta(days=3)
                    ))

                # Analyze resource utilization
                cursor = conn.execute("""
                    SELECT
                        AVG(CASE WHEN j.status = 'completed' THEN j.execution_time_ms ELSE NULL END) as avg_completion_time,
                        AVG(CASE WHEN j.status = 'failed' THEN j.execution_time_ms ELSE NULL END) as avg_failure_time
                    FROM jobs j
                    WHERE j.created_at BETWEEN ? AND ?
                """, (time_range.start.isoformat(), time_range.end.isoformat()))

                row = cursor.fetchone()
                if row and row['avg_completion_time'] and row['avg_failure_time']:
                    completion_time = row['avg_completion_time']
                    failure_time = row['avg_failure_time']

                    if failure_time > completion_time * 1.5:
                        insights.append(Insight(
                            insight_id=self._generate_insight_id(),
                            insight_type=InsightType.EFFICIENCY,
                            priority=InsightPriority.LOW,
                            title="Resource Inefficiency Detected",
                            description="Failed jobs take significantly longer than successful jobs",
                            evidence={
                                'avg_completion_time_ms': completion_time,
                                'avg_failure_time_ms': failure_time,
                                'ratio': failure_time / completion_time
                            },
                            recommendations=[
                                "Implement faster failure detection",
                                "Reduce timeout values for unreliable tasks",
                                "Add early validation to prevent obvious failures"
                            ],
                            impact_score=0.4,
                            confidence=0.6,
                            created_at=datetime.now(),
                            expires_at=datetime.now() + timedelta(days=5)
                        ))

        except Exception as e:
            self.logger.error(f"Error generating efficiency insights: {e}")

        return insights

    def _generate_anomaly_insights(self, time_range: 'TimeRange') -> List[Insight]:
        """Generate anomaly detection insights"""
        insights = []

        try:
            # Detect unusual patterns using statistical analysis
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        DATE(created_at) as date,
                        COUNT(*) as job_count,
                        AVG(CASE WHEN status = 'completed' THEN execution_time_ms ELSE NULL END) as avg_time
                    FROM jobs
                    WHERE created_at >= datetime('now', '-30 days')
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                """)

                daily_stats = []
                for row in cursor.fetchall():
                    daily_stats.append({
                        'date': row['date'],
                        'job_count': row['job_count'],
                        'avg_time': row['avg_time']
                    })

                if len(daily_stats) >= 7:
                    # Calculate statistics for recent days
                    recent_counts = [s['job_count'] for s in daily_stats[:7]]
                    recent_times = [s['avg_time'] for s in daily_stats[:7] if s['avg_time']]

                    if recent_counts:
                        count_mean = statistics.mean(recent_counts)
                        count_stdev = statistics.stdev(recent_counts) if len(recent_counts) > 1 else 0

                        # Check for anomalies
                        latest_count = recent_counts[0]
                        if count_stdev > 0 and abs(latest_count - count_mean) > 2 * count_stdev:
                            if latest_count > count_mean:
                                insights.append(Insight(
                                    insight_id=self._generate_insight_id(),
                                    insight_type=InsightType.ANOMALY,
                                    priority=InsightPriority.LOW,
                                    title="Unusually High Activity Detected",
                                    description=f"Job count is {((latest_count - count_mean) / count_mean):.1%} above normal",
                                    evidence={
                                        'latest_count': latest_count,
                                        'historical_mean': count_mean,
                                        'historical_stdev': count_stdev
                                    },
                                    recommendations=[
                                        "Investigate cause of increased activity",
                                        "Monitor system capacity",
                                        "Ensure this isn't automated abuse"
                                    ],
                                    impact_score=0.3,
                                    confidence=0.7,
                                    created_at=datetime.now(),
                                    expires_at=datetime.now() + timedelta(days=2)
                                ))
                            else:
                                insights.append(Insight(
                                    insight_id=self._generate_insight_id(),
                                    insight_type=InsightType.ANOMALY,
                                    priority=InsightPriority.LOW,
                                    title="Unusually Low Activity Detected",
                                    description=f"Job count is {((count_mean - latest_count) / count_mean):.1%} below normal",
                                    evidence={
                                        'latest_count': latest_count,
                                        'historical_mean': count_mean,
                                        'historical_stdev': count_stdev
                                    },
                                    recommendations=[
                                        "Check if systems are functioning normally",
                                        "Verify no service disruptions",
                                        "Review recent system changes"
                                    ],
                                    impact_score=0.4,
                                    confidence=0.7,
                                    created_at=datetime.now(),
                                    expires_at=datetime.now() + timedelta(days=2)
                                ))

        except Exception as e:
            self.logger.error(f"Error generating anomaly insights: {e}")

        return insights

    def _get_performance_baseline(self) -> float:
        """Get historical performance baseline"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT AVG(execution_time_ms) as avg_time
                    FROM jobs
                    WHERE created_at >= datetime('now', '-30 days')
                    AND status = 'completed'
                """)
                row = cursor.fetchone()
                return row['avg_time'] if row else 0.0
        except Exception:
            return 0.0

    def _generate_insight_id(self) -> str:
        """Generate unique insight ID"""
        import time
        return f"insight_{int(time.time() * 1000)}_{hash(time.time()) % 10000}"

    def get_insights(
        self,
        insight_type: Optional[InsightType] = None,
        priority: Optional[InsightPriority] = None,
        hours: int = 24
    ) -> List[Insight]:
        """Get cached insights with filtering"""
        insights = list(self._insight_cache.values())

        # Filter by time
        cutoff_time = datetime.now() - timedelta(hours=hours)
        insights = [i for i in insights if i.created_at >= cutoff_time]

        # Filter by type
        if insight_type:
            insights = [i for i in insights if i.insight_type == insight_type]

        # Filter by priority
        if priority:
            insights = [i for i in insights if i.priority == priority]

        # Remove expired insights
        now = datetime.now()
        insights = [i for i in insights if i.expires_at is None or i.expires_at > now]

        return sorted(insights, key=lambda i: (i.created_at, i.priority.value), reverse=True)

# Add missing TimeRange import for type hints
from dataclasses import dataclass
@dataclass
class TimeRange:
    start: datetime
    end: datetime