"""
Database query optimization and performance tuning module.

This module provides advanced database optimization features including
query analysis, index optimization, connection pooling, and performance
monitoring.
"""

import asyncio
import time
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from collections import defaultdict, Counter
import json
import logging

import asyncpg
import redis.asyncio as redis
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import QueuePool
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    """Database query execution plan."""
    query: str
    plan: List[Dict[str, Any]]
    cost: float
    execution_time: float
    rows_examined: int
    indexes_used: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class IndexRecommendation:
    """Index optimization recommendation."""
    table_name: str
    columns: List[str]
    index_type: str
    estimated_improvement: float
    current_usage: Optional[int] = None
    reason: str = ""


class QueryAnalyzer:
    """Analyzes and optimizes database queries."""

    def __init__(self, db_engine):
        self.db_engine = db_engine
        self.query_patterns = {
            'slow_select': re.compile(r'SELECT.*FROM.*WHERE', re.IGNORECASE),
            'missing_index': re.compile(r'WHERE.*=\s*\?', re.IGNORECASE),
            'join_optimization': re.compile(r'JOIN.*ON', re.IGNORECASE),
            'subquery_optimization': re.compile(r'EXISTS\s*\(|IN\s*\(', re.IGNORECASE)
        }

    async def analyze_query(self, query: str, params: Dict[str, Any] = None) -> QueryPlan:
        """Analyze a query and return execution plan."""
        async with self.db_engine.connect() as conn:
            # Get execution plan
            plan_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"

            try:
                if params:
                    result = await conn.execute(text(plan_query), params)
                else:
                    result = await conn.execute(text(plan_query))

                plan_data = result.fetchone()[0][0]

                # Extract plan information
                total_cost = self._extract_total_cost(plan_data)
                execution_time = self._extract_execution_time(plan_data)
                rows_examined = self._extract_rows_examined(plan_data)
                indexes_used = self._extract_indexes_used(plan_data)

                # Generate recommendations
                recommendations = await self._generate_recommendations(query, plan_data)

                return QueryPlan(
                    query=query,
                    plan=plan_data,
                    cost=total_cost,
                    execution_time=execution_time,
                    rows_examined=rows_examined,
                    indexes_used=indexes_used,
                    recommendations=recommendations
                )

            except Exception as e:
                logger.error(f"Error analyzing query: {e}")
                return QueryPlan(
                    query=query,
                    plan=[],
                    cost=0.0,
                    execution_time=0.0,
                    rows_examined=0,
                    recommendations=[f"Query analysis failed: {str(e)}"]
                )

    def _extract_total_cost(self, plan_data: List[Dict[str, Any]]) -> float:
        """Extract total cost from execution plan."""
        if plan_data and 'Plan' in plan_data[0]:
            return float(plan_data[0]['Plan'].get('Total Cost', 0.0))
        return 0.0

    def _extract_execution_time(self, plan_data: List[Dict[str, Any]]) -> float:
        """Extract execution time from plan."""
        if plan_data and 'Execution Time' in plan_data[0]:
            return float(plan_data[0]['Execution Time'])
        return 0.0

    def _extract_rows_examined(self, plan_data: List[Dict[str, Any]]) -> int:
        """Extract number of rows examined."""
        def count_rows(plan):
            if 'Actual Rows' in plan:
                return int(plan['Actual Rows'])
            if 'Plan Rows' in plan:
                return int(plan['Plan Rows'])
            return 0

        total_rows = 0
        for item in plan_data:
            if 'Plan' in item:
                total_rows += self._count_rows_recursive(item['Plan'])
        return total_rows

    def _count_rows_recursive(self, plan: Dict[str, Any]) -> int:
        """Recursively count rows in execution plan."""
        rows = int(plan.get('Actual Rows', plan.get('Plan Rows', 0)))

        if 'Plans' in plan:
            for subplan in plan['Plans']:
                rows += self._count_rows_recursive(subplan)

        return rows

    def _extract_indexes_used(self, plan_data: List[Dict[str, Any]]) -> List[str]:
        """Extract indexes used from execution plan."""
        indexes = []

        def extract_from_node(node):
            if 'Index Name' in node:
                indexes.append(node['Index Name'])
            if 'Index Scan' in node.get('Node Type', ''):
                indexes.append(node.get('Relation Name', ''))
            if 'Plans' in node:
                for subplan in node['Plans']:
                    extract_from_node(subplan)

        for item in plan_data:
            if 'Plan' in item:
                extract_from_node(item['Plan'])

        return list(set(indexes))

    async def _generate_recommendations(self, query: str, plan_data: List[Dict[str, Any]]) -> List[str]:
        """Generate optimization recommendations based on query and plan."""
        recommendations = []

        # Check for sequential scans
        if self._has_sequential_scan(plan_data):
            recommendations.append("Consider adding indexes to avoid sequential scans")

        # Check for high cost
        if self._extract_total_cost(plan_data) > 1000:
            recommendations.append("Query has high cost - consider query restructuring")

        # Check for missing LIMIT
        if 'LIMIT' not in query.upper() and 'INSERT' not in query.upper():
            recommendations.append("Consider adding LIMIT clause to restrict result set")

        # Check for JOIN operations
        if 'JOIN' in query.upper():
            if not self._has_join_indexes(plan_data):
                recommendations.append("Consider adding indexes on JOIN columns")

        return recommendations

    def _has_sequential_scan(self, plan_data: List[Dict[str, Any]]) -> bool:
        """Check if plan contains sequential scans."""
        def check_node(node):
            if 'Seq Scan' in node.get('Node Type', ''):
                return True
            if 'Plans' in node:
                return any(check_node(subplan) for subplan in node['Plans'])
            return False

        for item in plan_data:
            if 'Plan' in item and check_node(item['Plan']):
                return True
        return False

    def _has_join_indexes(self, plan_data: List[Dict[str, Any]]) -> bool:
        """Check if JOIN operations use indexes."""
        return any('Index Scan' in node.get('Node Type', '')
                  for item in plan_data
                  for node in self._traverse_plan(item.get('Plan', {})))

    def _traverse_plan(self, node):
        """Traverse execution plan tree."""
        yield node
        if 'Plans' in node:
            for subplan in node['Plans']:
                yield from self._traverse_plan(subplan)


