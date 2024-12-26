document.addEventListener('DOMContentLoaded', function() {
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
            const response = await fetch('/');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const text = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(text, 'text/html');
            const newFileList = doc.getElementById('fileList');

            if (newFileList) {
                fileList.innerHTML = newFileList.innerHTML;
                feather.replace();
            }
        } catch (error) {
            console.error('Error loading files:', error);
        }
    }

    // Function to load log content
    function loadLogContent(filename) {
        if (!filename) return;

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
                currentEventSource.close();
            };
        } catch (error) {
            console.error('Error setting up log stream:', error);
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
        message.textContent = ' ' + logData.message;

        logLine.appendChild(timestamp);
        logLine.appendChild(message);
        logViewer.appendChild(logLine);

        if (isFollowing) {
            logViewer.scrollTop = logViewer.scrollHeight;
        }
    }

    // Event Listeners
    fileList.addEventListener('click', function(e) {
        e.preventDefault();
        const item = e.target.closest('.list-group-item');
        if (item) {
            const filename = item.dataset.filename;
            if (filename) {
                document.querySelectorAll('.list-group-item').forEach(el => el.classList.remove('active'));
                item.classList.add('active');
                loadLogContent(filename);
            }
        }
    });

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

    // Set up periodic refresh for file list
    setInterval(loadFiles, 5000);  // Refresh every 5 seconds

    // Initial load
    loadFiles().then(() => {
        // Auto-select first log file if available
        const firstLogFile = fileList.querySelector('.list-group-item');
        if (firstLogFile) {
            firstLogFile.classList.add('active');
            const filename = firstLogFile.dataset.filename;
            if (filename) {
                loadLogContent(filename);
            }
        }
    });
});