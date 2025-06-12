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

// Display a Bootstrap alert with a progress bar that fades automatically
window.showAlert = function (message, category = 'success') {
    const wrapper = document.createElement('div');
    wrapper.className = `alert alert-${category} alert-dismissible shadow position-relative`;
    wrapper.role = 'alert';
    wrapper.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;

    const progress = document.createElement('div');
    progress.className = `alert-progress bg-${category}`;
    progress.style.width = '100%';
    wrapper.appendChild(progress);

    let container = document.getElementById('alerts');
    if (!container) {
        container = document.createElement('div');
        container.id = 'alerts';
        container.className = 'position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
    }
    container.appendChild(wrapper);

    const duration = 3000;
    let remaining = duration;
    let timer;
    function startTimer() {
        timer = setInterval(() => {
            remaining -= 50;
            const pct = Math.max(0, remaining / duration * 100);
            progress.style.width = pct + '%';
            if (remaining <= 0) {
                clearInterval(timer);
                bootstrap.Alert.getOrCreateInstance(wrapper).close();
            }
        }, 50);
    }

    wrapper.addEventListener('mouseenter', () => clearInterval(timer));
    wrapper.addEventListener('mouseleave', () => startTimer());

    startTimer();
};

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

    // DOM is ready; nothing to do here for alerts since showAlert is global
});
