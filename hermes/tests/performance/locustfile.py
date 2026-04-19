"""
Locust performance testing file for Hermes AI Assistant

This file defines load testing scenarios for the Hermes API endpoints.
Run with: locust -f tests/performance/locustfile.py --host=http://localhost:8080
"""

import json
import random
import time
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask

# Global variables for tracking
test_data = {
    "conversations": [],
    "active_tasks": []
}

class HermesUser(HttpUser):
    """
    Simulates a typical user interacting with the Hermes AI Assistant
    """

    wait_time = between(2, 8)  # Wait 2-8 seconds between tasks

    def on_start(self):
        """Called when a user starts"""
        print(f"User {self.environment.parsed_options.host if hasattr(self.environment, 'parsed_options') else 'localhost'} started")
        self.create_conversation()

    def create_conversation(self):
        """Create a new conversation"""
        try:
            response = self.client.post("/api/orchestrator/conversation",
                                       json={
                                           "context": {
                                               "user_id": f"user_{random.randint(1000, 9999)}",
                                               "session_type": random.choice(["general", "technical", "creative", "analytical"]),
                                               "domain": random.choice(["software_development", "business", "analytics", "research"]),
                                               "preferences": {
                                                   "response_style": random.choice(["concise", "detailed"]),
                                                   "language": "en"
                                               }
                                           }
                                       },
                                       catch_response=True,
                                       name="Create Conversation")

            if response.status_code == 201:
                data = response.json()
                self.conversation_id = data["data"]["conversation_id"]
                test_data["conversations"].append(self.conversation_id)
                print(f"Created conversation: {self.conversation_id}")
            else:
                response.failure(f"Failed to create conversation: {response.status_code}")
                raise RescheduleTask()

        except Exception as e:
            print(f"Error creating conversation: {e}")
            raise RescheduleTask()

    @task(3)
    def execute_simple_task(self):
        """Execute a simple analysis task"""
        if not hasattr(self, 'conversation_id'):
            self.create_conversation()

        simple_tasks = [
            "Analyze user behavior patterns",
            "Generate performance metrics report",
            "Summarize recent system changes",
            "Check system health status",
            "Review cost optimization opportunities",
            "Generate weekly analytics summary"
        ]

        task_data = {
            "conversation_id": self.conversation_id,
            "idea": random.choice(simple_tasks),
            "context": {
                "domain": random.choice(["analytics", "monitoring", "business"]),
                "priority": random.choice(["low", "normal", "high"]),
                "constraints": {
                    "max_execution_time": random.choice([120, 180, 300]),
                    "budget_cents": random.choice([10, 25, 50])
                }
            }
        }

        with self.client.post("/api/orchestrator/execute",
                            json=task_data,
                            catch_response=True,
                            name="Execute Simple Task") as response:

            if response.status_code == 200:
                data = response.json()
                task_id = data["data"].get("task_id")
                if task_id:
                    test_data["active_tasks"].append(task_id)
                response.success()
            else:
                response.failure(f"Task execution failed: {response.status_code}")

    @task(2)
    def execute_complex_task(self):
        """Execute a complex task with more requirements"""
        if not hasattr(self, 'conversation_id'):
            self.create_conversation()

        complex_tasks = [
            "Optimize database queries for better performance",
            "Design scalable microservices architecture",
            "Implement machine learning pipeline",
            "Create comprehensive security audit report",
            "Develop automated testing framework",
            "Build real-time analytics dashboard"
        ]

        task_data = {
            "conversation_id": self.conversation_id,
            "idea": random.choice(complex_tasks),
            "context": {
                "domain": random.choice(["software_development", "architecture", "security", "devops"]),
                "priority": random.choice(["normal", "high", "urgent"]),
                "constraints": {
                    "max_execution_time": random.choice([300, 600, 900]),
                    "budget_cents": random.choice([50, 100, 200]),
                    "backends": random.choice([["openai_gpt4"], ["anthropic_claude"], ["openai_gpt4", "anthropic_claude"]])
                },
                "requirements": {
                    "include_code_examples": True,
                    "detailed_explanation": True,
                    "references": random.choice([["official_docs"], ["best_practices"], ["official_docs", "best_practices"]])
                }
            }
        }

        with self.client.post("/api/orchestrator/execute",
                            json=task_data,
                            catch_response=True,
                            name="Execute Complex Task") as response:

            if response.status_code == 200:
                data = response.json()
                task_id = data["data"].get("task_id")
                if task_id:
                    test_data["active_tasks"].append(task_id)
                response.success()
            else:
                response.failure(f"Complex task execution failed: {response.status_code}")

    @task(2)
    def generate_questions(self):
        """Generate questions for meta-learning"""
        if not hasattr(self, 'conversation_id'):
            self.create_conversation()

        ideas = [
            "Improve customer retention rates",
            "Enhance mobile app performance",
            "Reduce server response times",
            "Increase user engagement",
            "Optimize cloud infrastructure costs",
            "Implement better security measures"
        ]

        question_data = {
            "idea": random.choice(ideas),
            "max_questions": random.randint(3, 8),
            "conversation_id": self.conversation_id,
            "context": {
                "domain": random.choice(["business", "technology", "product"]),
                "current_metrics": {
                    "performance": random.randint(60, 95),
                    "satisfaction": random.randint(3.0, 4.8),
                    "retention": random.randint(70, 90)
                }
            },
            "question_types": random.sample(
                ["clarification", "requirement", "constraint", "assumption", "scope", "metrics"],
                random.randint(2, 4)
            )
        }

        with self.client.post("/api/metalearning/generate-questions",
                            json=question_data,
                            catch_response=True,
                            name="Generate Questions") as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Question generation failed: {response.status_code}")

    @task(2)
    def recognize_patterns(self):
        """Recognize patterns in conversation"""
        if not hasattr(self, 'conversation_id'):
            self.create_conversation()

        pattern_data = {
            "conversation_id": self.conversation_id,
            "context": {
                "current_session": {
                    "topic": random.choice(["performance", "security", "development", "analytics"]),
                    "duration_minutes": random.randint(5, 60),
                    "questions_asked": random.randint(3, 15)
                }
            },
            "include_historical": True
        }

        with self.client.post("/api/metalearning/recognize-patterns",
                            json=pattern_data,
                            catch_response=True,
                            name="Recognize Patterns") as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Pattern recognition failed: {response.status_code}")

    @task(2)
    def get_suggestions(self):
        """Get autonomous suggestions"""
        params = {
            "min_confidence": random.uniform(0.5, 0.9),
            "max_active": random.randint(5, 20)
        }

        # Occasionally filter by category
        if random.random() < 0.3:
            params["category"] = random.choice(["performance", "optimization", "security", "feature", "maintenance"])

        with self.client.get("/api/autonomous/suggestions",
                           params=params,
                           catch_response=True,
                           name="Get Suggestions") as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed to get suggestions: {response.status_code}")

    @task(1)
    def get_backend_health(self):
        """Check backend health status"""
        with self.client.get("/api/backends/health",
                           catch_response=True,
                           name="Get Backend Health") as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Backend health check failed: {response.status_code}")

    @task(1)
    def get_backend_performance(self):
        """Get backend performance metrics"""
        params = {
            "time_range": random.choice(["1h", "24h", "7d"])
        }

        with self.client.get("/api/backends/performance",
                           params=params,
                           catch_response=True,
                           name="Get Backend Performance") as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Performance metrics failed: {response.status_code}")

    @task(1)
    def get_cost_tracking(self):
        """Get cost tracking information"""
        params = {
            "period": random.choice(["daily", "weekly", "monthly"]),
            "include_optimization": random.choice([True, False])
        }

        with self.client.get("/api/backends/costs",
                           params=params,
                           catch_response=True,
                           name="Get Cost Tracking") as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Cost tracking failed: {response.status_code}")

    @task(1)
    def get_system_status(self):
        """Get system status"""
        params = {}
        if random.random() < 0.5:
            params["include_backends"] = True
        if random.random() < 0.5:
            params["include_metrics"] = True

        with self.client.get("/api/orchestrator/status",
                           params=params,
                           catch_response=True,
                           name="Get System Status") as response:

            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"System status check failed: {response.status_code}")


