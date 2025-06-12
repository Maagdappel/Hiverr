// Toggle between light and dark themes using Bootstrap 5's data-bs-theme
function setTheme(theme) {
    document.documentElement.setAttribute('data-bs-theme', theme);
    localStorage.setItem('theme', theme);
    const icon = document.querySelector('#theme-toggle i');
    if (icon) {
        if (theme === 'dark') {
            icon.className = 'mdi mdi-white-balance-sunny';
        } else {
            icon.className = 'mdi mdi-moon-waning-crescent';
        }
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const saved = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    setTheme(theme);

    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
        toggle.addEventListener('click', function () {
            const current = document.documentElement.getAttribute('data-bs-theme');
            const next = current === 'light' ? 'dark' : 'light';
            setTheme(next);
        });
    }

    window.showAlert = function(message, category='success') {
        const wrapper = document.createElement('div');
        wrapper.className = `alert alert-${category} alert-dismissible fade show`;
        wrapper.role = 'alert';
        wrapper.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
        let container = document.getElementById('alerts');
        if (!container) {
            container = document.createElement('div');
            container.id = 'alerts';
            container.className = 'position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '1100';
            document.body.appendChild(container);
        }
        container.appendChild(wrapper);
        setTimeout(() => {
            const alert = bootstrap.Alert.getOrCreateInstance(wrapper);
            alert.close();
        }, 3000);
    }
});
