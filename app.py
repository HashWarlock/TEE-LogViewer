import os
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename
import hashlib
import logging
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "default-secret-key"

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Local storage settings
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'logs')
ALLOWED_EXTENSIONS = {'log', 'txt'}

# Create logs directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/logs', methods=['GET'])
def list_logs():
    """List all available log files"""
    try:
        logger.debug("Listing files in logs directory")
        files = []
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath):
                file_stats = os.stat(filepath)
                files.append({
                    'name': filename,
                    'type': 'sanitized' if '.sanitized' in filename else 'original',
                    'timestamp': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    'size': file_stats.st_size
                })

        sorted_files = sorted(files, key=lambda x: x['timestamp'], reverse=True)
        logger.debug(f"Found {len(sorted_files)} log files")
        return jsonify(sorted_files)
    except Exception as e:
        error_msg = f"Error listing logs: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

@app.route('/api/logs/<path:filename>', methods=['GET'])
def get_log_content(filename):
    """Stream the content of a specific log file"""
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found'}), 404

        def generate():
            try:
                with open(filepath, 'r') as f:
                    for line in f:
                        if line.strip():
                            event_data = {
                                'timestamp': datetime.now().isoformat(),
                                'level': 'INFO',
                                'message': line.strip(),
                                'redacted': '.sanitized' in filename
                            }
                            yield f"data: {json.dumps(event_data)}\n\n"
            except Exception as stream_error:
                logger.error(f"Error streaming content: {str(stream_error)}")
                event_data = {
                    'timestamp': datetime.now().isoformat(),
                    'level': 'ERROR',
                    'message': f"Error streaming log: {str(stream_error)}",
                    'redacted': False
                }
                yield f"data: {json.dumps(event_data)}\n\n"

        return Response(generate(), mimetype='text/event-stream')
    except Exception as e:
        logger.error(f"Error accessing log: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs', methods=['POST'])
def upload_log():
    """Upload a new log file"""
    logger.debug("Received file upload request")

    if 'file' not in request.files:
        logger.warning("No file part in request")
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        logger.warning("No selected file")
        return jsonify({'error': 'No selected file'}), 400

    if not file or not allowed_file(file.filename):
        logger.warning(f"Invalid file type: {file.filename}")
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)

        # Save original file
        logger.debug(f"Saving original file to: {filepath}")
        file.save(filepath)
        logger.info(f"Saved original file: {filepath}")

        # Create sanitized version
        logger.debug("Creating sanitized version")
        sanitized_content = sanitize_log_content(open(filepath, 'r').read())
        sanitized_filepath = filepath + '.sanitized'
        with open(sanitized_filepath, 'w') as f:
            f.write(sanitized_content)
        logger.info(f"Saved sanitized file: {sanitized_filepath}")

        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename
        })

    except Exception as e:
        error_msg = f"Error uploading file: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

def sanitize_log_content(content):
    """Sanitize log content by redacting sensitive information"""
    lines = content.split('\n')
    sanitized_lines = []
    for line in lines:
        if any(sensitive in line.lower() for sensitive in ['password', 'token', 'key', 'secret']):
            timestamp = line[:24] if len(line) > 24 else ''
            sanitized_lines.append(f"{timestamp} [REDACTED] {hashlib.sha256(line.encode()).hexdigest()}")
        else:
            sanitized_lines.append(line)
    return '\n'.join(sanitized_lines)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)