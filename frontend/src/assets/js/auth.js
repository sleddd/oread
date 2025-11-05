/**
 * Frontend Authentication Helper
 * Handles session verification and redirects for protected pages
 */

// Get API base URL
const getAPIBase = () => {
    if (typeof CONFIG !== 'undefined' && CONFIG.API_BASE) {
        return CONFIG.API_BASE;
    }
    return `https://${window.location.hostname}:${window.location.port || '9000'}`;
};

// Check authentication status
async function checkAuthentication() {
    try {
        const response = await fetch(`${getAPIBase()}/auth/verify`, {
            credentials: 'include'
        });

        const result = await response.json();

        if (!result.authenticated) {
            // Not authenticated, redirect to login
            window.location.href = '/login';
            return false;
        }

        return true;
    } catch (error) {
        console.error('Authentication check failed:', error);
        // On error, redirect to login to be safe
        window.location.href = '/login';
        return false;
    }
}

// Handle logout
async function handleLogout() {
    try {
        // Get session ID before clearing storage
        const sessionId = sessionStorage.getItem('chatSessionId');

        const response = await fetch(`${getAPIBase()}/auth/logout`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sessionId: sessionId
            })
        });

        const result = await response.json();

        if (result.success) {
            // Clear session storage (session ID, character selection, etc.)
            sessionStorage.clear();

            // Redirect to login page
            window.location.href = '/login';
        } else {
            console.error('Logout failed:', result.error);
            alert('Failed to logout. Please try again.');
        }
    } catch (error) {
        console.error('Logout error:', error);
        alert('Network error during logout. Please try again.');
    }
}

// Initialize authentication check on page load
// This runs automatically when the script is loaded
(async function initAuth() {
    // Only check auth if not on login page
    if (!window.location.pathname.includes('/login')) {
        await checkAuthentication();
    }
})();

// Export for use in other scripts
window.authHelpers = {
    checkAuthentication,
    handleLogout
};