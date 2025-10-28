"""
CLI Interface for Local-First Router
Simple command-line interface for testing and using the router
"""
import sys
import argparse
from typing import Optional

from .router import LocalFirstRouter
from .config import SESSION_CONFIG


def format_local_success(result: dict):
    """Format local success result for CLI"""

    print("\n" + "=" * 60)
    print("🎯 LOCAL FIRST SUCCESS")
    print("=" * 60)
    print(f"✅ Model: {result['model']}")
    print(f"📊 Quality: {result['quality']:.1f}/10 (Target: 9.0/10)")
    print(f"💰 Cost: FREE")
    print(f"⏱️  Time: {result['response_time']:.2f}s")
    print(f"🔒 Privacy: 100% Local")
    print(f"\nSession: {result['session']['session_id']}")
    print(f"Tasks in session: {result['session']['task_count']}")
    print("=" * 60)
    print(f"\n{result['message']}\n")
    print("RESPONSE:")
    print("-" * 60)
    print(result['response'])
    print("-" * 60)


def format_upgrade_decision(result: dict):
    """Format upgrade decision for CLI"""

    local = result['local_result']
    session_analysis = result.get('session_analysis', {})

    print("\n" + "=" * 60)
    print("🏠 LOCAL FIRST APPROACH")
    print("=" * 60)
    print(f"✅ Best Local Model: {local['model']}")
    print(f"📊 Local Quality: {local['quality']:.1f}/10 (Target: 9.0/10)")
    print(f"💰 Local Cost: FREE")
    print(f"⏱️  Local Time: {local['response_time']:.2f}s")
    print(f"🔒 Privacy: 100% Local")
    print("\n❌ Local models cannot achieve 9/10 quality for this task")
    print("\n💡 CLOUD UPGRADE OPTIONS:\n")

    for i, option in enumerate(result['upgrade_options'], 1):
        print(f"{i}. {option['model'].replace('/', ' / ').replace('-', ' ').title()}")
        print(f"   📊 Quality: {option['quality']:.1f}/10 (+{option['quality_gain']:+.1f})")
        print(f"   💰 Cost: ${option['estimated_cost']:.6f} (${option['cost_per_point']:.6f} per quality point)")
        print()

    # Show session analysis if upgrading from local
    if session_analysis.get('status') == 'considering_upgrade':
        print("\n🚨 SESSION-AWARE COST ANALYSIS")
        print("-" * 60)
        print(f"💭 Single Task Cost: ${session_analysis['single_task_cost']:.6f}")
        print(f"🔄 Context Transfer Cost: ${session_analysis['context_transfer_cost']:.6f}")
        print(f"📊 Projected Session Tasks: {session_analysis['projected_session_tasks']}")
        print(f"💰 TOTAL SESSION COST: ${session_analysis['total_session_cost']:.4f}")
        print(f"📈 Session Premium: {session_analysis['session_premium']:.1f}x more than single task")
        print()
        print("⚠️  REALITY CHECK:")
        print(f"   - This upgrade commits you to ~${session_analysis['total_session_cost']:.2f} for the session")
        print(f"   - Average session lasts {session_analysis['projected_session_tasks']} tasks")
        print(f"   - Each task in session costs ${session_analysis['cost_per_task_in_session']:.6f}")
        print()

    print("=" * 60)
    print("\nLOCAL RESPONSE:")
    print("-" * 60)
    print(local['response'])
    print("-" * 60)
    print(f"\nSession ID: {result['session']['session_id']}")
    print(f"Session Tier: {result['session']['tier']}")
    print(f"Tasks in session: {result['session']['task_count']}")


def format_cloud_success(result: dict):
    """Format cloud success result for CLI"""

    print("\n" + "=" * 60)
    print("☁️  CLOUD UPGRADE SUCCESSFUL")
    print("=" * 60)
    print(f"✅ Model: {result['model']}")
    print(f"📊 Quality: {result['quality']:.1f}/10")
    print(f"💰 Cost: ${result['cost']:.6f}")
    print(f"\nSession: {result['session']['session_id']}")
    print(f"Session Tier: {result['session']['tier']}")
    print(f"Session Cost So Far: ${result['session']['total_cost']:.6f}")
    print(f"Tasks in session: {result['session']['task_count']}")
    print("=" * 60)
    print("\nRESPONSE:")
    print("-" * 60)
    print(result['response'])
    print("-" * 60)


