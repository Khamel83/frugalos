"""
Context-Aware Automation
Intelligent automation rules that adapt based on context
"""

import logging
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from enum import Enum

from ..config import Config
from ..database import Database
from ..logger import get_logger

logger = get_logger('autonomous.context_automation')

class AutomationTrigger(Enum):
    """Automation trigger types"""
    TIME_BASED = "time_based"  # Trigger at specific time
    EVENT_BASED = "event_based"  # Trigger on event
    PATTERN_BASED = "pattern_based"  # Trigger on pattern match
    CONDITION_BASED = "condition_based"  # Trigger when condition met
    THRESHOLD_BASED = "threshold_based"  # Trigger when threshold crossed

@dataclass
class AutomationRule:
    """An automation rule"""
    rule_id: str
    name: str
    description: str
    trigger_type: AutomationTrigger
    trigger_config: Dict[str, Any]
    conditions: List[Dict[str, Any]]
    actions: List[Dict[str, Any]]
    enabled: bool
    priority: int
    created_at: datetime
    last_triggered: Optional[datetime]
    trigger_count: int
    success_count: int

class ContextAwareAutomation:
    """Context-aware automation system"""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.db = Database()
        self.logger = get_logger('context_automation')

        # Automation configuration
        self.enabled = self.config.get('autonomous.automation.enabled', True)
        self.max_concurrent = self.config.get('autonomous.automation.max_concurrent', 5)

        # Automation state
        self._rules = {}  # rule_id -> AutomationRule
        self._active_automations = {}  # rule_id -> job_id
        self._context_cache = {}  # Cached context information

        # Load automation rules
        self._load_automation_rules()

    def _load_automation_rules(self):
        """Load automation rules from database"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM automation_rules
                    WHERE enabled = 1
                    ORDER BY priority
                """)

                for row in cursor.fetchall():
                    rule = AutomationRule(
                        rule_id=str(row['id']),
                        name=row['name'],
                        description=row['description'],
                        trigger_type=AutomationTrigger[row['trigger_type']],
                        trigger_config=eval(row['trigger_config']) if row['trigger_config'] else {},
                        conditions=eval(row['conditions']) if row['conditions'] else [],
                        actions=eval(row['actions']) if row['actions'] else [],
                        enabled=bool(row['enabled']),
                        priority=row['priority'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        last_triggered=datetime.fromisoformat(row['last_triggered']) if row['last_triggered'] else None,
                        trigger_count=row['trigger_count'] or 0,
                        success_count=row['success_count'] or 0
                    )

                    self._rules[rule.rule_id] = rule

            self.logger.info(f"Loaded {len(self._rules)} automation rules")

        except Exception as e:
            self.logger.error(f"Error loading automation rules: {e}")

    def evaluate_triggers(self, context: Dict[str, Any] = None) -> List[AutomationRule]:
        """
        Evaluate all triggers and return rules that should fire

        Args:
            context: Current context

        Returns:
            List of rules to trigger
        """
        if not self.enabled:
            return []

        context = context or self._get_current_context()
        triggered_rules = []

        for rule in self._rules.values():
            if not rule.enabled:
                continue

            try:
                if self._should_trigger(rule, context):
                    triggered_rules.append(rule)

            except Exception as e:
                self.logger.error(f"Error evaluating rule {rule.rule_id}: {e}")

        return triggered_rules

    def _should_trigger(self, rule: AutomationRule, context: Dict[str, Any]) -> bool:
        """Check if rule should trigger"""
        # Check trigger
        if not self._check_trigger(rule, context):
            return False

        # Check conditions
        if not self._check_conditions(rule, context):
            return False

        # Check rate limiting
        if not self._check_rate_limit(rule):
            return False

        return True

    def _check_trigger(self, rule: AutomationRule, context: Dict[str, Any]) -> bool:
        """Check if trigger condition is met"""
        trigger_type = rule.trigger_type
        config = rule.trigger_config

        if trigger_type == AutomationTrigger.TIME_BASED:
            return self._check_time_trigger(config, context)

        elif trigger_type == AutomationTrigger.EVENT_BASED:
            return self._check_event_trigger(config, context)

        elif trigger_type == AutomationTrigger.PATTERN_BASED:
            return self._check_pattern_trigger(config, context)

        elif trigger_type == AutomationTrigger.CONDITION_BASED:
            return self._check_condition_trigger(config, context)

        elif trigger_type == AutomationTrigger.THRESHOLD_BASED:
            return self._check_threshold_trigger(config, context)

        return False

    def _check_time_trigger(self, config: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check time-based trigger"""
        trigger_time = config.get('time')  # Format: "HH:MM"
        trigger_days = config.get('days', ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])

        now = datetime.now()
        current_day = now.strftime('%A').lower()

        # Check day
        if current_day not in trigger_days:
            return False

        # Check time (within 1-minute window)
        if trigger_time:
            try:
                hour, minute = map(int, trigger_time.split(':'))
                trigger_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # Check if we're within 1 minute of trigger time
                time_diff = abs((now - trigger_dt).total_seconds())
                return time_diff < 60

            except Exception:
                return False

        return True

    def _check_event_trigger(self, config: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check event-based trigger"""
        event_type = config.get('event_type')
        event_data = context.get('event')

        if not event_data:
            return False

        # Check if event type matches
        if event_data.get('type') == event_type:
            # Additional event filters
            filters = config.get('filters', {})
            for key, value in filters.items():
                if event_data.get(key) != value:
                    return False

            return True

        return False

    def _check_pattern_trigger(self, config: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check pattern-based trigger"""
        pattern = config.get('pattern')
        text = context.get('text', '')

        if pattern:
            try:
                return bool(re.search(pattern, text, re.IGNORECASE))
            except Exception:
                return False

        return False

    def _check_condition_trigger(self, config: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check condition-based trigger"""
        condition = config.get('condition')

        if not condition:
            return False

        try:
            # Safe evaluation of condition
            # In production, this would use a safer expression evaluator
            return bool(eval(condition, {"__builtins__": {}}, context))

        except Exception:
            return False

    def _check_threshold_trigger(self, config: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Check threshold-based trigger"""
        metric = config.get('metric')
        operator = config.get('operator', '>')
        threshold = config.get('threshold')

        metric_value = context.get(metric)

        if metric_value is None or threshold is None:
            return False

        try:
            if operator == '>':
                return metric_value > threshold
            elif operator == '>=':
                return metric_value >= threshold
            elif operator == '<':
                return metric_value < threshold
            elif operator == '<=':
                return metric_value <= threshold
            elif operator == '==':
                return metric_value == threshold
            elif operator == '!=':
                return metric_value != threshold

        except Exception:
            return False

        return False

    def _check_conditions(self, rule: AutomationRule, context: Dict[str, Any]) -> bool:
        """Check all conditions for a rule"""
        for condition in rule.conditions:
            if not self._evaluate_condition(condition, context):
                return False

        return True

    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a single condition"""
        condition_type = condition.get('type')

        if condition_type == 'time_range':
            # Check if current time is within range
            start_time = condition.get('start')
            end_time = condition.get('end')
            now = datetime.now().time()

            try:
                start = dt_time.fromisoformat(start_time)
                end = dt_time.fromisoformat(end_time)
                return start <= now <= end
            except Exception:
                return False

        elif condition_type == 'context_value':
            # Check context value
            key = condition.get('key')
            operator = condition.get('operator', '==')
            value = condition.get('value')

            context_value = context.get(key)
            if context_value is None:
                return False

            try:
                if operator == '==':
                    return context_value == value
                elif operator == '!=':
                    return context_value != value
                elif operator == '>':
                    return context_value > value
                elif operator == '<':
                    return context_value < value
                elif operator == 'in':
                    return context_value in value
                elif operator == 'contains':
                    return value in context_value

            except Exception:
                return False

        elif condition_type == 'not_recently_triggered':
            # Check if rule hasn't been triggered recently
            min_interval = condition.get('min_interval_minutes', 60)

            if rule.last_triggered:
                minutes_since = (datetime.now() - rule.last_triggered).total_seconds() / 60
                return minutes_since >= min_interval

            return True

        return True

    def _check_rate_limit(self, rule: AutomationRule) -> bool:
        """Check if rule is within rate limits"""
        # Check concurrent executions
        if len(self._active_automations) >= self.max_concurrent:
            return False

        # Check if already running
        if rule.rule_id in self._active_automations:
            return False

        return True

    def execute_rule(self, rule: AutomationRule, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute an automation rule

        Args:
            rule: Rule to execute
            context: Execution context

        Returns:
            Execution result
        """
        context = context or {}

        try:
            self.logger.info(f"Executing automation rule: {rule.name}")

            # Mark as active
            self._active_automations[rule.rule_id] = datetime.now()

            # Execute actions
            results = []
            for action in rule.actions:
                result = self._execute_action(action, context)
                results.append(result)

            # Update rule statistics
            rule.last_triggered = datetime.now()
            rule.trigger_count += 1
            rule.success_count += 1

            # Persist updates
            self._update_rule_stats(rule)

            # Remove from active
            del self._active_automations[rule.rule_id]

            self.logger.info(f"Automation rule {rule.name} executed successfully")

            return {
                'success': True,
                'rule_id': rule.rule_id,
                'results': results
            }

        except Exception as e:
            self.logger.error(f"Error executing rule {rule.name}: {e}")

            # Remove from active
            if rule.rule_id in self._active_automations:
                del self._active_automations[rule.rule_id]

            return {
                'success': False,
                'rule_id': rule.rule_id,
                'error': str(e)
            }

    def _execute_action(self, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single action"""
        action_type = action.get('type')

        if action_type == 'run_job':
            # Run a job
            idea = action.get('idea', '')

            # Substitute context variables
            for key, value in context.items():
                idea = idea.replace(f'{{{key}}}', str(value))

            from ..queue import JobQueue
            queue = JobQueue(self.config)
            job_id = self.db.create_job(idea)
            queue.enqueue_job(job_id, idea)

            return {'action': 'job_created', 'job_id': job_id}

        elif action_type == 'send_notification':
            # Send notification
            message = action.get('message', '')

            # Substitute context variables
            for key, value in context.items():
                message = message.replace(f'{{{key}}}', str(value))

            from ..notifications import get_notification_manager
            notif_manager = get_notification_manager(self.config)
            notif_manager.send_notification('Automation', message)

            return {'action': 'notification_sent'}

        elif action_type == 'log_event':
            # Log event
            self.logger.info(f"Automation event: {action.get('message', 'No message')}")
            return {'action': 'event_logged'}

        else:
            self.logger.warning(f"Unknown action type: {action_type}")
            return {'action': 'unknown', 'type': action_type}

    def _update_rule_stats(self, rule: AutomationRule):
        """Update rule statistics in database"""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE automation_rules
                    SET last_triggered = ?,
                        trigger_count = ?,
                        success_count = ?
                    WHERE id = ?
                """, (
                    rule.last_triggered.isoformat(),
                    rule.trigger_count,
                    rule.success_count,
                    rule.rule_id
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error updating rule stats: {e}")

    def _get_current_context(self) -> Dict[str, Any]:
        """Get current system context"""
        now = datetime.now()

        context = {
            'timestamp': now.isoformat(),
            'hour': now.hour,
            'minute': now.minute,
            'day_of_week': now.strftime('%A').lower(),
            'date': now.date().isoformat()
        }

        # Add system metrics
        try:
            with self.db.get_connection() as conn:
                # Job statistics
                cursor = conn.execute("""
                    SELECT
                        COUNT(*) as total_jobs,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_jobs,
                        AVG(execution_time_ms) as avg_time
                    FROM jobs
                    WHERE created_at >= datetime('now', '-1 hour')
                """)
                row = cursor.fetchone()

                if row:
                    context['jobs_last_hour'] = row['total_jobs']
                    context['jobs_completed_last_hour'] = row['completed_jobs']
                    context['avg_execution_time_ms'] = row['avg_time'] or 0

        except Exception as e:
            self.logger.error(f"Error getting context: {e}")

        return context

    def create_rule(
        self,
        name: str,
        description: str,
        trigger_type: AutomationTrigger,
        trigger_config: Dict[str, Any],
        actions: List[Dict[str, Any]],
        conditions: List[Dict[str, Any]] = None,
        priority: int = 5
    ) -> str:
        """
        Create a new automation rule

        Args:
            name: Rule name
            description: Rule description
            trigger_type: Type of trigger
            trigger_config: Trigger configuration
            actions: List of actions to execute
            conditions: Optional conditions
            priority: Rule priority (1-10, lower = higher priority)

        Returns:
            Rule ID
        """
        rule_id = f"rule_{int(datetime.now().timestamp())}_{hash(name) % 10000}"

        rule = AutomationRule(
            rule_id=rule_id,
            name=name,
            description=description,
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            conditions=conditions or [],
            actions=actions,
            enabled=True,
            priority=priority,
            created_at=datetime.now(),
            last_triggered=None,
            trigger_count=0,
            success_count=0
        )

        # Store in database
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO automation_rules (
                        id, name, description, trigger_type, trigger_config,
                        conditions, actions, enabled, priority, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rule_id,
                    name,
                    description,
                    trigger_type.name,
                    str(trigger_config),
                    str(conditions or []),
                    str(actions),
                    1,
                    priority,
                    datetime.now().isoformat()
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error creating rule: {e}")

        # Add to active rules
        self._rules[rule_id] = rule

        self.logger.info(f"Created automation rule: {name} ({rule_id})")

        return rule_id

    def get_automation_stats(self) -> Dict[str, Any]:
        """Get automation statistics"""
        return {
            'enabled': self.enabled,
            'total_rules': len(self._rules),
            'active_automations': len(self._active_automations),
            'rules_by_trigger': {
                trigger.value: len([
                    r for r in self._rules.values()
                    if r.trigger_type == trigger
                ])
                for trigger in AutomationTrigger
            },
            'total_triggers': sum(r.trigger_count for r in self._rules.values()),
            'total_successes': sum(r.success_count for r in self._rules.values())
        }