class PowerUser(HermesUser):
    """
    Simulates a power user who executes more tasks rapidly
    """

    wait_time = between(1, 4)  # Wait 1-4 seconds between tasks

    @task(5)
    def execute_rapid_tasks(self):
        """Execute tasks rapidly (power user behavior)"""
        self.execute_simple_task()


class AnalyticsUser(HttpUser):
    """
    Simulates a user focused on analytics and monitoring
    """

    wait_time = between(5, 15)

    def on_start(self):
        """Create conversation for analytics user"""
        response = self.client.post("/api/orchestrator/conversation",
                                   json={
                                       "context": {
                                           "user_id": f"analytics_user_{random.randint(1000, 9999)}",
                                           "session_type": "analytical",
                                           "domain": "analytics",
                                           "preferences": {
                                               "response_style": "detailed",
                                               "language": "en"
                                           }
                                       }
                                   },
                                   catch_response=True,
                                   name="Analytics User - Create Conversation")

        if response.status_code == 201:
            data = response.json()
            self.conversation_id = data["data"]["conversation_id"]
        else:
            raise RescheduleTask()

    @task(3)
    def get_performance_metrics(self):
        """Get performance metrics frequently"""
        self.get_backend_performance()

    @task(3)
    def get_costs(self):
        """Get cost tracking frequently"""
        self.get_cost_tracking()

    @task(2)
    def check_system_health(self):
        """Check system health frequently"""
        self.get_system_status()
        self.get_backend_health()

    @task(1)
    def execute_analytics_task(self):
        """Execute analytics-related task"""
        if not hasattr(self, 'conversation_id'):
            return

        analytics_tasks = [
            "Generate performance analysis report",
            "Analyze cost trends over time",
            "Create backend performance comparison",
            "Identify optimization opportunities",
            "Generate usage analytics summary"
        ]

        task_data = {
            "conversation_id": self.conversation_id,
            "idea": random.choice(analytics_tasks),
            "context": {
                "domain": "analytics",
                "priority": "normal",
                "constraints": {
                    "max_execution_time": 180,
                    "budget_cents": 25
                },
                "requirements": {
                    "detailed_explanation": True,
                    "references": ["metrics"]
                }
            }
        }

        self.client.post("/api/orchestrator/execute",
                        json=task_data,
                        catch_response=True,
                        name="Analytics Task Execution")


