class WebcamCapture {
    constructor(videoElementId, canvasElementId) {
        this.video = document.getElementById(videoElementId);
        this.canvas = document.getElementById(canvasElementId);
        this.stream = null;
    }

    async startCamera() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { width: 640, height: 480 } 
            });
            this.video.srcObject = this.stream;
            return true;
        } catch (error) {
            console.error('Error accessing camera:', error);
            return false;
        }
    }

    capturePhoto() {
        const context = this.canvas.getContext('2d');
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;
        context.drawImage(this.video, 0, 0);
        return this.canvas.toDataURL('image/jpeg', 0.8);
    }

    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }
}

// Radio button functions
function switchInputMethod() {
    const uploadRadio = document.getElementById('upload-radio');
    const webcamRadio = document.getElementById('webcam-radio');
    
    if (uploadRadio.checked) {
        // Switch to upload
        document.getElementById('upload-section').style.display = 'block';
        document.getElementById('webcam-section').style.display = 'none';
        stopWebcam();
    } else if (webcamRadio.checked) {
        // Switch to webcam and start camera immediately
        document.getElementById('upload-section').style.display = 'none';
        document.getElementById('webcam-section').style.display = 'block';
        startWebcam(); // Automatically start the camera
    }
}

async function startWebcam() {
    if (!window.webcamCapture) {
        window.webcamCapture = new WebcamCapture('webcam-video', 'webcam-canvas');
    }
    
    const success = await window.webcamCapture.startCamera();
    if (success) {
        document.getElementById('webcam-video').style.display = 'block';
        document.getElementById('capture-photo').style.display = 'inline-block';
    } else {
        alert('Unable to access camera. Please check permissions and ensure you are using HTTPS.');
        // Switch back to upload mode if camera fails
        document.getElementById('upload-radio').checked = true;
        switchInputMethod();
    }
}

function capturePhoto() {
    if (!window.webcamCapture) return;
    
    const photoData = window.webcamCapture.capturePhoto();
    document.getElementById('webcam-data').value = photoData;
    
    // Show captured photo
    document.getElementById('webcam-canvas').style.display = 'block';
    document.getElementById('webcam-video').style.display = 'none';
    document.getElementById('capture-photo').style.display = 'none';
    document.getElementById('retake-photo').style.display = 'inline-block';
}

function retakePhoto() {
    document.getElementById('webcam-canvas').style.display = 'none';
    document.getElementById('webcam-video').style.display = 'block';
    document.getElementById('retake-photo').style.display = 'none';
    document.getElementById('capture-photo').style.display = 'inline-block';
    document.getElementById('webcam-data').value = '';
}

function stopWebcam() {
    if (window.webcamCapture) {
        window.webcamCapture.stopCamera();
        document.getElementById('webcam-video').style.display = 'none';
        document.getElementById('webcam-canvas').style.display = 'none';
        document.getElementById('capture-photo').style.display = 'none';
        document.getElementById('retake-photo').style.display = 'none';
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Set upload radio as default checked
    const uploadRadio = document.getElementById('upload-radio');
    if (uploadRadio) {
        uploadRadio.checked = true;
        switchInputMethod(); // Initialize the correct state
    }
});