document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const progressBar = document.getElementById('uploadProgress');
    const progressBarInner = progressBar.querySelector('.progress-bar');
    const results = document.getElementById('results');
    const errorAlert = document.getElementById('errorAlert');
    const logViewer = document.getElementById('logViewer');
    const fileList = document.getElementById('fileList');
    const clearButton = document.getElementById('clearLogs');
    const followButton = document.getElementById('toggleFollow');
    const refreshButton = document.getElementById('refreshFiles');
    let isFollowing = true;
    let currentEventSource = null;

    // Function to load and display files
    async function loadFiles() {
        try {
            const response = await fetch('/api/logs');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const files = await response.json();
            fileList.innerHTML = '';
            files.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
                .forEach(file => {
                    const item = document.createElement('a');
                    item.className = 'list-group-item';
                    item.setAttribute('data-filename', file.name);
                    item.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <i data-feather="file-text" class="me-2"></i>
                                ${file.name}
                            </div>
                            <span class="badge ${file.type === 'sanitized' ? 'bg-warning' : 'bg-info'}">
                                ${file.type}
                            </span>
                        </div>
                    `;
                    item.addEventListener('click', () => {
                        document.querySelectorAll('.list-group-item').forEach(el => el.classList.remove('active'));
                        item.classList.add('active');
                        loadLogContent(file.name);
                    });
                    fileList.appendChild(item);
                });
            feather.replace();
        } catch (error) {
            console.error('Error loading files:', error);
            errorAlert.textContent = `Error loading files: ${error.message}`;
            errorAlert.classList.remove('d-none');
        }
    }

    // Function to load log content
    async function loadLogContent(filename) {
        logViewer.innerHTML = '';
        if (currentEventSource) {
            currentEventSource.close();
        }

        try {
            currentEventSource = new EventSource(`/api/logs/${encodeURIComponent(filename)}`);

            currentEventSource.onmessage = function(event) {
                const logData = JSON.parse(event.data);
                appendLogEntry(logData);
            };

            currentEventSource.onerror = function(error) {
                console.error('EventSource error:', error);
                appendSystemMessage('Error streaming log. Reconnecting...');
                currentEventSource.close();
            };
        } catch (error) {
            console.error('Error setting up log stream:', error);
            appendSystemMessage(`Error: ${error.message}`);
        }
    }

    // Function to append log entries
    function appendLogEntry(logData) {
        const logLine = document.createElement('div');
        logLine.className = `log-line ${logData.redacted ? 'redacted' : ''}`;

        const timestamp = document.createElement('span');
        timestamp.className = 'log-timestamp';
        timestamp.textContent = new Date(logData.timestamp).toISOString();

        const level = document.createElement('span');
        level.className = 'log-level';
        level.textContent = logData.level;

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

    // Function to append system messages
    function appendSystemMessage(message) {
        const systemLine = document.createElement('div');
        systemLine.className = 'log-line system';
        systemLine.innerHTML = `<span class="log-timestamp">${new Date().toISOString()}</span> <span class="log-level">SYSTEM</span> ${message}`;
        logViewer.appendChild(systemLine);
    }

    // Event Listeners
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

    refreshButton.addEventListener('click', loadFiles);

    // Initial load
    loadFiles();

    // Set up periodic refresh
    setInterval(loadFiles, 30000); // Refresh every 30 seconds

    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const fileInput = document.getElementById('logFile');
        const file = fileInput.files[0];
        if (!file) {
            showError('Please select a file');
            return;
        }
        progressBar.classList.remove('d-none');
        results.classList.add('d-none');
        errorAlert.classList.add('d-none');
        progressBarInner.style.width = '0%';
        const formData = new FormData();
        formData.append('file', file);
        try {
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
            document.getElementById('originalHash').textContent = data.original_hash;
            document.getElementById('sanitizedHash').textContent = data.sanitized_hash;
            document.getElementById('azureStatus').textContent =
                data.azure_uploaded ? 'Successfully uploaded' : 'Azure storage not configured';
            results.classList.remove('d-none');
            uploadForm.reset();
            setTimeout(() => {
                progressBar.classList.add('d-none');
            }, 1000);
            loadFiles(); // Refresh file list after upload
        } catch (error) {
            showError(error.message);
            progressBar.classList.add('d-none');
        }
    });

    function showError(message) {
        errorAlert.textContent = message;
        errorAlert.classList.remove('d-none');
    }
});