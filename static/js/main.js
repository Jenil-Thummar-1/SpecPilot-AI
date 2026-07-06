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

    // 3. Auto-Dismiss Toast Notifications with elegant animations
    const toasts = document.querySelectorAll('.toast-alert');
    toasts.forEach(toast => {
        // Set a timer to trigger dismissal fade
        setTimeout(() => {
            toast.style.transition = 'all 0.4s cubic-bezier(0.16, 1, 0.3, 1)';
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(-20px) scale(0.95)';
            setTimeout(() => {
                toast.remove();
            }, 400);
        }, 5000);
    });

    // 4. Smooth scroll for detail tabs
    const tabElList = [].slice.call(document.querySelectorAll('button[data-bs-toggle="tab"]'));
    tabElList.forEach(tabEl => {
        tabEl.addEventListener('shown.bs.tab', (event) => {
            // Remove active classes from other button tabs manually if needed to keep them sync
            tabElList.forEach(btn => {
                if (btn !== event.target) {
                    btn.classList.remove('text-white', 'active');
                } else {
                    btn.classList.add('text-white');
                }
            });
    // 5. Auto-apply data-progress to progress bars to avoid parsing errors in HTML template files
    document.querySelectorAll('.progress-bar[data-progress]').forEach(bar => {
        const progress = bar.getAttribute('data-progress') || '0';
        bar.style.width = progress + '%';
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
