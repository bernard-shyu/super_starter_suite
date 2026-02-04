/**
 * Common Prompt & Style Component
 * 
 * Provides stylish alternatives to native window.confirm() and window.alert()
 */

class PromptUIManager {
    constructor() {
        this.addStyles();
        this.createContainer();
    }

    addStyles() {
        if (document.getElementById('prompt-ui-styles')) return;

        const style = document.createElement('style');
        style.id = 'prompt-ui-styles';
        style.textContent = `
            .prompt-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(4px);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            .prompt-overlay.active { opacity: 1; }
            
            .prompt-modal {
                background: var(--panel-bg, #fff);
                border-radius: 12px;
                box-shadow: 0 15px 50px rgba(0,0,0,0.3);
                width: 90%;
                max-width: 450px;
                padding: 30px;
                transform: scale(0.9);
                transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
                border: 1px solid var(--border-color, #eee);
            }
            .prompt-overlay.active .prompt-modal { transform: scale(1); }
            
            .prompt-header { margin-bottom: 20px; }
            .prompt-header h3 { 
                margin: 0; 
                font-size: 20px; 
                color: var(--text-primary, #333); 
                font-weight: 600;
            }
            
            .prompt-body { 
                margin-bottom: 30px; 
                color: var(--text-secondary, #666);
                line-height: 1.5;
                font-size: 15px;
            }
            
            .prompt-actions { 
                display: flex; 
                justify-content: flex-end; 
                gap: 12px; 
            }
            
            .prompt-btn {
                padding: 10px 22px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s;
                border: none;
            }
            
            .prompt-btn-cancel {
                background: var(--bg-secondary, #f5f5f5);
                color: var(--text-primary, #333);
            }
            .prompt-btn-cancel:hover { background: var(--bg-hover, #e0e0e0); }
            
            .prompt-btn-confirm {
                background: var(--accent-color, #4f46e5);
                color: white;
            }
            .prompt-btn-confirm:hover { 
                background: var(--accent-hover, #4338ca);
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
            }
            
            .prompt-btn-danger {
                background: #ef4444;
                color: white;
            }
            .prompt-btn-danger:hover { background: #dc2626; }
            
            .prompt-btn-accept {
                background: #10b981;
                color: white;
            }
            .prompt-btn-accept:hover { 
                background: #059669;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
            }
            
            .prompt-btn-reject {
                background: #ef4444;
                color: white;
            }
            .prompt-btn-reject:hover { 
                background: #dc2626;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
            }
        `;
        document.head.appendChild(style);
    }

    createContainer() {
        if (document.getElementById('prompt-ui-container')) return;
        const container = document.createElement('div');
        container.id = 'prompt-ui-container';
        document.body.appendChild(container);
    }

    async confirm(title, message, options = {}) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'prompt-overlay';

            const isDanger = options.type === 'danger';
            const isAcceptReject = options.type === 'acceptReject';

            let confirmClass = 'prompt-btn-confirm';
            if (isDanger) confirmClass = 'prompt-btn-danger';
            if (isAcceptReject) confirmClass = 'prompt-btn-accept';

            let cancelClass = 'prompt-btn-cancel';
            if (isAcceptReject) cancelClass = 'prompt-btn-reject';

            overlay.innerHTML = `
                <div class="prompt-modal">
                    <div class="prompt-header">
                        <h3>${title}</h3>
                    </div>
                    <div class="prompt-body">
                        ${message}
                    </div>
                    <div class="prompt-actions">
                        <button class="prompt-btn ${cancelClass}" id="prompt-cancel">${options.cancelText || (isAcceptReject ? 'Reject' : 'Cancel')}</button>
                        <button class="prompt-btn ${confirmClass}" id="prompt-confirm">${options.confirmText || (isAcceptReject ? 'Accept' : 'Confirm')}</button>
                    </div>
                </div>
            `;

            document.getElementById('prompt-ui-container').appendChild(overlay);

            // Trigger animation
            setTimeout(() => overlay.classList.add('active'), 10);

            const cleanup = (result) => {
                overlay.classList.remove('active');
                setTimeout(() => {
                    overlay.remove();
                    resolve(result);
                }, 300);
            };

            overlay.querySelector('#prompt-cancel').onclick = () => cleanup(false);
            overlay.querySelector('#prompt-confirm').onclick = () => cleanup(true);

            // Close on overlay click
            overlay.onclick = (e) => {
                if (e.target === overlay) cleanup(false);
            };
        });
    }

    async alert(title, message, options = {}) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'prompt-overlay';

            overlay.innerHTML = `
                <div class="prompt-modal">
                    <div class="prompt-header">
                        <h3>${title}</h3>
                    </div>
                    <div class="prompt-body">
                        ${message}
                    </div>
                    <div class="prompt-actions">
                        <button class="prompt-btn prompt-btn-confirm" id="prompt-ok">OK</button>
                    </div>
                </div>
            `;

            document.getElementById('prompt-ui-container').appendChild(overlay);
            setTimeout(() => overlay.classList.add('active'), 10);

            const cleanup = () => {
                overlay.classList.remove('active');
                setTimeout(() => {
                    overlay.remove();
                    resolve();
                }, 300);
            };

            overlay.querySelector('#prompt-ok').onclick = cleanup;
        });
    }
}

// Global initialization
window.promptUI = new PromptUIManager();

// Export cleaner helper
window.showConfirm = (title, message, options) => window.promptUI.confirm(title, message, options);
window.showAlert = (title, message, options) => window.promptUI.alert(title, message, options);
