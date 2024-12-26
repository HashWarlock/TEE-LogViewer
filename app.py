import os
from flask import Flask, render_template
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Local storage settings
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'logs')

# Create logs directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    # Get list of log files
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if os.path.isfile(os.path.join(UPLOAD_FOLDER, filename)):
            files.append(filename)
    return render_template('index.html', files=files)

@app.route('/view/<filename>')
def view_log(filename):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(filepath):
            return "File not found", 404

        with open(filepath, 'r') as f:
            content = f.read()
        return render_template('view.html', filename=filename, content=content)
    except Exception as e:
        logger.error(f"Error reading log file: {str(e)}")
        return f"Error reading file: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)