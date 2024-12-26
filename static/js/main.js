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
});
