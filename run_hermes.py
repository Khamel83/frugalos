#!/usr/bin/env python3
"""
Hermes Application Launcher
Convenient script to start the Hermes application
"""

import os
import sys
import argparse
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from hermes.app import app
from hermes.config import Config
from hermes.logger import configure_logging

def main():
    parser = argparse.ArgumentParser(description="Start Hermes AI Assistant")
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=5000, help='Port to bind to')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--init-db', action='store_true', help='Initialize database and exit')

    args = parser.parse_args()

    # Load configuration
    config = Config(args.config)

    # Override config with command line arguments
    if args.debug:
        config.set('hermes.debug', True)
    config.set('hermes.host', args.host)
    config.set('hermes.port', args.port)

    # Configure logging
    configure_logging({
        'level': args.log_level,
        'console_output': True,
        'log_dir': config.get('hermes.log_dir', 'logs')
    })

    from hermes.logger import get_logger
    logger = get_logger('launcher')

    # Initialize database if requested
    if args.init_db:
        logger.info("Initializing database...")
        from hermes.database import Database
        db = Database(config)
        db.initialize()
        logger.info("Database initialized successfully")
        return

    # Create log directory
    log_dir = Path(config.get('hermes.log_dir', 'logs'))
    log_dir.mkdir(exist_ok=True)

    # Start job queue
    from hermes.queue import JobQueue
    queue = JobQueue(config)
    queue.start()
    logger.info("Job queue started")

    # Start metrics collection
    metrics_collector.start_collection()
    logger.info("Metrics collection started")

    try:
        logger.info(f"Starting Hermes on {args.host}:{args.port}")
        app.run(
            host=args.host,
            port=args.port,
            debug=config.get('hermes.debug', False),
            use_reloader=False  # Prevent duplicate workers
        )
    except KeyboardInterrupt:
        logger.info("Shutting down Hermes...")
    finally:
        queue.stop()
        metrics_collector.stop_collection()
        logger.info("Hermes stopped")

if __name__ == '__main__':
    main()