(function () {
    const containerId = 'toastContainer';

    function ensureContainer() {
        let container = document.getElementById(containerId);
        if (!container) {
            container = document.createElement('div');
            container.id = containerId;
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    function removeToast(toast, delay) {
        setTimeout(() => {
            if (toast && toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, delay);
    }

    function showToast(message, options) {
        const settings = Object.assign({
            title: '',
            type: 'info',
            duration: 3500
        }, options || {});

        const container = ensureContainer();
        const toast = document.createElement('div');
        toast.className = `toast toast--${settings.type}`;

        const content = document.createElement('div');
        if (settings.title) {
            const title = document.createElement('div');
            title.className = 'toast-title';
            title.textContent = settings.title;
            content.appendChild(title);
        }

        const body = document.createElement('div');
        body.className = 'toast-message';
        body.textContent = message;
        content.appendChild(body);

        toast.appendChild(content);
        container.appendChild(toast);

        if (settings.duration > 0) {
            removeToast(toast, settings.duration);
        }

        return toast;
    }

    window.showToast = showToast;
})();
