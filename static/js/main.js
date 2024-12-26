document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const progressBar = document.getElementById('uploadProgress');
    const progressBarInner = progressBar.querySelector('.progress-bar');
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
            files.forEach(file => {
                const item = document.createElement('a');
                item.className = 'list-group-item';
                item.setAttribute('data-filename', file.name);
                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i data-feather="file-text" class="me-2"></i>
                            ${file.name}
                        </div>
                        <small class="text-muted">
                            ${new Date(file.timestamp).toLocaleString()}
                        </small>
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
            showError(`Error loading files: ${error.message}`);
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
                showError('Error streaming log. Please try again.');
                currentEventSource.close();
            };
        } catch (error) {
            console.error('Error setting up log stream:', error);
            showError(`Error: ${error.message}`);
        }
    }

    // Function to append log entries
    function appendLogEntry(logData) {
        const logLine = document.createElement('div');
        logLine.className = 'log-line';

        const timestamp = document.createElement('span');
        timestamp.className = 'log-timestamp';
        timestamp.textContent = new Date(logData.timestamp).toLocaleString();

        const message = document.createElement('span');
        message.className = 'log-message';
        message.textContent = logData.message;

        logLine.appendChild(timestamp);
        logLine.appendChild(message);
        logViewer.appendChild(logLine);

        if (isFollowing) {
            logViewer.scrollTop = logViewer.scrollHeight;
        }
    }

    // Event Listeners
    clearButton.addEventListener('click', () => {
        logViewer.innerHTML = '';
    });

    followButton.addEventListener('click', () => {
        isFollowing = !isFollowing;
        followButton.querySelector('i').setAttribute('data-feather', isFollowing ? 'eye' : 'eye-off');
        feather.replace();
        if (isFollowing) {
            logViewer.scrollTop = logViewer.scrollHeight;
        }
    });

    refreshButton.addEventListener('click', loadFiles);

    // File upload handling
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const fileInput = document.getElementById('logFile');
        const file = fileInput.files[0];

        if (!file) {
            showError('Please select a file');
            return;
        }

        progressBar.classList.remove('d-none');
        errorAlert.classList.add('d-none');
        progressBarInner.style.width = '0%';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/logs', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Upload failed: ${response.status}`);
            }

            progressBarInner.style.width = '100%';
            setTimeout(() => {
                progressBar.classList.add('d-none');
                uploadForm.reset();
            }, 1000);

            await loadFiles();
        } catch (error) {
            showError(error.message);
            progressBar.classList.add('d-none');
        }
    });

    function showError(message) {
        errorAlert.textContent = message;
        errorAlert.classList.remove('d-none');
    }

    // Initial load
    loadFiles();
});