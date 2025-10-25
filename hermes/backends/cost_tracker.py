"""
Backend Cost Tracking
Comprehensive cost tracking and budget management for backends
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('backends.cost_tracker')

@dataclass
class CostReport:
    """Cost report for a time period"""
    start_date: datetime
    end_date: datetime
    total_cost_cents: float
    total_requests: int
    cost_per_request: float
    by_backend: Dict[str, Dict[str, Any]]
    by_day: Dict[str, float]
    budget_limit_cents: float
    budget_remaining_cents: float
    budget_utilization: float

class BackendCostTracker:
    """Tracks costs across all backends"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('cost_tracker')

        # Budget configuration
        self.daily_budget_cents = self.config.get('backends.daily_budget_cents', 100)
        self.monthly_budget_cents = self.config.get('backends.monthly_budget_cents', 3000)

        # Cost rates (cents per 1000 tokens)
        self.cost_rates = {
            # Ollama models (local, free)
            'ollama:llama3.1:8b-instruct': {'input': 0, 'output': 0},
            'ollama:qwen2.5-coder:7b': {'input': 0, 'output': 0},

            # OpenRouter models (approximate costs)
            'openrouter:anthropic/claude-3.5-sonnet': {'input': 0.3, 'output': 1.5},
            'openrouter:openai/gpt-4': {'input': 0.3, 'output': 0.6},
            'openrouter:openai/gpt-3.5-turbo': {'input': 0.05, 'output': 0.15},
        }

        # In-memory cost tracking
        self._daily_costs = defaultdict(lambda: defaultdict(float))  # date -> backend -> cost
        self._monthly_costs = defaultdict(lambda: defaultdict(float))  # month -> backend -> cost
        self._request_counts = defaultdict(lambda: defaultdict(int))  # date -> backend -> count

        # Load existing costs from database
        self._load_costs_from_db()

    def _load_costs_from_db(self):
        """Load cost history from database"""
        try:
            with self.db.get_connection() as conn:
                # Load job costs from last 30 days
                cutoff = datetime.now() - timedelta(days=30)

                cursor = conn.execute("""
                    SELECT
                        DATE(created_at) as date,
                        backend_id,
                        SUM(cost_cents) as total_cost,
                        COUNT(*) as request_count
                    FROM jobs
                    WHERE created_at >= ? AND cost_cents > 0
                    GROUP BY DATE(created_at), backend_id
                """, (cutoff,))

                for row in cursor.fetchall():
                    # Get backend name
                    backend_cursor = conn.execute(
                        "SELECT name FROM backends WHERE id = ?",
                        (row['backend_id'],)
                    )
                    backend_row = backend_cursor.fetchone()

                    if backend_row:
                        backend_name = backend_row['name']
                        date_str = row['date']
                        cost = row['total_cost']
                        count = row['request_count']

                        self._daily_costs[date_str][backend_name] = cost
                        self._request_counts[date_str][backend_name] = count

                        # Also aggregate to monthly
                        month_str = date_str[:7]  # YYYY-MM
                        self._monthly_costs[month_str][backend_name] += cost

            self.logger.info("Loaded cost history from database")

        except Exception as e:
            self.logger.error(f"Error loading costs from database: {e}")

    def record_request_cost(
        self,
        backend_name: str,
        input_tokens: int,
        output_tokens: int,
        job_id: Optional[int] = None
    ) -> float:
        """
        Record cost for a request

        Args:
            backend_name: Name of backend used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            job_id: Optional job ID for database tracking

        Returns:
            Cost in cents
        """
        # Calculate cost
        rates = self.cost_rates.get(backend_name, {'input': 0, 'output': 0})
        input_cost = (input_tokens / 1000) * rates['input']
        output_cost = (output_tokens / 1000) * rates['output']
        total_cost = input_cost + output_cost

        # Record in memory
        today = datetime.now().strftime('%Y-%m-%d')
        month = datetime.now().strftime('%Y-%m')

        self._daily_costs[today][backend_name] += total_cost
        self._monthly_costs[month][backend_name] += total_cost
        self._request_counts[today][backend_name] += 1

        # Record in database if job_id provided
        if job_id:
            try:
                with self.db.get_connection() as conn:
                    conn.execute("""
                        UPDATE jobs
                        SET cost_cents = cost_cents + ?
                        WHERE id = ?
                    """, (total_cost, job_id))
                    conn.commit()
            except Exception as e:
                self.logger.error(f"Error recording cost to database: {e}")

        self.logger.debug(
            f"Recorded cost for {backend_name}: {total_cost:.4f} cents "
            f"({input_tokens} in, {output_tokens} out)"
        )

        return total_cost

    def get_daily_cost(self, date: Optional[datetime] = None) -> float:
        """Get total cost for a day"""
        date_str = (date or datetime.now()).strftime('%Y-%m-%d')
        return sum(self._daily_costs[date_str].values())

    def get_monthly_cost(self, date: Optional[datetime] = None) -> float:
        """Get total cost for a month"""
        month_str = (date or datetime.now()).strftime('%Y-%m')
        return sum(self._monthly_costs[month_str].values())

    def get_backend_daily_cost(self, backend_name: str, date: Optional[datetime] = None) -> float:
        """Get cost for a specific backend on a day"""
        date_str = (date or datetime.now()).strftime('%Y-%m-%d')
        return self._daily_costs[date_str].get(backend_name, 0.0)

    def get_daily_budget_remaining(self) -> float:
        """Get remaining daily budget in cents"""
        today_cost = self.get_daily_cost()
        return max(0, self.daily_budget_cents - today_cost)

    def get_monthly_budget_remaining(self) -> float:
        """Get remaining monthly budget in cents"""
        month_cost = self.get_monthly_cost()
        return max(0, self.monthly_budget_cents - month_cost)

    def is_within_budget(self, estimated_cost_cents: float = 0) -> bool:
        """Check if estimated cost would be within budget"""
        remaining = self.get_daily_budget_remaining()
        return estimated_cost_cents <= remaining

    def can_afford_request(
        self,
        backend_name: str,
        estimated_tokens: int = 1000
    ) -> bool:
        """Check if we can afford a request on this backend"""
        # Local backends are always affordable
        rates = self.cost_rates.get(backend_name, {'input': 0, 'output': 0})
        if rates['input'] == 0 and rates['output'] == 0:
            return True

        # Estimate cost (assuming 50/50 input/output split)
        estimated_cost = (
            (estimated_tokens * 0.5 / 1000) * rates['input'] +
            (estimated_tokens * 0.5 / 1000) * rates['output']
        )

        return self.is_within_budget(estimated_cost)

    def get_cost_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> CostReport:
        """
        Generate comprehensive cost report

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to today)

        Returns:
            CostReport object
        """
        end = end_date or datetime.now()
        start = start_date or (end - timedelta(days=30))

        # Aggregate costs
        total_cost = 0.0
        total_requests = 0
        by_backend = defaultdict(lambda: {'cost': 0.0, 'requests': 0})
        by_day = {}

        # Iterate through date range
        current = start
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')

            # Daily total
            day_cost = sum(self._daily_costs[date_str].values())
            by_day[date_str] = day_cost
            total_cost += day_cost

            # By backend
            for backend, cost in self._daily_costs[date_str].items():
                by_backend[backend]['cost'] += cost
                by_backend[backend]['requests'] += self._request_counts[date_str][backend]
                total_requests += self._request_counts[date_str][backend]

            current += timedelta(days=1)

        # Calculate averages
        for backend in by_backend:
            if by_backend[backend]['requests'] > 0:
                by_backend[backend]['cost_per_request'] = (
                    by_backend[backend]['cost'] / by_backend[backend]['requests']
                )
            else:
                by_backend[backend]['cost_per_request'] = 0.0

        # Budget calculations
        days_in_range = (end - start).days + 1
        budget_limit = self.daily_budget_cents * days_in_range
        budget_remaining = max(0, budget_limit - total_cost)
        budget_utilization = total_cost / budget_limit if budget_limit > 0 else 0

        return CostReport(
            start_date=start,
            end_date=end,
            total_cost_cents=total_cost,
            total_requests=total_requests,
            cost_per_request=total_cost / total_requests if total_requests > 0 else 0,
            by_backend=dict(by_backend),
            by_day=by_day,
            budget_limit_cents=budget_limit,
            budget_remaining_cents=budget_remaining,
            budget_utilization=budget_utilization
        )

    def get_most_expensive_backends(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most expensive backends this month"""
        month_str = datetime.now().strftime('%Y-%m')
        backend_costs = self._monthly_costs[month_str]

        sorted_backends = sorted(
            backend_costs.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {
                'backend': backend,
                'cost_cents': cost,
                'cost_dollars': cost / 100
            }
            for backend, cost in sorted_backends
        ]

    def get_cost_optimization_suggestions(self) -> List[str]:
        """Get suggestions for cost optimization"""
        suggestions = []

        # Check if approaching budget limits
        daily_remaining = self.get_daily_budget_remaining()
        daily_used_pct = (
            (self.daily_budget_cents - daily_remaining) / self.daily_budget_cents
            if self.daily_budget_cents > 0 else 0
        )

        if daily_used_pct > 0.8:
            suggestions.append(
                f"Daily budget {daily_used_pct:.0%} used - consider using more local backends"
            )

        # Check backend costs
        report = self.get_cost_report(
            start_date=datetime.now() - timedelta(days=7)
        )

        for backend, stats in report.by_backend.items():
            if stats['cost'] > 0 and backend.startswith('ollama:'):
                # This shouldn't happen
                suggestions.append(
                    f"Warning: {backend} showing costs but should be free (local)"
                )
            elif stats['cost_per_request'] > 5:  # More than 5 cents per request
                suggestions.append(
                    f"{backend} averaging {stats['cost_per_request']:.2f}¢ per request - "
                    f"consider alternatives for high-volume tasks"
                )

        # Check if free alternatives available
        if report.total_cost_cents > 0:
            suggestions.append(
                "Cost-saving tip: Ollama backends are free and suitable for many tasks"
            )

        return suggestions

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for dashboard"""
        return {
            'today': {
                'cost_cents': self.get_daily_cost(),
                'budget_cents': self.daily_budget_cents,
                'remaining_cents': self.get_daily_budget_remaining(),
                'utilization': (
                    self.get_daily_cost() / self.daily_budget_cents
                    if self.daily_budget_cents > 0 else 0
                )
            },
            'month': {
                'cost_cents': self.get_monthly_cost(),
                'budget_cents': self.monthly_budget_cents,
                'remaining_cents': self.get_monthly_budget_remaining(),
                'utilization': (
                    self.get_monthly_cost() / self.monthly_budget_cents
                    if self.monthly_budget_cents > 0 else 0
                )
            },
            'most_expensive_backends': self.get_most_expensive_backends(3),
            'suggestions': self.get_cost_optimization_suggestions()
        }
