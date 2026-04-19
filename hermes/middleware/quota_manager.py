"""
Advanced Quota Management System for Hermes AI Assistant

This module provides comprehensive quota management including dynamic quotas,
fair share algorithms, quota inheritance, and automated quota adjustments.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class QuotaPeriod(Enum):
    """Quota reset periods"""
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class QuotaStrategy(Enum):
    """Quota allocation strategies"""
    FIXED = "fixed"
    PROPORTIONAL = "proportional"
    FAIR_SHARE = "fair_share"
    PRIORITY_BASED = "priority_based"
    DEMAND_BASED = "demand_based"
    HYBRID = "hybrid"


class QuotaType(Enum):
    """Types of quotas"""
    TOKENS = "tokens"
    REQUESTS = "requests"
    CPU_TIME = "cpu_time"
    MEMORY = "memory"
    STORAGE = "storage"
    BANDWIDTH = "bandwidth"
    CUSTOM = "custom"


@dataclass
class QuotaDefinition:
    """Quota definition"""
    quota_type: QuotaType
    period: QuotaPeriod
    limit: int
    strategy: QuotaStrategy = QuotaStrategy.FIXED
    priority: int = 0
    is_hard_limit: bool = True
    auto_scale: bool = False
    burst_allowed: bool = False
    burst_multiplier: float = 1.5
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuotaAllocation:
    """Individual quota allocation"""
    client_id: str
    quota_type: QuotaType
    allocated: int
    used: int
    remaining: int
    period_start: datetime
    period_end: datetime
    last_updated: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuotaUsage:
    """Quota usage tracking"""
    client_id: str
    quota_type: QuotaType
    usage: int
    timestamp: datetime
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class QuotaAdjustmentRule(ABC):
    """Base class for quota adjustment rules"""

    @abstractmethod
    async def should_adjust(self, allocation: QuotaAllocation, usage_history: List[QuotaUsage]) -> bool:
        """Determine if quota should be adjusted"""
        pass

    @abstractmethod
    async def calculate_adjustment(self, allocation: QuotaAllocation, usage_history: List[QuotaUsage]) -> int:
        """Calculate quota adjustment amount"""
        pass


class UsageBasedAdjustment(QuotaAdjustmentRule):
    """Adjust quota based on usage patterns"""

    def __init__(self, threshold: float = 0.8, adjustment_factor: float = 1.2):
        self.threshold = threshold
        self.adjustment_factor = adjustment_factor

    async def should_adjust(self, allocation: QuotaAllocation, usage_history: List[QuotaUsage]) -> bool:
        """Adjust if usage exceeds threshold consistently"""
        if len(usage_history) < 3:
            return False

        # Calculate average usage over last 3 periods
        recent_usage = sum(u.usage for u in usage_history[-3:]) / 3
        usage_ratio = recent_usage / allocation.allocated

        return usage_ratio >= self.threshold

    async def calculate_adjustment(self, allocation: QuotaAllocation, usage_history: List[QuotaUsage]) -> int:
        """Calculate adjustment amount"""
        recent_usage = sum(u.usage for u in usage_history[-3:]) / 3
        suggested_quota = int(recent_usage * self.adjustment_factor)
        return suggested_quota - allocation.allocated


class FairShareAdjustment(QuotaAdjustmentRule):
    """Adjust quota for fair share among clients"""

    def __init__(self, fairness_threshold: float = 0.3):
        self.fairness_threshold = fairness_threshold

    async def should_adjust(self, allocation: QuotaAllocation, usage_history: List[QuotaUsage]) -> bool:
        """Adjust if client is significantly under-utilizing quota"""
        if len(usage_history) < 2:
            return False

        recent_usage = usage_history[-1].usage
        usage_ratio = recent_usage / allocation.allocated

        return usage_ratio <= self.fairness_threshold

    async def calculate_adjustment(self, allocation: QuotaAllocation, usage_history: List[QuotaUsage]) -> int:
        """Calculate reduction for fair share"""
        recent_usage = usage_history[-1].usage
        suggested_quota = max(int(recent_usage * 1.5), allocation.allocated // 2)
        return suggested_quota - allocation.allocated


class QuotaManager:
    """
    Advanced quota management system
    """

    def __init__(self, storage_backend=None):
        self.storage_backend = storage_backend
        self.allocations: Dict[str, Dict[QuotaType, QuotaAllocation]] = {}
        self.usage_history: Dict[str, List[QuotaUsage]] = {}
        self.quota_definitions: Dict[str, QuotaDefinition] = {}
        self.adjustment_rules: List[QuotaAdjustmentRule] = []
        self.inheritance_rules: Dict[str, str] = {}  # parent -> child relationships

        # Initialize default quota definitions
        self._initialize_default_quotas()

        # Initialize adjustment rules
        self._initialize_adjustment_rules()

    def _initialize_default_quotas(self):
        """Initialize default quota definitions"""
        default_quotas = {
            "anonymous_tokens": QuotaDefinition(
                quota_type=QuotaType.TOKENS,
                period=QuotaPeriod.DAILY,
                limit=10000,
                strategy=QuotaStrategy.FIXED,
                is_hard_limit=True
            ),
            "basic_tokens": QuotaDefinition(
                quota_type=QuotaType.TOKENS,
                period=QuotaPeriod.MONTHLY,
                limit=1000000,
                strategy=QuotaStrategy.FIXED,
                is_hard_limit=True,
                auto_scale=True
            ),
            "premium_tokens": QuotaDefinition(
                quota_type=QuotaType.TOKENS,
                period=QuotaPeriod.MONTHLY,
                limit=10000000,
                strategy=QuotaStrategy.PROPORTIONAL,
                is_hard_limit=False,
                auto_scale=True,
                burst_allowed=True,
                burst_multiplier=2.0
            ),
            "enterprise_tokens": QuotaDefinition(
                quota_type=QuotaType.TOKENS,
                period=QuotaPeriod.MONTHLY,
                limit=100000000,
                strategy=QuotaStrategy.HYBRID,
                is_hard_limit=False,
                auto_scale=True,
                burst_allowed=True,
                burst_multiplier=3.0
            ),
        }

        self.quota_definitions.update(default_quotas)

    def _initialize_adjustment_rules(self):
        """Initialize quota adjustment rules"""
        self.adjustment_rules = [
            UsageBasedAdjustment(threshold=0.8, adjustment_factor=1.2),
            FairShareAdjustment(fairness_threshold=0.3),
        ]

    async def allocate_quota(
        self,
        client_id: str,
        quota_definition_key: str,
        custom_limit: Optional[int] = None,
        priority: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> QuotaAllocation:
        """
        Allocate quota to a client
        """
        quota_def = self.quota_definitions.get(quota_definition_key)
        if not quota_def:
            raise ValueError(f"Quota definition '{quota_definition_key}' not found")

        # Calculate allocation based on strategy
        allocated_amount = await self._calculate_allocation(
            client_id, quota_def, custom_limit, priority
        )

        # Create allocation
        now = datetime.now()
        period_start, period_end = self._get_period_bounds(quota_def.period, now)

        allocation = QuotaAllocation(
            client_id=client_id,
            quota_type=quota_def.quota_type,
            allocated=allocated_amount,
            used=0,
            remaining=allocated_amount,
            period_start=period_start,
            period_end=period_end,
            last_updated=now,
            metadata=metadata or {}
        )

        # Store allocation
        if client_id not in self.allocations:
            self.allocations[client_id] = {}
        self.allocations[client_id][quota_def.quota_type] = allocation

        # Store in backend if available
        if self.storage_backend:
            await self.storage_backend.store_allocation(allocation)

        logger.info(f"Allocated {allocated_amount} {quota_def.quota_type.value} to client {client_id}")
        return allocation

    async def _calculate_allocation(
        self,
        client_id: str,
        quota_def: QuotaDefinition,
        custom_limit: Optional[int],
        priority: Optional[int]
    ) -> int:
        """Calculate allocation amount based on strategy"""
        base_limit = custom_limit or quota_def.limit

        if quota_def.strategy == QuotaStrategy.FIXED:
            return base_limit

        elif quota_def.strategy == QuotaStrategy.PROPORTIONAL:
            # Calculate based on client's historical usage
            return await self._calculate_proportional_allocation(client_id, quota_def, base_limit)

        elif quota_def.strategy == QuotaStrategy.FAIR_SHARE:
            # Calculate fair share among all clients
            return await self._calculate_fair_share_allocation(client_id, quota_def, base_limit)

        elif quota_def.strategy == QuotaStrategy.PRIORITY_BASED:
            # Calculate based on client priority
            client_priority = priority or 0
            return await self._calculate_priority_allocation(client_id, quota_def, base_limit, client_priority)

        elif quota_def.strategy == QuotaStrategy.DEMAND_BASED:
            # Calculate based on current demand
            return await self._calculate_demand_based_allocation(client_id, quota_def, base_limit)

        elif quota_def.strategy == QuotaStrategy.HYBRID:
            # Combine multiple strategies
            return await self._calculate_hybrid_allocation(client_id, quota_def, base_limit, priority)

        else:
            return base_limit

    async def _calculate_proportional_allocation(self, client_id: str, quota_def: QuotaDefinition, base_limit: int) -> int:
        """Calculate proportional allocation based on usage history"""
        if client_id not in self.usage_history:
            return base_limit

        # Get usage history for this quota type
        usage_history = [
            u for u in self.usage_history[client_id]
            if u.quota_type == quota_def.quota_type
        ]

        if not usage_history:
            return base_limit

        # Calculate average usage
        avg_usage = sum(u.usage for u in usage_history[-10:]) / min(10, len(usage_history))

        # Return average usage with some buffer
        return int(avg_usage * 1.2)

    async def _calculate_fair_share_allocation(self, client_id: str, quota_def: QuotaDefinition, base_limit: int) -> int:
        """Calculate fair share allocation"""
        # Count clients with this quota type
        client_count = sum(
            1 for allocations in self.allocations.values()
            if quota_def.quota_type in allocations
        )

        if client_count == 0:
            return base_limit

        # Distribute evenly among clients
        return base_limit // max(1, client_count)

    async def _calculate_priority_allocation(self, client_id: str, quota_def: QuotaDefinition, base_limit: int, priority: int) -> int:
        """Calculate priority-based allocation"""
        # Get all clients with their priorities
        client_priorities = []
        for allocations in self.allocations.values():
            for allocation in allocations.values():
                if allocation.quota_type == quota_def.quota_type:
                    client_priorities.append(allocation.metadata.get("priority", 0))

        if not client_priorities:
            return base_limit

        # Calculate priority weight
        total_priority = sum(client_priorities) + priority  # Include current client
        if total_priority == 0:
            return base_limit // (len(client_priorities) + 1)

        weight = priority / total_priority
        return int(base_limit * weight)

    async def _calculate_demand_based_allocation(self, client_id: str, quota_def: QuotaDefinition, base_limit: int) -> int:
        """Calculate demand-based allocation"""
        # This would integrate with demand forecasting
        # For now, return base limit
        return base_limit

    async def _calculate_hybrid_allocation(self, client_id: str, quota_def: QuotaDefinition, base_limit: int, priority: Optional[int]) -> int:
        """Calculate hybrid allocation combining multiple strategies"""
        # Get allocations from different strategies
        proportional = await self._calculate_proportional_allocation(client_id, quota_def, base_limit)
        fair_share = await self._calculate_fair_share_allocation(client_id, quota_def, base_limit)

        # Weight the strategies
        weights = {
            "proportional": 0.4,
            "fair_share": 0.3,
            "priority": 0.3 if priority is not None else 0.0
        }

        allocation = int(
            proportional * weights["proportional"] +
            fair_share * weights["fair_share"]
        )

        if priority is not None:
            priority_alloc = await self._calculate_priority_allocation(client_id, quota_def, base_limit, priority)
            allocation = int(allocation + priority_alloc * weights["priority"])

        return min(allocation, base_limit)

    def _get_period_bounds(self, period: QuotaPeriod, reference_time: datetime) -> tuple[datetime, datetime]:
        """Get period start and end times"""
        if period == QuotaPeriod.MINUTELY:
            start = reference_time.replace(second=0, microsecond=0)
            end = start + timedelta(minutes=1)
        elif period == QuotaPeriod.HOURLY:
            start = reference_time.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        elif period == QuotaPeriod.DAILY:
            start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif period == QuotaPeriod.WEEKLY:
            # Start of week (Monday)
            days_since_monday = reference_time.weekday()
            start = (reference_time - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(weeks=1)
        elif period == QuotaPeriod.MONTHLY:
            start = reference_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Next month
            if reference_time.month == 12:
                end = start.replace(year=reference_time.year + 1, month=1)
            else:
                end = start.replace(month=reference_time.month + 1)
        elif period == QuotaPeriod.QUARTERLY:
            # Start of quarter
            quarter = (reference_time.month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            start = reference_time.replace(month=start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=90)  # Approximate
        elif period == QuotaPeriod.YEARLY:
            start = reference_time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=reference_time.year + 1)
        else:
            start = reference_time
            end = reference_time + timedelta(hours=1)

        return start, end

    async def consume_quota(
        self,
        client_id: str,
        quota_type: QuotaType,
        amount: int,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, QuotaAllocation]:
        """
        Consume quota for a client
        """
        # Get allocation
        allocation = await self.get_allocation(client_id, quota_type)
        if not allocation:
            raise ValueError(f"No allocation found for client {client_id}, quota type {quota_type.value}")

        # Check if allocation needs reset
        now = datetime.now()
        if now >= allocation.period_end:
            allocation = await self.reset_allocation(client_id, quota_type)

        # Check if quota is available
        if allocation.remaining < amount:
            return False, allocation

        # Consume quota
        allocation.used += amount
        allocation.remaining -= amount
        allocation.last_updated = now

        # Record usage
        usage = QuotaUsage(
            client_id=client_id,
            quota_type=quota_type,
            usage=amount,
            timestamp=now,
            request_id=request_id,
            metadata=metadata or {}
        )

        if client_id not in self.usage_history:
            self.usage_history[client_id] = []
        self.usage_history[client_id].append(usage)

        # Store in backend if available
        if self.storage_backend:
            await self.storage_backend.store_usage(usage)
            await self.storage_backend.update_allocation(allocation)

        # Check if adjustment is needed
        await self._check_for_adjustment(allocation)

        return True, allocation

    async def get_allocation(self, client_id: str, quota_type: QuotaType) -> Optional[QuotaAllocation]:
        """Get quota allocation for client"""
        if client_id not in self.allocations:
            return None

        return self.allocations[client_id].get(quota_type)

    async def reset_allocation(self, client_id: str, quota_type: QuotaType) -> QuotaAllocation:
        """Reset quota allocation for new period"""
        current_allocation = self.allocations[client_id][quota_type]
        now = datetime.now()

        # Get period bounds
        quota_def = None
        for def_key, def_val in self.quota_definitions.items():
            if def_val.quota_type == quota_type:
                quota_def = def_val
                break

        if not quota_def:
            raise ValueError(f"No quota definition found for type {quota_type.value}")

        period_start, period_end = self._get_period_bounds(quota_def.period, now)

        # Recalculate allocation
        allocated_amount = await self._calculate_allocation(
            client_id, quota_def, current_allocation.allocated, current_allocation.metadata.get("priority")
        )

        # Create new allocation
        new_allocation = QuotaAllocation(
            client_id=client_id,
            quota_type=quota_type,
            allocated=allocated_amount,
            used=0,
            remaining=allocated_amount,
            period_start=period_start,
            period_end=period_end,
            last_updated=now,
            metadata=current_allocation.metadata.copy()
        )

        # Update allocation
        self.allocations[client_id][quota_type] = new_allocation

        # Store in backend if available
        if self.storage_backend:
            await self.storage_backend.store_allocation(new_allocation)

        return new_allocation

    async def _check_for_adjustment(self, allocation: QuotaAllocation):
        """Check if quota adjustment is needed"""
        # Get usage history for this client and quota type
        usage_history = [
            u for u in self.usage_history.get(allocation.client_id, [])
            if u.quota_type == allocation.quota_type
        ]

        # Check each adjustment rule
        for rule in self.adjustment_rules:
            try:
                if await rule.should_adjust(allocation, usage_history):
                    adjustment = await rule.calculate_adjustment(allocation, usage_history)
                    if adjustment != 0:
                        await self._apply_adjustment(allocation, adjustment)
                        logger.info(f"Applied quota adjustment of {adjustment} for client {allocation.client_id}")
            except Exception as e:
                logger.error(f"Error in quota adjustment rule: {e}")

    async def _apply_adjustment(self, allocation: QuotaAllocation, adjustment: int):
        """Apply quota adjustment"""
        new_allocated = max(0, allocation.allocated + adjustment)
        allocation.allocated = new_allocated
        allocation.remaining = new_allocated - allocation.used
        allocation.last_updated = datetime.now()

        # Store in backend if available
        if self.storage_backend:
            await self.storage_backend.update_allocation(allocation)

    async def get_client_quotas(self, client_id: str) -> Dict[str, QuotaAllocation]:
        """Get all quotas for a client"""
        return self.allocations.get(client_id, {})

    async def get_quota_usage(self, client_id: str, quota_type: QuotaType, period_days: int = 30) -> List[QuotaUsage]:
        """Get quota usage history for a client"""
        if client_id not in self.usage_history:
            return []

        cutoff_date = datetime.now() - timedelta(days=period_days)
        return [
            u for u in self.usage_history[client_id]
            if u.quota_type == quota_type and u.timestamp >= cutoff_date
        ]

    async def get_system_overview(self) -> Dict[str, Any]:
        """Get system-wide quota overview"""
        now = datetime.now()
        total_clients = len(self.allocations)
        total_allocated = 0
        total_used = 0
        quota_types = set()

        for client_allocations in self.allocations.values():
            for allocation in client_allocations.values():
                total_allocated += allocation.allocated
                total_used += allocation.used
                quota_types.add(allocation.quota_type.value)

        usage_percentage = (total_used / total_allocated * 100) if total_allocated > 0 else 0

        return {
            "timestamp": now.isoformat(),
            "total_clients": total_clients,
            "total_allocated": total_allocated,
            "total_used": total_used,
            "total_remaining": total_allocated - total_used,
            "usage_percentage": round(usage_percentage, 2),
            "quota_types": list(quota_types),
            "quota_definitions": len(self.quota_definitions),
            "adjustment_rules": len(self.adjustment_rules)
        }

    async def add_quota_definition(self, key: str, definition: QuotaDefinition):
        """Add a new quota definition"""
        self.quota_definitions[key] = definition
        logger.info(f"Added quota definition: {key}")

    async def add_adjustment_rule(self, rule: QuotaAdjustmentRule):
        """Add a new quota adjustment rule"""
        self.adjustment_rules.append(rule)
        logger.info(f"Added quota adjustment rule: {rule.__class__.__name__}")

    async def remove_client_quotas(self, client_id: str):
        """Remove all quotas for a client"""
        if client_id in self.allocations:
            del self.allocations[client_id]
        if client_id in self.usage_history:
            del self.usage_history[client_id]

        # Remove from backend if available
        if self.storage_backend:
            await self.storage_backend.remove_client_data(client_id)

        logger.info(f"Removed all quotas for client {client_id}")


# Storage backend interface
class QuotaStorageBackend(ABC):
    """Interface for quota storage backends"""

    @abstractmethod
    async def store_allocation(self, allocation: QuotaAllocation):
        pass

    @abstractmethod
    async def update_allocation(self, allocation: QuotaAllocation):
        pass

    @abstractmethod
    async def store_usage(self, usage: QuotaUsage):
        pass

    @abstractmethod
    async def remove_client_data(self, client_id: str):
        pass


# Redis storage backend
class RedisQuotaStorage(QuotaStorageBackend):
    """Redis-based quota storage backend"""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def store_allocation(self, allocation: QuotaAllocation):
        """Store allocation in Redis"""
        key = f"quota:allocation:{allocation.client_id}:{allocation.quota_type.value}"
        data = {
            "allocated": allocation.allocated,
            "used": allocation.used,
            "remaining": allocation.remaining,
            "period_start": allocation.period_start.isoformat(),
            "period_end": allocation.period_end.isoformat(),
            "last_updated": allocation.last_updated.isoformat(),
            "metadata": json.dumps(allocation.metadata)
        }
        await self.redis.hset(key, mapping=data)

    async def update_allocation(self, allocation: QuotaAllocation):
        """Update allocation in Redis"""
        await self.store_allocation(allocation)

    async def store_usage(self, usage: QuotaUsage):
        """Store usage in Redis"""
        key = f"quota:usage:{usage.client_id}:{usage.quota_type.value}"
        data = {
            "usage": usage.usage,
            "timestamp": usage.timestamp.isoformat(),
            "request_id": usage.request_id or "",
            "metadata": json.dumps(usage.metadata)
        }
        await self.redis.lpush(key, json.dumps(data))
        await self.redis.expire(key, 86400 * 30)  # Keep for 30 days

    async def remove_client_data(self, client_id: str):
        """Remove all client data from Redis"""
        pattern = f"quota:*:{client_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)


# Global quota manager instance
quota_manager = QuotaManager()


async def initialize_quota_manager(storage_backend: Optional[QuotaStorageBackend] = None):
    """Initialize the global quota manager"""
    global quota_manager
    quota_manager = QuotaManager(storage_backend)