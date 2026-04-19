#!/usr/bin/env python3
"""Debug session tracking"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hermes.routing.router import LocalFirstRouter
from hermes.routing.session import Session

# Direct session test
print("Direct Session Test:")
session = Session()
print(f"Initial task_count: {session.task_count}")

session.add_task("test", "response", "model", 0.0, 8.0)
print(f"After add_task: {session.task_count}")

session.add_task("test2", "response2", "model", 0.0, 8.0)
print(f"After 2nd add_task: {session.task_count}")

print("\n" + "="*60)
print("Router Test:")

router = LocalFirstRouter()

# Create session
session = router.session_manager.create_session()
print(f"Created session: {session.session_id}")
print(f"Initial task_count: {session.task_count}")

# Add tasks directly
session.add_task("test", "response", "model", 0.0, 8.0)
print(f"After direct add_task: {session.task_count}")

# Get it back
retrieved = router.session_manager.get_session(session.session_id)
print(f"Retrieved task_count: {retrieved.task_count if retrieved else 'NOT FOUND'}")
