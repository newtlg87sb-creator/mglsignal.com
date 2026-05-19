document.addEventListener('DOMContentLoaded', function() {
    // Disable right-click context menu
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault();
    });

    // Disable text selection
    document.body.style.userSelect = 'none';
    document.body.style.webkitUserSelect = 'none'; // For Safari
    document.body.style.mozUserSelect = 'none';    // For Firefox
    document.body.style.msUserSelect = 'none';     // For Internet Explorer/Edge

    // Disable common copy/cut/paste keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Disable F12 (developer tools)
        if (e.key === 'F12' || e.keyCode === 123) {
            e.preventDefault();
        }

        // Disable Ctrl+C (copy), Ctrl+X (cut), Ctrl+U (view source)
        if (e.ctrlKey && (e.key === 'c' || e.key === 'u' || e.key === 'x')) {
            e.preventDefault();
        }
        
        // Disable Ctrl+Shift+I (developer tools)
        if (e.ctrlKey && e.shiftKey && e.key === 'I') {
            e.preventDefault();
        }
    });
});