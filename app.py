import os
from flask import Flask, render_template, request, jsonify, Response
from werkzeug.utils import secure_filename
import logging
import json
from datetime import datetime

app = Flask(__name__)

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
    # Get list of log files
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if os.path.isfile(os.path.join(UPLOAD_FOLDER, filename)):
            files.append(filename)
    return render_template('index.html', files=files)

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
                    # First read existing content
                    content = f.read()
                    for line in content.splitlines():
                        if line.strip():
                            event_data = {
                                'timestamp': datetime.now().isoformat(),
                                'message': line.strip()
                            }
                            yield f"data: {json.dumps(event_data)}\n\n"

                    # Then seek to end and wait for new content
                    f.seek(0, 2)  # Seek to end
                    while True:
                        line = f.readline()
                        if line:
                            if line.strip():
                                event_data = {
                                    'timestamp': datetime.now().isoformat(),
                                    'message': line.strip()
                                }
                                yield f"data: {json.dumps(event_data)}\n\n"
            except Exception as stream_error:
                logger.error(f"Error streaming content: {str(stream_error)}")
                event_data = {
                    'timestamp': datetime.now().isoformat(),
                    'message': f"Error streaming log: {str(stream_error)}"
                }
                yield f"data: {json.dumps(event_data)}\n\n"

        return Response(generate(), mimetype='text/event-stream')
    except Exception as e:
        logger.error(f"Error accessing log: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logs', methods=['POST'])
def upload_log():
    """Upload a new log file via HTTP endpoint"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        logger.info(f"File uploaded via API: {filepath}")

        return jsonify({
            'message': 'File uploaded successfully',
            'filename': filename
        })
    except Exception as e:
        error_msg = f"Error uploading file: {str(e)}"
        logger.error(error_msg)
        return jsonify({'error': error_msg}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)