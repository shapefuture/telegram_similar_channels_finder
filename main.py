"""
Telegram Similar Channels Crawler Web Interface
A web application to interact with the Telegram Similar Channels Crawler.
"""

import os
import json
import asyncio
import logging
import csv
import io
import secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("TelegramCrawlerApp")

# Import the crawler module
import telegram_crawler

# File-based storage that persists across worker reloads
class TempStorage:
    """Class for storing data in files instead of relying on session or memory."""
    _channels_file = 'temp_channels.json'
    _results_file = 'temp_results.json'
    
    @classmethod
    def _ensure_dirs(cls):
        """Ensure directories exist."""
        os.makedirs('data', exist_ok=True)
    
    @classmethod
    def set_channels(cls, value):
        """Set the channels value."""
        cls._ensure_dirs()
        try:
            with open(cls._channels_file, 'w') as f:
                json.dump(value, f)
        except Exception as e:
            logger.error(f"Error saving channels to file: {e}")
    
    @classmethod
    def set_results(cls, value):
        """Set the results value."""
        cls._ensure_dirs()
        try:
            with open(cls._results_file, 'w') as f:
                json.dump(value, f)
        except Exception as e:
            logger.error(f"Error saving results to file: {e}")
    
    @classmethod
    def channels(cls):
        """Get the channels value."""
        try:
            if os.path.exists(cls._channels_file):
                with open(cls._channels_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading channels from file: {e}")
        return []
    
    @classmethod
    def results(cls):
        """Get the results value."""
        try:
            if os.path.exists(cls._results_file):
                with open(cls._results_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading results from file: {e}")
        return {}

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", secrets.token_hex(16))

@app.route('/', methods=['GET', 'POST'])
def index():
    """Single-page application for Telegram Similar Channels Crawler."""
    # Handle POST requests for different input types
    if request.method == 'POST':
        input_type = request.form.get('input_type', '')
        
        # Configuration form submission
        if input_type == 'config':
            return handle_config_form()
            
        # Manual input form submission
        elif input_type == 'manual':
            return handle_manual_input()
            
        # File upload form submission
        elif input_type == 'file':
            return handle_file_upload()
            
        # Start crawler form submission
        elif input_type == 'start_crawler':
            return handle_start_crawler()
    
    # Prepare context for the template
    results = TempStorage.results()
    logger.info(f"Before render - Results exists: {bool(results)}")
    logger.info(f"Results type: {type(results)}")
    logger.info(f"Results value: {results}")
    if results:
        logger.info(f"Results keys: {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}")
        logger.info(f"Similar channels in results: {bool(isinstance(results, dict) and 'similar_channels' in results)}")
        if isinstance(results, dict) and 'similar_channels' in results:
            logger.info(f"Similar channels count: {len(results['similar_channels'])}")
            logger.info(f"Channel names: {list(results['similar_channels'].keys())}")
    
    context = {
        'channels': TempStorage.channels(),
        'results': results,
        'telegram_api_id': os.getenv('TELEGRAM_API_ID', ''),
        'telegram_api_hash': os.getenv('TELEGRAM_API_HASH', ''),
        'telegram_phone': os.getenv('TELEGRAM_PHONE', ''),
        'delay_between_channels': os.getenv('DELAY_BETWEEN_CHANNELS', '3'),
        'batch_size': os.getenv('BATCH_SIZE', '50'),
        'telegram_session': os.getenv('TELEGRAM_SESSION', 'crawler')
    }
    
    return render_template('index.html', **context)

def handle_config_form():
    """Handle configuration form submission."""
    try:
        # Get form data
        telegram_api_id = request.form.get('telegram_api_id')
        telegram_api_hash = request.form.get('telegram_api_hash')
        telegram_phone = request.form.get('telegram_phone')
        delay_between_channels = request.form.get('delay_between_channels')
        batch_size = request.form.get('batch_size')
        telegram_session = request.form.get('telegram_session')
        
        # Handle file upload for Google credentials
        google_credentials_file = None
        if 'google_credentials_file' in request.files and request.files['google_credentials_file'].filename:
            file = request.files['google_credentials_file']
            filename = f"service_account_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
            file_path = os.path.join('uploads', filename)
            os.makedirs('uploads', exist_ok=True)
            file.save(file_path)
            google_credentials_file = file_path
        
        # Read existing .env if it exists
        env_content = ""
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                env_content = f.read()
        
        # Parse existing env variables
        env_vars = {}
        for line in env_content.splitlines():
            if '=' in line and not line.strip().startswith('#'):
                key, value = line.strip().split('=', 1)
                env_vars[key] = value
        
        # Update with new values if provided
        if telegram_api_id:
            env_vars['TELEGRAM_API_ID'] = telegram_api_id
        if telegram_api_hash:
            env_vars['TELEGRAM_API_HASH'] = telegram_api_hash
        if telegram_phone:
            env_vars['TELEGRAM_PHONE'] = telegram_phone
        if delay_between_channels:
            env_vars['DELAY_BETWEEN_CHANNELS'] = delay_between_channels
        if batch_size:
            env_vars['BATCH_SIZE'] = batch_size
        if telegram_session:
            env_vars['TELEGRAM_SESSION'] = telegram_session
        
        # Generate new env content
        new_env_content = ""
        new_env_content += "# Telegram API credentials\n"
        new_env_content += f"TELEGRAM_API_ID={env_vars.get('TELEGRAM_API_ID', 'your_telegram_api_id')}\n"
        new_env_content += f"TELEGRAM_API_HASH={env_vars.get('TELEGRAM_API_HASH', 'your_telegram_api_hash')}\n"
        new_env_content += f"TELEGRAM_PHONE={env_vars.get('TELEGRAM_PHONE', 'your_phone_number')}\n\n"
        
        new_env_content += "# Optional settings\n"
        new_env_content += f"DELAY_BETWEEN_CHANNELS={env_vars.get('DELAY_BETWEEN_CHANNELS', '3')}\n"
        new_env_content += f"BATCH_SIZE={env_vars.get('BATCH_SIZE', '50')}\n"
        new_env_content += f"TELEGRAM_SESSION={env_vars.get('TELEGRAM_SESSION', 'crawler')}\n"
        
        # Keep existing SESSION_SECRET or generate a new one
        if 'SESSION_SECRET' in env_vars:
            new_env_content += f"SESSION_SECRET={env_vars['SESSION_SECRET']}\n"
        else:
            session_secret = secrets.token_hex(16)
            new_env_content += f"SESSION_SECRET={session_secret}\n"
        
        # Write the updated .env file
        with open('.env', 'w') as f:
            f.write(new_env_content)
        
        # Update the app's environment variables
        os.environ['TELEGRAM_API_ID'] = env_vars.get('TELEGRAM_API_ID', '')
        os.environ['TELEGRAM_API_HASH'] = env_vars.get('TELEGRAM_API_HASH', '')
        
        logger.info("Configuration saved successfully")
        
        # Detect AJAX requests by checking headers
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        logger.info(f"handle_config_form: is_ajax = {is_ajax}") # ADD THIS LINE
        
        response_data = {
            'success': True,
            'message': 'Configuration saved successfully',
            'telegram_api_id': env_vars.get('TELEGRAM_API_ID', ''),
            'telegram_api_hash': env_vars.get('TELEGRAM_API_HASH', ''),
            'telegram_phone': env_vars.get('TELEGRAM_PHONE', ''),
            'delay_between_channels': env_vars.get('DELAY_BETWEEN_CHANNELS', '3'),
            'batch_size': env_vars.get('BATCH_SIZE', '50'),
            'telegram_session': env_vars.get('TELEGRAM_SESSION', 'crawler'), 
            'redirect': url_for('index', _anchor='config')
        }
        
        if is_ajax:
            return jsonify(response_data), 200
        return redirect(url_for('index', _anchor='config'))
        
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        if request.headers.get('Accept') == 'application/json':
            return jsonify({
                'success': False,
                'message': f'Error saving configuration: {str(e)}'
            }), 500
        return redirect(url_for('index', _anchor='config'))

def handle_manual_input():
    """Handle manual channel input form submission."""
    channels_text = request.form.get('channels', '')
    channels = [
        channel.strip() for channel in channels_text.split('\n') 
        if channel.strip()
    ]
    
    if not channels:
        logger.warning("No channels entered")
        return redirect(url_for('index', _anchor='input'))
    
    # Store channels in TempStorage only
    TempStorage.set_channels(channels)
    logger.info(f"{len(channels)} channel(s) added")
    return redirect(url_for('index', _anchor='input'))

def handle_file_upload():
    """Handle file upload form submission."""
    if 'channelsFile' not in request.files:
        logger.warning("No file selected")
        return redirect(url_for('index', _anchor='input'))
        
    file = request.files['channelsFile']
    if file.filename == '':
        logger.warning("No file selected")
        return redirect(url_for('index', _anchor='input'))
        
    try:
        # Save the file temporarily
        filename = f"upload_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        filepath = os.path.join('uploads', filename)
        os.makedirs('uploads', exist_ok=True)
        file.save(filepath)
        
        # Parse the file based on its extension
        channels = []
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        if file_ext == '.json':
            with open(filepath, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    channels = data
                elif isinstance(data, dict) and 'channels' in data:
                    channels = data['channels']
        elif file_ext == '.csv':
            with open(filepath, 'r') as f:
                reader = csv.reader(f)
                channels = [row[0] for row in reader if row]
        else:  # Treat as plain text
            with open(filepath, 'r') as f:
                channels = [line.strip() for line in f if line.strip()]
        
        # Cleanup
        os.remove(filepath)
        
        if not channels:
            logger.warning("No channel usernames found in file")
            return redirect(url_for('index', _anchor='input'))
        
        # Store channels in TempStorage only
        TempStorage.set_channels(channels)
        logger.info(f"{len(channels)} channel(s) loaded from file")
        return redirect(url_for('index', _anchor='input'))
        
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return redirect(url_for('index', _anchor='input'))


def handle_start_crawler():
    """Handle start crawler form submission."""
    # Only use TempStorage for consistent behavior
    channels = TempStorage.channels()
    
    if not channels:
        logger.warning("No channels to process")
        return redirect(url_for('index', _anchor='input'))
    
    try:
        # Debug channels before processing
        logger.info(f"Before processing - Channels: {channels}")
        
        load_dotenv() # ADD THIS LINE
        # Load config from environment variables
        config = telegram_crawler.load_config()
        
        # Run the crawler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            telegram_crawler.process_channels(channels, config)
        )
        loop.close()
        
        # Debug the results
        logger.info(f"Crawler Results: {results}")
        
        # Store results in TempStorage only
        TempStorage.set_results(results)
        
        # Debug after storing
        logger.info(f"After processing - TempStorage results: {bool(TempStorage.results())}")
        logger.info(f"Result keys: {list(results.keys())}")
        if 'similar_channels' in results:
            logger.info(f"Similar channels count: {len(results['similar_channels'])}")
            logger.info(f"Channel names: {list(results['similar_channels'].keys())}")
        
        logger.info("Crawler completed successfully")
        return redirect(url_for('index', _anchor='results'))
        
    except Exception as e:
        logger.error(f"Error running crawler: {str(e)}")
        return redirect(url_for('index', _anchor='input'))

@app.route('/api/run-crawler', methods=['POST'])
def api_run_crawler():
    """API endpoint to run crawler asynchronously."""
    # Only use TempStorage for consistent behavior
    channels = TempStorage.channels()
    
    if not channels:
        return jsonify({
            'success': False, 
            'message': 'No channels to process.'
        }), 400
    
    try:
        load_dotenv() # ADD THIS LINE
        # Load config from environment variables
        config = telegram_crawler.load_config()
        
        # Run the crawler in a separate thread/process in a real app
        # For simplicity, we'll run it synchronously here
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            telegram_crawler.process_channels(channels, config)
        )
        loop.close()
        
        # Debug before storing
        logger.info(f"API Crawler Results: {results}")
        
        # Store results in TempStorage only
        TempStorage.set_results(results)
        
        # Debug after storing
        logger.info(f"API After storing - TempStorage results: {bool(TempStorage.results())}")
        logger.info(f"Result keys: {list(results.keys())}")
        if 'similar_channels' in results:
            logger.info(f"Similar channels count: {len(results['similar_channels'])}")
            logger.info(f"Channel names: {list(results['similar_channels'].keys())}")
        
        # Report completion
        message = 'Crawler completed successfully!'
        
        return jsonify({
            'success': True,
            'message': message,
            'channels_processed': len(channels),
            'similar_channels_found': sum(len(similar) for similar in results.get('similar_channels', {}).values())
        })
        
    except Exception as e:
        logger.error(f"Error running crawler API: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

# Export route
@app.route('/export-csv')
def export_csv():
    """Export the results as a CSV file."""
    results = TempStorage.results()
    
    if not results or 'export_data' not in results:
        logger.warning("No results available to export")
        return redirect(url_for('index', _anchor='results'))
    
    export_data = results['export_data']
    headers = export_data['headers']
    rows = export_data['rows']
    
    # Create a CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers and rows
    writer.writerow(headers)
    writer.writerows(rows)
    
    # Prepare response
    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=telegram_similar_channels_{timestamp}.csv'
        }
    )

# Gunicorn entry point
app = app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