# Event handlers for statistics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, **kwargs):
    """Log request statistics"""
    if response.status_code >= 400:
        print(f"Failed request: {name} - Status: {response.status_code} - Response time: {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("Starting Hermes AI Assistant performance test")
    test_data["conversations"] = []
    test_data["active_tasks"] = []


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("Stopping Hermes AI Assistant performance test")
    print(f"Total conversations created: {len(test_data['conversations'])}")
    print(f"Total active tasks: {len(test_data['active_tasks'])}")

    # Print statistics
    stats = environment.stats

    print("\n=== Performance Test Summary ===")
    for endpoint in stats.entries:
        if endpoint.request_count > 0:
            print(f"Endpoint: {endpoint.name}")
            print(f"  Requests: {endpoint.request_count}")
            print(f"  Failures: {endpoint.failure_count}")
            print(f"  Average Response Time: {endpoint.avg_response_time:.2f}ms")
            print(f"  Min Response Time: {endpoint.min_response_time:.2f}ms")
            print(f"  Max Response Time: {endpoint.max_response_time:.2f}ms")
            print(f"  Median Response Time: {endpoint.median_response_time:.2f}ms")
            print(f"  95th Percentile: {endpoint.get_response_time_percentile(0.95):.2f}ms")
            print(f"  Requests/Second: {endpoint.current_rps:.2f}")
            print()