def interactive_mode(router: LocalFirstRouter):
    """Interactive CLI mode"""

    print("=" * 60)
    print("🤖 LOCAL-FIRST AI ROUTER - Interactive Mode")
    print("=" * 60)
    print("\nCommands:")
    print("  /new     - Start new session")
    print("  /status  - Show session status")
    print("  /quit    - Exit")
    print("\nEnter prompts to process them through the router.")
    print("You'll see local results first, with upgrade options if needed.")
    print("=" * 60 + "\n")

    current_session_id = None

    while True:
        try:
            prompt = input("\n💭 Prompt: ").strip()

            if not prompt:
                continue

            if prompt == "/quit":
                if current_session_id:
                    router.end_session(current_session_id)
                print("\n👋 Goodbye!\n")
                break

            if prompt == "/new":
                if current_session_id:
                    router.end_session(current_session_id)
                current_session_id = None
                print("\n✅ New session will start with next prompt\n")
                continue

            if prompt == "/status":
                if current_session_id:
                    status = router.get_session_status(current_session_id)
                    if status:
                        print(f"\n📊 Session Status:")
                        print(f"   ID: {status['session_id']}")
                        print(f"   Tier: {status['tier']}")
                        print(f"   Tasks: {status['task_count']}")
                        print(f"   Total Cost: ${status['total_cost']:.6f}")
                else:
                    print("\n⚠️  No active session")
                continue

            # Process prompt
            result = router.process_prompt(prompt, session_id=current_session_id)

            # Update session ID
            if 'session' in result:
                current_session_id = result['session']['session_id']

            # Format output based on status
            if result['status'] == 'local_success':
                format_local_success(result)

            elif result['status'] == 'local_limited':
                format_upgrade_decision(result)

                # Ask if user wants to upgrade
                choice = input("\n🔄 Upgrade to cloud? [y/n]: ").strip().lower()

                if choice == 'y':
                    # Ask which model
                    print("\nSelect model (or press Enter for best option):")
                    for i, option in enumerate(result['upgrade_options'], 1):
                        print(f"  {i}. {option['model']}")

                    model_choice = input("\nChoice [1]: ").strip()

                    if model_choice and model_choice.isdigit():
                        model_idx = int(model_choice) - 1
                        if 0 <= model_idx < len(result['upgrade_options']):
                            model = result['upgrade_options'][model_idx]['model']
                        else:
                            model = None
                    else:
                        model = None

                    # Upgrade to cloud
                    cloud_result = router.upgrade_to_cloud(current_session_id, prompt, model)

                    if 'error' in cloud_result:
                        print(f"\n❌ Error: {cloud_result['error']}")
                    else:
                        format_cloud_success(cloud_result)

            elif result['status'] == 'cloud_success':
                format_cloud_success(result)

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")


def main():
    """Main CLI entry point"""

    parser = argparse.ArgumentParser(description="Local-First AI Router CLI")
    parser.add_argument('prompt', nargs='*', help='Prompt to process')
    parser.add_argument('--session', '-s', help='Session ID to continue')
    parser.add_argument('--auto-upgrade', '-a', action='store_true', help='Auto upgrade to cloud if needed')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')

    args = parser.parse_args()

    router = LocalFirstRouter()

    if args.interactive or not args.prompt:
        interactive_mode(router)
        return

    # Single prompt mode
    prompt = ' '.join(args.prompt)

    result = router.process_prompt(
        prompt=prompt,
        session_id=args.session,
        auto_upgrade=args.auto_upgrade
    )

    # Format output
    if result['status'] == 'local_success':
        format_local_success(result)
    elif result['status'] == 'local_limited':
        format_upgrade_decision(result)
        print("\n💡 Use --auto-upgrade to automatically use cloud models")
        print(f"💡 Use --session {result['session']['session_id']} to continue this session")
    elif result['status'] == 'cloud_success':
        format_cloud_success(result)


if __name__ == '__main__':
    main()
