#!/usr/bin/env python3
"""
Hermes: Backend-Agnostic Personal AI Assistant
Main Flask application
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response
from werkzeug.utils import secure_filename

# Add frugalos to path for CLI integration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hermes.database import Database
from hermes.config import Config
from hermes.logger import setup_logger
from hermes.tailscale import TailscaleClient
from hermes.monitoring import get_metrics_collector

# Initialize Flask app
app = Flask(__name__)
config = Config()

# Configure app
app.config['SECRET_KEY'] = os.getenv('HERMES_SECRET_KEY', 'dev-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Initialize components
db = Database()
logger = setup_logger('hermes.app')
tailscale_client = TailscaleClient()
metrics_collector = get_metrics_collector(config)

@app.route('/')
def index():
    """Main dashboard interface"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Advanced monitoring dashboard"""
    return render_template('dashboard.html')

@app.route('/api/status')
def status():
    """System status endpoint"""
    metrics = metrics_collector.get_current_metrics()
    return jsonify({
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'version': '0.1.0',
        'components': {
            'database': 'connected',
            'tailscale': 'connected' if tailscale_client.test_connection() else 'disconnected',
            'hermes': 'available',
            'monitoring': 'active' if metrics_collector._running else 'inactive'
        },
        'metrics': metrics
    })

@app.route('/api/submit', methods=['POST'])
def submit_idea():
    """Submit new idea for execution"""
    try:
        data = request.get_json()

        if not data or 'idea' not in data:
            return jsonify({'error': 'Missing idea field'}), 400

        idea = data['idea'].strip()
        if not idea:
            return jsonify({'error': 'Idea cannot be empty'}), 400

        # Create job record
        job_id = db.create_job(idea)

        # Queue job for processing
        from hermes.queue import JobQueue
        queue = JobQueue()
        queue.enqueue_job(job_id, idea)

        logger.info(f"Job {job_id} created for idea: {idea[:100]}...")

        return jsonify({
            'job_id': job_id,
            'status': 'queued',
            'message': 'Idea submitted for execution'
        })

    except Exception as e:
        logger.error(f"Error submitting idea: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/jobs')
def list_jobs():
    """List recent jobs"""
    try:
        limit = request.args.get('limit', 20, type=int)
        jobs = db.get_recent_jobs(limit)
        return jsonify({'jobs': jobs})
    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/jobs/<int:job_id>')
def get_job(job_id):
    """Get specific job details"""
    try:
        job = db.get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        return jsonify(job)
    except Exception as e:
        logger.error(f"Error getting job {job_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/jobs/<int:job_id>/events')
def job_events(job_id):
    """Server-sent events for job updates"""
    def generate():
        try:
            # Get existing events
            events = db.get_job_events(job_id)
            for event in events:
                yield f"data: {event}\n\n"

            # Stream new events
            from hermes.events import EventStreamer
            streamer = EventStreamer()
            for event in streamer.stream_job_events(job_id):
                yield f"data: {event}\n\n"

        except Exception as e:
            logger.error(f"Error streaming events for job {job_id}: {str(e)}")
            yield f"data: {{'type': 'error', 'message': 'Stream error'}}\n\n"

    return Response(generate(), mimetype='text/plain')

@app.route('/api/backends')
def list_backends():
    """List available AI backends"""
    try:
        backends = db.get_active_backends()
        return jsonify({'backends': backends})
    except Exception as e:
        logger.error(f"Error listing backends: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        db_status = 'healthy' if db.test_connection() else 'unhealthy'

        # Test tailscale connection
        tailscale_status = 'connected' if tailscale_client.test_connection() else 'disconnected'

        # Test local execution
        from .local_execution import LocalExecutionEngine
        local_engine = LocalExecutionEngine(config)
        local_status = 'available' if local_engine.test_local_execution() else 'unavailable'

        # Determine overall status
        overall_status = 'healthy' if db_status == 'healthy' else 'unhealthy'

        return jsonify({
            'status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'components': {
                'database': db_status,
                'tailscale': tailscale_status,
                'local_execution': local_status,
                'monitoring': 'active' if metrics_collector._running else 'inactive'
            }
        }), 200 if overall_status == 'healthy' else 503

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503

@app.route('/api/metrics')
def get_metrics():
    """Get current system metrics"""
    return jsonify(metrics_collector.get_current_metrics())

@app.route('/api/metrics/history')
def get_metrics_history():
    """Get metrics history"""
    hours = request.args.get('hours', 24, type=int)
    return jsonify(metrics_collector.get_metrics_history(hours))

@app.route('/api/alerts')
def get_alerts():
    """Get monitoring alerts"""
    hours = request.args.get('hours', 24, type=int)
    resolved = request.args.get('resolved', 'false').lower() == 'true'
    return jsonify({'alerts': metrics_collector.get_alerts(hours, resolved)})

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize database
    db.initialize()

    logger.info("Starting Hermes application on port 5000")
    app.run(host='0.0.0.0', port=5000, debug=config.get('hermes.debug', False))