class IndexOptimizer:
    """Analyzes and optimizes database indexes."""

    def __init__(self, db_engine):
        self.db_engine = db_engine
        self.index_usage_stats: Dict[str, Dict[str, Any]] = {}

    async def analyze_index_usage(self) -> Dict[str, Any]:
        """Analyze current index usage statistics."""
        async with self.db_engine.connect() as conn:
            # Get index statistics
            index_stats_query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size
            FROM pg_stat_user_indexes
            ORDER BY idx_scan DESC;
            """

            result = await conn.execute(text(index_stats_query))
            indexes = result.fetchall()

            # Get unused indexes
            unused_indexes_query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
            ORDER BY pg_relation_size(indexrelid) DESC;
            """

            result = await conn.execute(text(unused_indexes_query))
            unused_indexes = result.fetchall()

            return {
                'total_indexes': len(indexes),
                'unused_indexes': len(unused_indexes),
                'index_details': [
                    {
                        'schema': row[0],
                        'table': row[1],
                        'name': row[2],
                        'scans': row[3],
                        'tuples_read': row[4],
                        'tuples_fetched': row[5],
                        'size': row[6]
                    }
                    for row in indexes
                ],
                'unused_index_details': [
                    {
                        'schema': row[0],
                        'table': row[1],
                        'name': row[2],
                        'size': row[3]
                    }
                    for row in unused_indexes
                ]
            }

    async def suggest_indexes(self, table_name: Optional[str] = None) -> List[IndexRecommendation]:
        """Suggest new indexes based on query patterns."""
        recommendations = []

        async with self.db_engine.connect() as conn:
            # Get slow queries
            slow_queries_query = """
            SELECT query, calls, total_time, mean_time
            FROM pg_stat_statements
            WHERE mean_time > 100  -- queries taking more than 100ms
            ORDER BY mean_time DESC
            LIMIT 20;
            """

            try:
                result = await conn.execute(text(slow_queries_query))
                slow_queries = result.fetchall()

                for query_row in slow_queries:
                    query = query_row[0]
                    recommendations.extend(await self._analyze_query_for_indexes(query))
            except Exception as e:
                logger.warning(f"Could not analyze slow queries: {e}")

            # Get foreign key relationships
            fk_query = """
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            """

            if table_name:
                fk_query += f" AND tc.table_name = '{table_name}'"

            result = await conn.execute(text(fk_query))
            foreign_keys = result.fetchall()

            for fk in foreign_keys:
                recommendations.append(IndexRecommendation(
                    table_name=fk[0],
                    columns=[fk[1]],
                    index_type='btree',
                    estimated_improvement=30.0,
                    reason=f"Foreign key column: {fk[0]}.{fk[1]} -> {fk[2]}.{fk[3]}"
                ))

        return recommendations

    async def _analyze_query_for_indexes(self, query: str) -> List[IndexRecommendation]:
        """Analyze a query and suggest indexes."""
        recommendations = []

        # Extract table and column patterns from WHERE clauses
        where_pattern = r'FROM\s+(\w+).*?WHERE\s+([^;]+)'
        matches = re.findall(where_pattern, query, re.IGNORECASE | re.DOTALL)

        for table_name, where_clause in matches:
            # Extract column references from WHERE clause
            column_pattern = r'(\w+)\s*='
            columns = re.findall(column_pattern, where_clause, re.IGNORECASE)

            if columns and len(columns) <= 3:  # Limit to 3 columns per index
                recommendations.append(IndexRecommendation(
                    table_name=table_name,
                    columns=list(set(columns)),
                    index_type='btree',
                    estimated_improvement=50.0,
                    reason=f"WHERE clause columns in slow query: {', '.join(columns)}"
                ))

        return recommendations

    async def create_recommended_index(self, recommendation: IndexRecommendation) -> bool:
        """Create a recommended index."""
        index_name = f"idx_{recommendation.table_name}_{'_'.join(recommendation.columns)}"

        create_index_query = f"""
        CREATE INDEX CONCURRENTLY {index_name}
        ON {recommendation.table_name}
        USING {recommendation.index_type} ({', '.join(recommendation.columns)});
        """

        try:
            async with self.db_engine.connect() as conn:
                await conn.execute(text(create_index_query))
                await conn.commit()
            logger.info(f"Created index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            return False

    async def drop_unused_index(self, schema: str, table_name: str, index_name: str) -> bool:
        """Drop an unused index."""
        drop_index_query = f"DROP INDEX CONCURRENTLY {schema}.{index_name};"

        try:
            async with self.db_engine.connect() as conn:
                await conn.execute(text(drop_index_query))
                await conn.commit()
            logger.info(f"Dropped unused index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop index {index_name}: {e}")
            return False


class ConnectionPoolOptimizer:
    """Optimizes database connection pool settings."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.current_pool_size = 5
        self.current_max_overflow = 10
        self.pool_timeout = 30
        self.pool_recycle = 3600

    def create_optimized_engine(self) -> AsyncSession:
        """Create an optimized database engine."""
        return create_async_engine(
            self.connection_string,
            poolclass=QueuePool,
            pool_size=self.current_pool_size,
            max_overflow=self.current_max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,
            echo=False  # Set to True for SQL logging in development
        )

    async def analyze_pool_performance(self, redis_client: redis.Redis) -> Dict[str, Any]:
        """Analyze connection pool performance."""
        pool_stats = await redis_client.hgetall("db_pool_stats")

        if not pool_stats:
            return {}

        return {
            'active_connections': int(pool_stats.get('active', 0)),
            'idle_connections': int(pool_stats.get('idle', 0)),
            'total_requests': int(pool_stats.get('total_requests', 0)),
            'average_wait_time': float(pool_stats.get('avg_wait_time', 0)),
            'timeouts': int(pool_stats.get('timeouts', 0)),
            'pool_utilization': (
                int(pool_stats.get('active', 0)) /
                (self.current_pool_size + self.current_max_overflow)
            ) * 100
        }

    def recommend_pool_settings(self, performance_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend optimal pool settings based on performance."""
        recommendations = {
            'current_pool_size': self.current_pool_size,
            'current_max_overflow': self.current_max_overflow,
            'recommended_pool_size': self.current_pool_size,
            'recommended_max_overflow': self.current_max_overflow,
            'reasoning': []
        }

        utilization = performance_stats.get('pool_utilization', 0)
        timeouts = performance_stats.get('timeouts', 0)
        avg_wait_time = performance_stats.get('average_wait_time', 0)

        # Increase pool size if high utilization
        if utilization > 80:
            recommendations['recommended_pool_size'] = min(
                self.current_pool_size + 2, 20
            )
            recommendations['reasoning'].append(
                f"High pool utilization ({utilization:.1f}%) - increasing pool size"
            )

        # Increase overflow if many timeouts
        if timeouts > 10:
            recommendations['recommended_max_overflow'] = min(
                self.current_max_overflow + 5, 30
            )
            recommendations['reasoning'].append(
                f"Many timeouts ({timeouts}) - increasing max overflow"
            )

        # Decrease if underutilized
        if utilization < 30 and timeouts == 0:
            recommendations['recommended_pool_size'] = max(
                self.current_pool_size - 1, 3
            )
            recommendations['reasoning'].append(
                f"Low pool utilization ({utilization:.1f}%) - decreasing pool size"
            )

        return recommendations


class QueryCacheManager:
    """Manages query result caching."""

    def __init__(self, redis_client: redis.Redis, default_ttl: int = 300):
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0
        }

    def _generate_cache_key(self, query: str, params: Dict[str, Any] = None) -> str:
        """Generate cache key for query."""
        query_hash = hash(query.strip().lower())
        params_hash = hash(json.dumps(params or {}, sort_keys=True))
        return f"query_cache:{query_hash}:{params_hash}"

    async def get_cached_result(self, query: str, params: Dict[str, Any] = None) -> Optional[List[Dict[str, Any]]]:
        """Get cached query result."""
        cache_key = self._generate_cache_key(query, params)

        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                self.cache_stats['hits'] += 1
                return json.loads(cached_data)
            else:
                self.cache_stats['misses'] += 1
                return None
        except Exception as e:
            logger.error(f"Error getting cached result: {e}")
            self.cache_stats['misses'] += 1
            return None

    async def cache_result(self, query: str, result: List[Dict[str, Any]],
                          params: Dict[str, Any] = None, ttl: Optional[int] = None) -> bool:
        """Cache query result."""
        cache_key = self._generate_cache_key(query, params)
        cache_ttl = ttl or self.default_ttl

        try:
            await self.redis.setex(
                cache_key,
                cache_ttl,
                json.dumps(result, default=str)
            )
            self.cache_stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"Error caching result: {e}")
            return False

    @asynccontextmanager
    async def cached_query(self, query: str, params: Dict[str, Any] = None,
                          ttl: Optional[int] = None):
        """Execute query with caching."""
        # Try to get from cache first
        cached_result = await self.get_cached_result(query, params)
        if cached_result is not None:
            yield cached_result
            return

        # Execute query and cache result
        yield None  # Signal that cache was miss

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'sets': self.cache_stats['sets'],
            'hit_rate_percent': hit_rate,
            'total_requests': total_requests
        }

    async def invalidate_cache(self, pattern: str = None) -> int:
        """Invalidate cached results."""
        if pattern:
            keys = await self.redis.keys(pattern)
        else:
            keys = await self.redis.keys("query_cache:*")

        if keys:
            deleted = await self.redis.delete(*keys)
            return deleted
        return 0


