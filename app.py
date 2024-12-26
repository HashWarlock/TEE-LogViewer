import os
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient
import hashlib
import logging
import tempfile

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "default-secret-key"

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Azure Storage settings
AZURE_CONNECTION_STRING = os.environ.get('AZURE_BLOB_CONNECTION_STRING')
ALLOWED_EXTENSIONS = {'log', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def sanitize_log_content(content):
    """Sanitize log content by redacting sensitive information"""
    lines = content.split('\n')
    sanitized_lines = []
    for line in lines:
        # Redact potential sensitive information
        if any(sensitive in line.lower() for sensitive in ['password', 'token', 'key', 'secret']):
            timestamp = line[:24] if len(line) > 24 else ''
            sanitized_lines.append(f"{timestamp} [REDACTED] {hashlib.sha256(line.encode()).hexdigest()}")
        else:
            sanitized_lines.append(line)
    return '\n'.join(sanitized_lines)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type'}), 400

    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file.save(temp_file.name)
            
            # Calculate original hash
            original_hash = calculate_file_hash(temp_file.name)
            
            # Read and sanitize content
            with open(temp_file.name, 'r') as f:
                content = f.read()
            sanitized_content = sanitize_log_content(content)
            
            # Save sanitized content
            sanitized_path = temp_file.name + '.sanitized'
            with open(sanitized_path, 'w') as f:
                f.write(sanitized_content)
            
            # Calculate sanitized hash
            sanitized_hash = calculate_file_hash(sanitized_path)
            
            # Upload to Azure if configured
            if AZURE_CONNECTION_STRING:
                blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
                
                # Upload original
                container_client = blob_service_client.get_container_client("logs-original")
                blob_client = container_client.get_blob_client(secure_filename(file.filename))
                with open(temp_file.name, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)
                
                # Upload sanitized
                container_client = blob_service_client.get_container_client("logs-sanitized")
                blob_client = container_client.get_blob_client(secure_filename(file.filename) + '.sanitized')
                with open(sanitized_path, "rb") as data:
                    blob_client.upload_blob(data, overwrite=True)
            
            # Cleanup
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
