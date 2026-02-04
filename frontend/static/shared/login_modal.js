/**
 * Login & User Selection Modal
 * 
 * Provides a stylish modal to pick from known users or add a new one.
 */

class LoginModalManager {
    constructor() {
        this.addStyles();
    }

    addStyles() {
        if (document.getElementById('login-modal-styles')) return;

        const style = document.createElement('style');
        style.id = 'login-modal-styles';
        style.textContent = `
            .user-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
                gap: 15px;
                margin-top: 20px;
                max-height: 300px;
                overflow-y: auto;
                padding: 5px;
            }
            
            .user-card {
                background: var(--bg-secondary, #f9fafb);
                border: 2px solid transparent;
                border-radius: 10px;
                padding: 15px;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 8px;
            }
            .user-card.selected { 
                border-color: var(--accent-color, #4f46e5);
                background: var(--bg-hover, #f3f4f6);
                box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
            }
            
            .prompt-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
                filter: grayscale(1);
            }
        `;
        document.head.appendChild(style);
    }

    async show() {
        return new Promise(async (resolve) => {
            // Fetch known users
            let users = [];
            try {
                const resp = await fetch('/api/system/known_users');
                const data = await resp.json();
                users = data.users || [];
            } catch (err) {
                console.error('Failed to fetch known users', err);
            }

            const overlay = document.createElement('div');
            overlay.className = 'prompt-overlay';

            overlay.innerHTML = `
                <div class="prompt-modal" style="max-width: 500px;">
                    <div class="prompt-header">
                        <h3>Associate User</h3>
                    </div>
                    <div class="prompt-body">
                        <p>Select an existing user profile.</p>
                        
                        <div class="user-grid" id="user-selection-grid">
                            ${users.map(u => `
                                <div class="user-card" data-user-id="${u}">
                                    <div class="user-avatar">${u.charAt(0).toUpperCase()}</div>
                                    <span class="user-name">${u}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div class="prompt-actions">
                        <button class="prompt-btn prompt-btn-accept" id="login-accept" disabled>ACCEPT</button>
                        <button class="prompt-btn prompt-btn-reject" id="login-cancel">REJECT</button>
                    </div>
                </div>
            `;

            document.getElementById('prompt-ui-container').appendChild(overlay);
            setTimeout(() => overlay.classList.add('active'), 10);

            const cleanup = (result) => {
                overlay.classList.remove('active');
                setTimeout(() => {
                    overlay.remove();
                    resolve(result);
                }, 300);
            };

            // Event Listeners
            let selectedUserId = null;
            const acceptBtn = overlay.querySelector('#login-accept');

            overlay.querySelectorAll('.user-card').forEach(card => {
                card.onclick = () => {
                    overlay.querySelectorAll('.user-card').forEach(c => c.classList.remove('selected'));
                    card.classList.add('selected');
                    selectedUserId = card.dataset.userId;
                    acceptBtn.disabled = false;
                };
            });

            overlay.querySelector('#login-accept').onclick = () => {
                if (selectedUserId) cleanup(selectedUserId);
            };

            overlay.querySelector('#login-cancel').onclick = () => cleanup(null);

            overlay.onclick = (e) => {
                if (e.target === overlay) cleanup(null);
            };
        });
    }
}

window.loginModal = new LoginModalManager();
