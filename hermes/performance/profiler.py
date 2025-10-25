"""
Advanced Performance Profiler
Real-time performance profiling with automatic analysis
"""

import logging
import time
import threading
import cProfile
import pstats
import io
from typing import Dict, Any, List, Optional, Callable, ContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
import json

from ..config import Config
from ..logger import get_logger

logger = get_logger('performance.profiler')

class ProfileType(Enum):
    """Types of profiling"""
    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    FUNCTION = "function"

@dataclass
class ProfileStats:
    """Profile statistics"""
    profile_id: str
    name: str
    profile_type: ProfileType
    start_time: datetime
    end_time: datetime
    duration_ms: float
    peak_memory_mb: float
    function_calls: int
    top_functions: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class Profiler:
    """Advanced performance profiler"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.logger = get_logger('profiler')

        # Profile storage
        self._profiles = {}  # profile_id -> ProfileStats
        self._active_profiles = {}  # thread_id -> profile_id
        self._profile_lock = threading.Lock()

        # Configuration
        self.enabled = self.config.get('performance.profiling.enabled', True)
        self.max_profiles = self.config.get('performance.profiling.max_profiles', 1000)
        self.auto_profile_functions = self.config.get('performance.profiling.auto_profile', True)
        self.profile_threshold_ms = self.config.get('performance.profiling.threshold_ms', 100)

        # Global profiler instance
        self._current_profiler = None

    def profile(self, name: str, profile_type: ProfileType = ProfileType.CPU) -> ContextManager:
        """
        Context manager for profiling code blocks

        Args:
            name: Profile name
            profile_type: Type of profiling

        Returns:
            Context manager
        """
        return ProfileContext(self, name, profile_type)

    def profile_function(self, name: Optional[str] = None, threshold_ms: Optional[float] = None):
        """
        Decorator for profiling functions

        Args:
            name: Profile name (defaults to function name)
            threshold_ms: Minimum duration to profile

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            profile_name = name or f"{func.__module__}.{func.__qualname__}"

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                start_time = time.time()

                # Create profile
                profile_id = self._generate_profile_id()

                # Start profiling
                if profile_type := ProfileType.CPU:  # Default to CPU profiling
                    profiler = cProfile.Profile()
                    profiler.enable()

                try:
                    # Execute function
                    result = func(*args, **kwargs)
                    return result

                finally:
                    end_time = time.time()
                    duration_ms = (end_time - start_time) * 1000

                    # Check threshold
                    min_duration = threshold_ms or self.profile_threshold_ms
                    if duration_ms >= min_duration:
                        # Stop profiling
                        if profile_type == ProfileType.CPU:
                            profiler.disable()

                            # Process profile data
                            self._process_cpu_profile(
                                profile_id,
                                profile_name,
                                start_time,
                                end_time,
                                profiler
                            )

                    else:
                        self.logger.debug(
                            f"Function {profile_name} duration {duration_ms:.2f}ms "
                            f"below threshold {min_duration}ms - skipping profile"
                        )

            return wrapper
        return decorator

    def start_profile(self, name: str, profile_type: ProfileType = ProfileType.CPU) -> str:
        """
        Start manual profiling

        Args:
            name: Profile name
            profile_type: Type of profiling

        Returns:
            Profile ID
        """
        if not self.enabled:
            return ""

        profile_id = self._generate_profile_id()
        thread_id = threading.get_ident()

        # Store active profile
        with self._profile_lock:
            self._active_profiles[thread_id] = profile_id

        # Create profile entry
        profile_stats = ProfileStats(
            profile_id=profile_id,
            name=name,
            profile_type=profile_type,
            start_time=datetime.now(),
            end_time=datetime.now(),  # Will be updated on stop
            duration_ms=0.0,
            peak_memory_mb=0.0,
            function_calls=0,
            top_functions=[],
            metadata={}
        )

        with self._profile_lock:
            self._profiles[profile_id] = profile_stats

        # Start actual profiling
        if profile_type == ProfileType.CPU:
            self._current_profiler = cProfile.Profile()
            self._current_profiler.enable()

        self.logger.debug(f"Started profile {profile_id}: {name}")

        return profile_id

    def stop_profile(self, profile_id: str) -> Optional[ProfileStats]:
        """
        Stop manual profiling

        Args:
            profile_id: Profile ID to stop

        Returns:
            Profile stats if found
        """
        if not self.enabled or not profile_id:
            return None

        thread_id = threading.get_ident()

        with self._profile_lock:
            # Remove from active profiles
            if thread_id in self._active_profiles:
                del self._active_profiles[thread_id]

            # Get profile stats
            profile_stats = self._profiles.get(profile_id)

        if not profile_stats:
            self.logger.warning(f"Profile {profile_id} not found")
            return None

        # Update end time
        profile_stats.end_time = datetime.now()
        profile_stats.duration_ms = (
            (profile_stats.end_time - profile_stats.start_time).total_seconds() * 1000
        )

        # Stop actual profiling
        if self._current_profiler and profile_stats.profile_type == ProfileType.CPU:
            self._current_profiler.disable()

            # Process profile data
            self._process_cpu_profile(
                profile_id,
                profile_stats.name,
                profile_stats.start_time,
                profile_stats.end_time,
                self._current_profiler,
                profile_stats
            )

            self._current_profiler = None

        self.logger.debug(f"Stopped profile {profile_id}: {profile_stats.name}")

        return profile_stats

    def _process_cpu_profile(
        self,
        profile_id: str,
        name: str,
        start_time: datetime,
        end_time: datetime,
        profiler: cProfile.Profile,
        profile_stats: Optional[ProfileStats] = None
    ):
        """Process CPU profiling data"""
        try:
            # Create stats object
            stats_stream = io.StringIO()
            ps = pstats.Stats(profiler, stream=stats_stream)

            # Sort stats by cumulative time
            ps.sort_stats('cumulative')
            ps.print_stats(20)  # Top 20 functions

            # Parse stats
            stats_text = stats_stream.getvalue()
            top_functions = self._parse_profile_output(stats_text)

            # Calculate total function calls
            total_calls = sum(func.get('calls', 0) for func in top_functions)

            # Update or create profile stats
            if profile_stats is None:
                profile_stats = ProfileStats(
                    profile_id=profile_id,
                    name=name,
                    profile_type=ProfileType.CPU,
                    start_time=start_time,
                    end_time=end_time,
                    duration_ms=(end_time - start_time).total_seconds() * 1000,
                    peak_memory_mb=0.0,
                    function_calls=total_calls,
                    top_functions=top_functions,
                    metadata={}
                )
            else:
                profile_stats.function_calls = total_calls
                profile_stats.top_functions = top_functions

            # Store profile
            with self._profile_lock:
                self._profiles[profile_id] = profile_stats

                # Limit number of profiles
                if len(self._profiles) > self.max_profiles:
                    self._cleanup_old_profiles()

        except Exception as e:
            self.logger.error(f"Error processing CPU profile: {e}")

    def _parse_profile_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse pstats output into structured data"""
        functions = []
        lines = output.split('\n')

        for line in lines[5:]:  # Skip header lines
            if line.strip() and not line.startswith('ncalls'):
                parts = line.split()
                if len(parts) >= 6:
                    try:
                        ncalls = parts[0]
                        cumtime = float(parts[3])
                        percall = float(parts[4])
                        func_name = ' '.join(parts[6:])

                        functions.append({
                            'function': func_name,
                            'calls': int(ncalls) if '/' not in ncalls else int(ncalls.split('/')[1]),
                            'cumulative_time': cumtime,
                            'per_call': percall,
                            'filename': func_name.split(':')[0] if ':' in func_name else 'unknown'
                        })
                    except (ValueError, IndexError):
                        continue

        return functions[:10]  # Return top 10

    def get_profile(self, profile_id: str) -> Optional[ProfileStats]:
        """Get profile by ID"""
        with self._profile_lock:
            return self._profiles.get(profile_id)

    def get_profiles(
        self,
        profile_type: Optional[ProfileType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ProfileStats]:
        """
        Get profiles with filtering

        Args:
            profile_type: Filter by type
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of profiles

        Returns:
            List of profiles
        """
        with self._profile_lock:
            profiles = list(self._profiles.values())

        # Apply filters
        if profile_type:
            profiles = [p for p in profiles if p.profile_type == profile_type]

        if start_time:
            profiles = [p for p in profiles if p.start_time >= start_time]

        if end_time:
            profiles = [p for p in profiles if p.end_time <= end_time]

        # Sort by duration (descending) and limit
        profiles.sort(key=lambda p: p.duration_ms, reverse=True)

        return profiles[:limit]

    def get_top_functions(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get top functions across all profiles

        Args:
            hours: Time window in hours

        Returns:
            List of top functions
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)

        with self._profile_lock:
            recent_profiles = [
                p for p in self._profiles.values()
                if p.start_time >= cutoff_time
            ]

        # Aggregate function data
        function_stats = {}

        for profile in recent_profiles:
            for func in profile.top_functions:
                func_name = func['function']

                if func_name not in function_stats:
                    function_stats[func_name] = {
                        'function': func_name,
                        'filename': func['filename'],
                        'total_calls': 0,
                        'total_time': 0.0,
                        'profile_count': 0
                    }

                function_stats[func_name]['total_calls'] += func['calls']
                function_stats[func_name]['total_time'] += func['cumulative_time']
                function_stats[func_name]['profile_count'] += 1

        # Calculate averages and sort
        for func_stats in function_stats.values():
            func_stats['avg_calls'] = (
                func_stats['total_calls'] / func_stats['profile_count']
                if func_stats['profile_count'] > 0 else 0
            )
            func_stats['avg_time'] = (
                func_stats['total_time'] / func_stats['profile_count']
                if func_stats['profile_count'] > 0 else 0
            )

        # Sort by total time
        top_functions = sorted(
            function_stats.values(),
            key=lambda f: f['total_time'],
            reverse=True
        )

        return top_functions[:20]

    def _cleanup_old_profiles(self):
        """Remove oldest profiles to stay within limits"""
        profiles = list(self._profiles.items())
        profiles.sort(key=lambda x: x[1].start_time)

        # Remove oldest profiles
        to_remove = len(profiles) - self.max_profiles
        for i in range(to_remove):
            profile_id = profiles[i][0]
            del self._profiles[profile_id]

    def _generate_profile_id(self) -> str:
        """Generate unique profile ID"""
        return f"profile_{int(time.time() * 1000)}_{hash(threading.get_ident()) % 10000}"

    def get_stats(self) -> Dict[str, Any]:
        """Get profiler statistics"""
        with self._profile_lock:
            profiles = list(self._profiles.values())

        if not profiles:
            return {
                'total_profiles': 0,
                'avg_duration_ms': 0,
                'max_duration_ms': 0,
                'profiles_by_type': {}
            }

        durations = [p.duration_ms for p in profiles]

        # Count by type
        profiles_by_type = {}
        for profile in profiles:
            ptype = profile.profile_type.value
            profiles_by_type[ptype] = profiles_by_type.get(ptype, 0) + 1

        return {
            'total_profiles': len(profiles),
            'avg_duration_ms': sum(durations) / len(durations),
            'max_duration_ms': max(durations),
            'min_duration_ms': min(durations),
            'profiles_by_type': profiles_by_type,
            'active_profiles': len(self._active_profiles)
        }

    def clear_profiles(self):
        """Clear all profiles"""
        with self._profile_lock:
            self._profiles.clear()
            self._active_profiles.clear()

        self.logger.info("All profiles cleared")


class ProfileContext:
    """Context manager for profiling"""

    def __init__(self, profiler: Profiler, name: str, profile_type: ProfileType):
        self.profiler = profiler
        self.name = name
        self.profile_type = profile_type
        self.profile_id = None

    def __enter__(self):
        self.profile_id = self.profiler.start_profile(self.name, self.profile_type)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.profile_id:
            return self.profiler.stop_profile(self.profile_id)
        return None


# Global profiler instance
_profiler_instance = None
_profiler_lock = threading.Lock()

def get_profiler(config: Optional[Config] = None) -> Profiler:
    """Get global profiler instance"""
    global _profiler_instance

    if _profiler_instance is None:
        with _profiler_lock:
            if _profiler_instance is None:
                _profiler_instance = Profiler(config)

    return _profiler_instance

# Decorator for easy function profiling
def profile(name: Optional[str] = None, threshold_ms: Optional[float] = None):
    """Decorator for profiling functions"""
    profiler = get_profiler()
    return profiler.profile_function(name, threshold_ms)