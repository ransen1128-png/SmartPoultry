(() => {
    const input = document.getElementById('photos');
    const zone = document.getElementById('estimatorDropzone');
    const selection = document.getElementById('photoSelection');
    const maxFiles = Number(input.dataset.maxFiles) || 0;
    input.addEventListener('change', () => {
        // The server enforces the same limit; this just fails fast before uploading.
        const tooMany = maxFiles && input.files.length > maxFiles;
        input.setCustomValidity(tooMany ? `Select at most ${maxFiles} photos at a time.` : '');
        selection.textContent = tooMany ? `${input.files.length} photos selected. The limit is ${maxFiles}.`
            : input.files.length === 1 ? input.files[0].name
            : input.files.length ? `${input.files.length} photos selected` : 'Drag and drop or click to upload';
    });
    ['dragenter', 'dragover'].forEach(name => zone.addEventListener(name, event => {
        event.preventDefault(); zone.classList.add('is-dragging');
    }));
    ['dragleave', 'drop'].forEach(name => zone.addEventListener(name, event => {
        event.preventDefault(); zone.classList.remove('is-dragging');
    }));
    zone.addEventListener('drop', event => {
        if (!event.dataTransfer.files.length) return;
        input.files = event.dataTransfer.files;
        input.dispatchEvent(new Event('change', {bubbles: true}));
    });
    const calibration = document.getElementById('useCalibration');
    function updateCalibration() {
        document.getElementById('calibrationFields').hidden = !calibration.checked;
        document.getElementById('pixelsPerCm').disabled = !calibration.checked;
        calibration.setAttribute('aria-expanded', String(calibration.checked));
    }
    calibration.addEventListener('change', updateCalibration);
    updateCalibration();
})();
