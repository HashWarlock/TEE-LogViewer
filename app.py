import os
from functools import wraps
from flask import Flask, render_template, request, jsonify, Response
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient
import hashlib
import logging
import tempfile
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "default-secret-key"

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Azure Storage settings
AZURE_CONNECTION_STRING = os.environ.get('AZURE_BLOB_CONNECTION_STRING')
ALLOWED_EXTENSIONS = {'log', 'txt'}

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            logger.warning("API request received without API key")
            return jsonify({'error': 'Missing API key', 'message': 'Please provide an API key in the X-API-Key header'}), 401
        if api_key != os.environ.get('LOG_VIEWER_API_KEY'):
            logger.warning("Invalid API key used in request")
            return jsonify({'error': 'Invalid API key', 'message': 'The provided API key is not valid'}), 401
        return f(*args, **kwargs)
    return decorated_function

def setup_dummy_data():
    """Initialize dummy log data in Azure storage"""
    if AZURE_CONNECTION_STRING:
        try:
            blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

            # Create containers if they don't exist
            for container_name in ['logs-original', 'logs-sanitized']:
                container_client = blob_service_client.get_container_client(container_name)
                container_client.create_container_if_not_exists()

                # Upload dummy log content
                blob_name = 'example_log.log'
                if container_name == 'logs-original':
                    content = DUMMY_LOG_CONTENT
                else:
                    content = sanitize_log_content(DUMMY_LOG_CONTENT)

                blob_client = container_client.get_blob_client(blob_name)
                try:
                    blob_client.upload_blob(content.encode(), overwrite=True)
                    logger.info(f"Uploaded dummy data to {container_name}/{blob_name}")
                except Exception as upload_error:
                    logger.error(f"Error uploading to {container_name}: {str(upload_error)}")

            logger.info("Dummy log data initialized")
        except Exception as e:
            logger.error(f"Error setting up dummy data: {str(e)}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    setup_dummy_data()  # Initialize dummy data when accessing the index
    return render_template('index.html')

@app.route('/api/logs', methods=['GET'])
def list_logs():
    """List all available log files"""
    if AZURE_CONNECTION_STRING:
        try:
            blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
            containers = ['logs-original', 'logs-sanitized']
            logs = []

            for container_name in containers:
                container_client = blob_service_client.get_container_client(container_name)
                try:
                    container_client.create_container_if_not_exists()
                    blobs = container_client.list_blobs()
                    logs.extend([{
                        'name': blob.name,
                        'type': 'sanitized' if container_name == 'logs-sanitized' else 'original',
                        'timestamp': blob.last_modified.isoformat() if hasattr(blob, 'last_modified') else datetime.now().isoformat(),
                        'size': blob.size if hasattr(blob, 'size') else 0
                    } for blob in blobs])
                except Exception as container_error:
                    logger.error(f"Error accessing container {container_name}: {str(container_error)}")

            return jsonify(logs)
        except Exception as e:
            logger.error(f"Error listing logs: {str(e)}")
            return jsonify({'error': str(e)}), 500
    return jsonify([])

@app.route('/api/logs/<path:filename>', methods=['GET'])
def get_log_content(filename):
    """Stream the content of a specific log file"""
    if AZURE_CONNECTION_STRING:
        try:
            blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
            container_name = 'logs-sanitized' if '.sanitized' in filename else 'logs-original'
            container_client = blob_service_client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(filename)

            def generate():
                try:
                    download_stream = blob_client.download_blob()
                    content = download_stream.readall().decode()
                    for line in content.split('\n'):
                        if line.strip():
                            event_data = {
                                'timestamp': datetime.now().isoformat(),
                                'level': 'INFO',
                                'message': line.strip(),
                                'redacted': '.sanitized' in filename
                            }
                            # Proper SSE format: each message must start with "data: " and end with two newlines
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
    return jsonify({'error': 'Azure storage not configured'}), 500

@app.route('/api/logs', methods=['POST'])
@require_api_key
def upload_log():
    """Upload a new log file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        filename = secure_filename(file.filename)
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file.save(temp_file.name)

            if AZURE_CONNECTION_STRING:
                blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

                # Upload original
                container_client = blob_service_client.get_container_client("logs-original")
                container_client.create_container_if_not_exists()
                blob_client = container_client.get_blob_client(filename)
                with open(temp_file.name, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

                # Create and upload sanitized version
                sanitized_content = sanitize_log_content(open(temp_file.name, 'r').read())

                container_client = blob_service_client.get_container_client("logs-sanitized")
                container_client.create_container_if_not_exists()
                blob_client = container_client.get_blob_client(filename + '.sanitized')
                blob_client.upload_blob(sanitized_content.encode(), overwrite=True)

            os.unlink(temp_file.name)

            return jsonify({
                'message': 'File uploaded successfully',
                'filename': filename
            })

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        return jsonify({'error': str(e)}), 500

DUMMY_LOG_CONTENT = '''Remote Attestation Quote generated successfully!
ECDSA Key Derived Successfully!
Cache miss for fetchPrices
Generating text...
INFORMATIONS
Generating text with options: {"modelProvider":"redpill","model":"small"}
INFORMATIONS
Selected model: nousresearch/hermes-3-llama-3.1-405b
Posting new tweet: Just spent 8 hours in the lab cooking up some fresh beats.
Nothing beats that feeling of getting lost in the creative process and watching a new track come to life...
Tweet posted: https://twitter.com/1ncipi3nt/status/1872414961731088670
LOGS
Creating Memory
90ee0675-99bc-017f-b810-1f4df68dfb5c
Next tweet scheduled in 14 minutes
Checking Twitter interactions
Finished checking Twitter interactions'''

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

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

@app.route('/upload', methods=['POST'])
@require_api_key
def upload_file():
    """Legacy upload endpoint with hash calculation"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file.save(temp_file.name)

            original_hash = calculate_file_hash(temp_file.name)
            content = open(temp_file.name, 'r').read()
            sanitized_content = sanitize_log_content(content)

            sanitized_path = temp_file.name + '.sanitized'
            with open(sanitized_path, 'w') as f:
                f.write(sanitized_content)

            sanitized_hash = calculate_file_hash(sanitized_path)

            if AZURE_CONNECTION_STRING:
                blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

                container_client = blob_service_client.get_container_client("logs-original")
                blob_client = container_client.get_blob_client(secure_filename(file.filename))
                with open(temp_file.name, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

                container_client = blob_service_client.get_container_client("logs-sanitized")
                blob_client = container_client.get_blob_client(secure_filename(file.filename) + '.sanitized')
                with open(sanitized_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)

            os.unlink(temp_file.name)
            os.unlink(sanitized_path)

            return jsonify({
                'message': 'File processed successfully',
                'original_hash': original_hash,
                'sanitized_hash': sanitized_hash,
                'azure_uploaded': bool(AZURE_CONNECTION_STRING)
            })

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)