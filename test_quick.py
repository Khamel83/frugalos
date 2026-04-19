#!/usr/bin/env python3
"""Quick test to debug session tracking"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hermes.routing.router import LocalFirstRouter

router = LocalFirstRouter()

# First task
print("Task 1...")
result1 = router.process_prompt("Hello")
print(f"Session ID: {result1['session']['session_id']}")
print(f"Task count: {result1['session']['task_count']}")
print(f"Tier: {result1['session']['tier']}")

# Second task
print("\nTask 2...")
result2 = router.process_prompt("World", session_id=result1['session']['session_id'])
print(f"Session ID: {result2['session']['session_id']}")
print(f"Task count: {result2['session']['task_count']}")
print(f"Tier: {result2['session']['tier']}")

# Check database
print("\nChecking database...")
db_session = router.database.get_session(result1['session']['session_id'])
if db_session:
    print(f"DB: Found session {db_session['session_id']}")
    print(f"DB: Tier = {db_session['tier']}, Tasks = {db_session['task_count']}")

    tasks = router.database.get_session_tasks(result1['session']['session_id'])
    print(f"DB: {len(tasks)} tasks found")
else:
    print("DB: Session NOT found")
