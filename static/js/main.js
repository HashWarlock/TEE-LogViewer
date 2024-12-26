document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const progressBar = document.getElementById('uploadProgress');
    const progressBarInner = progressBar.querySelector('.progress-bar');
    const results = document.getElementById('results');
    const errorAlert = document.getElementById('errorAlert');

    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const fileInput = document.getElementById('logFile');
        const file = fileInput.files[0];
        
        if (!file) {
            showError('Please select a file');
            return;
        }

        // Reset UI
        progressBar.classList.remove('d-none');
        results.classList.add('d-none');
        errorAlert.classList.add('d-none');
        progressBarInner.style.width = '0%';

        const formData = new FormData();
        formData.append('file', file);

        try {
            // Simulate upload progress
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 5;
                if (progress <= 90) {
                    progressBarInner.style.width = `${progress}%`;
                    progressBarInner.setAttribute('aria-valuenow', progress);
                }
            }, 100);

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            clearInterval(progressInterval);
            progressBarInner.style.width = '100%';
            progressBarInner.setAttribute('aria-valuenow', 100);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            // Show results
            document.getElementById('originalHash').textContent = data.original_hash;
            document.getElementById('sanitizedHash').textContent = data.sanitized_hash;
            document.getElementById('azureStatus').textContent = 
                data.azure_uploaded ? 'Successfully uploaded' : 'Azure storage not configured';
            
            results.classList.remove('d-none');
            
            // Reset form
            uploadForm.reset();

            setTimeout(() => {
                progressBar.classList.add('d-none');
            }, 1000);

        } catch (error) {
            showError(error.message);
            progressBar.classList.add('d-none');
        }
    });

    function showError(message) {
        errorAlert.textContent = message;
        errorAlert.classList.remove('d-none');
    }

    const logViewer = document.getElementById('logViewer');
    const clearButton = document.getElementById('clearLogs');
    const followButton = document.getElementById('toggleFollow');
    let isFollowing = true;

    // Connect to log stream
    function connectLogStream() {
        const source = new EventSource('/stream');

        source.onmessage = function(event) {
            const logData = JSON.parse(event.data);
            appendLogEntry(logData);
        };

        source.onerror = function() {
            appendSystemMessage('Connection lost. Reconnecting...');
            source.close();
            setTimeout(connectLogStream, 5000);
        };
    }

    function appendLogEntry(logData) {
        const logLine = document.createElement('div');
        logLine.className = `log-line ${logData.redacted ? 'redacted' : ''}`;

        // Format timestamp
        const timestamp = document.createElement('span');
        timestamp.className = 'log-timestamp';
        timestamp.textContent = logData.timestamp;

        // Format log level
        const level = document.createElement('span');
        level.className = 'log-level';
        level.textContent = logData.level;

        // Format message
        const message = document.createElement('span');
        message.className = 'log-message';
        message.textContent = logData.message;

        logLine.appendChild(timestamp);
        logLine.appendChild(level);
        logLine.appendChild(message);
        logViewer.appendChild(logLine);

        if (isFollowing) {
            logViewer.scrollTop = logViewer.scrollHeight;
        }
    }

    function appendSystemMessage(message) {
        const systemLine = document.createElement('div');
        systemLine.className = 'log-line system';
        systemLine.textContent = `[SYSTEM] ${message}`;
        logViewer.appendChild(systemLine);
    }

    // Event handlers
    clearButton.addEventListener('click', function() {
        logViewer.innerHTML = '';
        appendSystemMessage('Logs cleared');
    });

    followButton.addEventListener('click', function() {
        isFollowing = !isFollowing;
        followButton.querySelector('i').setAttribute('data-feather', isFollowing ? 'eye' : 'eye-off');
        feather.replace();

        if (isFollowing) {
            logViewer.scrollTop = logViewer.scrollHeight;
        }
    });

    // Initialize
    connectLogStream();
});