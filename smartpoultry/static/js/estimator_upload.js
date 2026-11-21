(() => {
    const input = document.getElementById('photos');
    const zone = document.getElementById('estimatorDropzone');
    const selection = document.getElementById('photoSelection');
    input.addEventListener('change', () => {
        selection.textContent = input.files.length === 1 ? input.files[0].name
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
