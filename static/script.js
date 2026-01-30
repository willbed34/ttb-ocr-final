/* Alcohol Label Verifier JavaScript */

// Tab switching functionality
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    
    if (tab === 'single') {
        document.querySelector('.tabs .tab:first-child').classList.add('active');
        document.getElementById('single-tab').classList.add('active');
    } else {
        document.querySelector('.tabs .tab:last-child').classList.add('active');
        document.getElementById('batch-tab').classList.add('active');
    }
}

// Toggle extracted text visibility
function toggleExtracted(id) {
    const el = document.getElementById(id);
    if (el) {
        el.style.display = el.style.display === 'none' ? 'block' : 'none';
    }
}

// Show loading overlay
function showLoading(message, subtext) {
    const overlay = document.getElementById('loading-overlay');
    if (!overlay) return;
    
    const textEl = overlay.querySelector('.loading-text');
    const subtextEl = overlay.querySelector('.loading-subtext');
    
    if (message && textEl) textEl.textContent = message;
    if (subtext && subtextEl) subtextEl.textContent = subtext;
    
    overlay.classList.add('active');
}

// Hide loading overlay
function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
}

// Format time for display
function formatTime(seconds) {
    if (seconds < 1) {
        return `${(seconds * 1000).toFixed(0)}ms`;
    } else if (seconds < 60) {
        return `${seconds.toFixed(2)}s`;
    } else {
        const mins = Math.floor(seconds / 60);
        const secs = (seconds % 60).toFixed(1);
        return `${mins}m ${secs}s`;
    }
}

// Initialize event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Single upload form
    const singleForm = document.querySelector('#single-tab form');
    if (singleForm) {
        singleForm.addEventListener('submit', function() {
            showLoading('Verifying Label...', 'Extracting text and checking fields');
        });
    }
    
    // Batch upload form
    const batchForm = document.querySelector('#batch-tab form');
    if (batchForm) {
        batchForm.addEventListener('submit', function() {
            const fileInput = batchForm.querySelector('input[name="images"]');
            const fileCount = fileInput && fileInput.files ? fileInput.files.length : 0;
            showLoading(
                'Processing ' + fileCount + ' images...', 
                'This may take a few seconds per image'
            );
        });
    }
    
    // Add keyboard navigation for tabs
    document.addEventListener('keydown', function(e) {
        if (e.altKey && e.key === '1') {
            switchTab('single');
        } else if (e.altKey && e.key === '2') {
            switchTab('batch');
        }
    });
});
