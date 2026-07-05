/*
   SpecPilot AI Core JavaScript
   Manages client-side operations, theme switches, and interactive components.
*/

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Theme (Dark Mode is Default)
    const savedTheme = localStorage.getItem('specpilot-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeTogglerIcon(savedTheme);

    const themeToggleBtn = document.getElementById('theme-toggler');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('specpilot-theme', newTheme);
            updateThemeTogglerIcon(newTheme);
            
            // Log theme adjustment locally
            console.log(`Theme toggled to: ${newTheme}`);
        });
    }

    // 2. Responsive Sidebar Toggle for Mobile/Tablet Views
    const sidebarToggleBtn = document.getElementById('sidebar-toggler');
    const sidebar = document.querySelector('.sidebar');
    
    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('active');
        });
        
        // Close sidebar if clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (sidebar.classList.contains('active') && !sidebar.contains(e.target) && e.target !== sidebarToggleBtn) {
                sidebar.classList.remove('active');
            }
        });
    }

    // 3. Auto-Dismiss Toast Notifications after 5 seconds
    const toasts = document.querySelectorAll('.toast-alert');
    toasts.forEach(toast => {
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 5000);
    });
});

/**
 * Updates UI toggler button icon indicators based on active theme setting.
 */
function updateThemeTogglerIcon(theme) {
    const icon = document.querySelector('#theme-toggler i');
    if (icon) {
        if (theme === 'light') {
            icon.className = 'bi bi-moon-stars-fill';
        } else {
            icon.className = 'bi bi-sun-fill';
        }
    }
}