@asynccontextmanager
async def optimized_db_session(db_engine, cache_manager: Optional[QueryCacheManager] = None):
    """Create optimized database session with performance monitoring."""
    start_time = time.time()

    async with AsyncSession(db_engine) as session:
        try:
            yield session
        finally:
            execution_time = time.time() - start_time

            # Log slow sessions
            if execution_time > 1.0:
                logger.warning(f"Slow database session: {execution_time:.3f}s")


class DatabasePerformanceMonitor:
    """Comprehensive database performance monitoring."""

    def __init__(self, db_engine, redis_client: redis.Redis):
        self.db_engine = db_engine
        self.redis = redis_client
        self.query_analyzer = QueryAnalyzer(db_engine)
        self.index_optimizer = IndexOptimizer(db_engine)
        self.connection_optimizer = ConnectionPoolOptimizer(str(db_engine.url))
        self.cache_manager = QueryCacheManager(redis_client)
        self.slow_queries: List[Dict[str, Any]] = []
        self.max_slow_queries = 100

    @asynccontextmanager
    async def monitor_query(self, query: str, params: Dict[str, Any] = None):
        """Monitor and analyze query performance."""
        start_time = time.time()

        try:
            yield
        finally:
            execution_time = time.time() - start_time

            # Log slow queries
            if execution_time > 0.5:  # Slow query threshold
                await self._handle_slow_query(query, params, execution_time)

    async def _handle_slow_query(self, query: str, params: Dict[str, Any], execution_time: float):
        """Handle slow query logging and analysis."""
        slow_query_info = {
            'query': query,
            'params': params,
            'execution_time': execution_time,
            'timestamp': datetime.utcnow().isoformat(),
            'analysis': None
        }

        # Analyze the slow query
        try:
            analysis = await self.query_analyzer.analyze_query(query, params)
            slow_query_info['analysis'] = {
                'cost': analysis.cost,
                'recommendations': analysis.recommendations,
                'indexes_used': analysis.indexes_used
            }
        except Exception as e:
            logger.error(f"Error analyzing slow query: {e}")

        # Store slow query
        self.slow_queries.append(slow_query_info)
        if len(self.slow_queries) > self.max_slow_queries:
            self.slow_queries.pop(0)

        # Log warning
        logger.warning(f"Slow query detected: {execution_time:.3f}s - {query[:100]}...")

        # Store in Redis for dashboard
        await self.redis.lpush(
            "slow_queries",
            json.dumps(slow_query_info, default=str)
        )
        await self.redis.ltrim("slow_queries", 0, 99)  # Keep last 100

    async def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        # Get index usage
        index_usage = await self.index_optimizer.analyze_index_usage()

        # Get pool performance
        pool_performance = await self.connection_optimizer.analyze_pool_performance(self.redis)

        # Get cache stats
        cache_stats = self.cache_manager.get_cache_stats()

        # Analyze slow queries
        slow_query_analysis = self._analyze_slow_queries()

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'index_usage': index_usage,
            'pool_performance': pool_performance,
            'cache_performance': cache_stats,
            'slow_queries': {
                'total_count': len(self.slow_queries),
                'analysis': slow_query_analysis,
                'recent': self.slow_queries[-10:] if self.slow_queries else []
            }
        }

    def _analyze_slow_queries(self) -> Dict[str, Any]:
        """Analyze patterns in slow queries."""
        if not self.slow_queries:
            return {}

        # Group by execution time ranges
        time_ranges = {
            '0.5-1.0s': 0,
            '1.0-2.0s': 0,
            '2.0-5.0s': 0,
            '5.0s+': 0
        }

        total_time = 0
        for query in self.slow_queries:
            exec_time = query['execution_time']
            total_time += exec_time

            if exec_time < 1.0:
                time_ranges['0.5-1.0s'] += 1
            elif exec_time < 2.0:
                time_ranges['1.0-2.0s'] += 1
            elif exec_time < 5.0:
                time_ranges['2.0-5.0s'] += 1
            else:
                time_ranges['5.0s+'] += 1

        return {
            'time_distribution': time_ranges,
            'average_execution_time': total_time / len(self.slow_queries),
            'total_slow_queries': len(self.slow_queries),
            'most_common_recommendations': self._get_common_recommendations()
        }

    def _get_common_recommendations(self) -> List[str]:
        """Get most common optimization recommendations."""
        all_recommendations = []
        for query in self.slow_queries:
            if query.get('analysis') and query['analysis'].get('recommendations'):
                all_recommendations.extend(query['analysis']['recommendations'])

        # Count and return top recommendations
        recommendation_counts = Counter(all_recommendations)
        return [rec for rec, count in recommendation_counts.most_common(5)]


# Global database performance monitor
db_performance_monitor: Optional[DatabasePerformanceMonitor] = None