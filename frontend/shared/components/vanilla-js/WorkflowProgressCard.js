/**
 * Vanilla JavaScript implementation of WorkflowProgressCard
 *
 * Provides a framework-free implementation for environments without React.
 * Features:
 * - No external dependencies
 * - CSS custom properties for theming
 * - Accessibility support
 * - Event-driven updates
 */

class WorkflowProgressCard {
  constructor(options = {}) {
    this.container = options.container;
    this.events = options.events || [];
    this.config = options.config || {};
    this.workflowTitle = options.workflowTitle || 'Workflow';

    // CSS custom properties for theming
    this.cssVars = {
      '--bg-gradient-start': this.config.plan?.gradient?.split(' ')[0] || '#f8fafc',
      '--bg-gradient-end': this.config.plan?.gradient?.split(' ')[1] || '#ffffff',
      '--primary-color': this.config.plan?.iconBg?.includes('blue') ? '#3b82f6' : '#6366f1',
      '--secondary-color': this.config.generate?.iconBg?.includes('violet') ? '#8b5cf6' : '#6366f1',
      '--success-color': '#10b981',
      '--border-radius': '8px',
      '--shadow': '0 2px 12px 0 rgba(80, 80, 120, 0.08), 0 1px 3px 0 rgba(80, 80, 120, 0.04)'
    };

    this.isVisible = true;
    this.currentEvent = null;

    this.init();
    this.update();
  }

  init() {
    if (!this.container) {
      console.error('WorkflowProgressCard: Container element is required');
      return;
    }

    // Create component structure
    this.element = this.createElement();
    this.container.appendChild(this.element);
  }

  createElement() {
    const wrapper = document.createElement('div');
    wrapper.className = 'workflow-progress-card-wrapper';
    wrapper.style.cssText = `
      display: flex;
      min-height: 180px;
      width: 100%;
      align-items: center;
      justify-content: center;
      padding: 8px;
    `;

    const card = document.createElement('div');
    card.className = 'workflow-progress-card';
    card.setAttribute('role', 'region');
    card.setAttribute('aria-live', 'polite');
    card.setAttribute('aria-label', 'Workflow progress');

    // Apply CSS custom properties
    Object.entries(this.cssVars).forEach(([prop, value]) => {
      card.style.setProperty(prop, value);
    });

    card.style.cssText = `
      width: 100%;
      border-radius: var(--border-radius);
      box-shadow: var(--shadow);
      border: none;
      transition: opacity 0.5s ease, transform 0.3s ease;
      background: linear-gradient(to-br, var(--bg-gradient-start), var(--bg-gradient-end));
    `;

    // Header
    const header = this.createHeader();
    card.appendChild(header);

    // Content
    const content = this.createContent();
    card.appendChild(content);

    // Progress
    const progress = this.createProgress();
    card.appendChild(progress);

    wrapper.appendChild(card);
    return wrapper;
  }

  createHeader() {
    const header = document.createElement('div');
    header.className = 'workflow-progress-header';
    header.style.cssText = `
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 12px 4px 12px;
    `;

    // Icon
    const iconContainer = document.createElement('div');
    iconContainer.style.cssText = `
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 50%;
      padding: 2px;
      background-color: var(--primary-color);
      color: white;
    `;

    const icon = document.createElement('span');
    icon.innerHTML = '⚙️'; // Default icon (plan)
    icon.style.cssText = 'font-size: 20px;';
    iconContainer.appendChild(icon);

    // Badge
    const badge = document.createElement('span');
    badge.className = 'workflow-badge';
    badge.style.cssText = `
      margin-left: 4px;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 500;
      background-color: var(--primary-color);
      color: white;
    `;
    badge.textContent = 'Progress';

    // Title
    const title = document.createElement('div');
    title.className = 'workflow-title';
    title.style.cssText = `
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 16px;
      font-weight: 600;
      color: #374151;
      flex: 1;
    `;

    const badgeContainer = document.createElement('span');
    badgeContainer.appendChild(badge);
    title.appendChild(badgeContainer);

    header.appendChild(iconContainer);
    header.appendChild(title);

    return header;
  }

  createContent() {
    const content = document.createElement('div');
    content.className = 'workflow-progress-content';
    content.style.cssText = 'padding: 4px 12px;';

    // Status container
    const statusContainer = document.createElement('div');
    statusContainer.className = 'status-container';
    statusContainer.style.cssText = `
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 8px 0;
    `;

    // Spinner
    const spinner = document.createElement('div');
    spinner.className = 'spinner';
    spinner.style.cssText = `
      width: 24px;
      height: 24px;
      border: 2px solid #e5e7eb;
      border-top: 2px solid var(--primary-color);
      border-radius: 50%;
      animation: spin 1s linear infinite;
      opacity: 0;
    `;

    // Status text
    const statusText = document.createElement('div');
    statusText.className = 'status-text';
    statusText.style.cssText = `
      text-align: center;
      font-size: 14px;
      font-weight: 500;
      color: #374151;
    `;
    statusText.textContent = 'Analyzing your request...';

    // Skeleton loader
    const skeleton = document.createElement('div');
    skeleton.className = 'skeleton';
    skeleton.style.cssText = `
      height: 12px;
      width: 128px;
      border-radius: 6px;
      background-color: #f3f4f6;
      opacity: 0;
    `;

    // Description container
    const descriptionContainer = document.createElement('div');
    descriptionContainer.className = 'description-container';
    descriptionContainer.style.cssText = 'display: flex; flex-direction: column; gap: 8px; padding: 8px 0;';

    const descriptionText = document.createElement('div');
    descriptionText.className = 'description-text';
    descriptionText.style.cssText = `
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 14px;
      font-weight: 500;
      color: #6b7280;
    `;

    const descriptionIcon = document.createElement('span');
    descriptionIcon.innerHTML = '⏳';
    descriptionIcon.style.cssText = 'font-size: 16px; color: var(--secondary-color);';

    const descriptionSpan = document.createElement('span');
    descriptionSpan.textContent = 'Working on the requirement:';

    descriptionText.appendChild(descriptionIcon);
    descriptionText.appendChild(descriptionSpan);

    const descriptionBox = document.createElement('div');
    descriptionBox.className = 'description-box';
    descriptionBox.style.cssText = `
      max-height: 96px;
      overflow-y: auto;
      border-radius: 6px;
      border: 1px solid #d1d5db;
      background-color: #f9fafb;
      padding: 8px;
      font-size: 12px;
      color: #374151;
      opacity: 0;
    `;

    descriptionContainer.appendChild(descriptionText);
    descriptionContainer.appendChild(descriptionBox);

    statusContainer.appendChild(spinner);
    statusContainer.appendChild(statusText);
    statusContainer.appendChild(skeleton);

    content.appendChild(statusContainer);
    content.appendChild(descriptionContainer);

    // Hide initially
    statusContainer.style.display = 'flex';
    descriptionContainer.style.display = 'none';

    return content;
  }

  createProgress() {
    const progress = document.createElement('div');
    progress.className = 'workflow-progress';
    progress.style.cssText = 'padding: 8px 12px 12px 12px;';

    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar';
    progressBar.style.cssText = `
      height: 4px;
      border-radius: 2px;
      background-color: #f3f4f6;
      overflow: hidden;
    `;

    const progressFill = document.createElement('div');
    progressFill.className = 'progress-fill';
    progressFill.style.cssText = `
      height: 100%;
      border-radius: 2px;
      background-color: var(--primary-color);
      width: 33%;
      transition: width 0.3s ease, background-color 0.3s ease;
    `;

    progressBar.appendChild(progressFill);
    progress.appendChild(progressBar);

    return progress;
  }

  update(newEvents) {
    if (newEvents !== undefined) {
      this.events = newEvents;
    }

    const events = this.events || [];
    this.currentEvent = events.length > 0 ? events[events.length - 1] : null;

    if (!this.currentEvent || !this.isVisible) {
      this.hide();
      return;
    }

    const { state, requirement } = this.currentEvent;
    const meta = this.config[state];

    if (!meta) {
      this.hide();
      return;
    }

    this.show();

    // Update styling based on state
    this.updateStyling(state, meta);

    // Update content based on state
    this.updateContent(state, requirement, meta);
  }

  updateStyling(state, meta) {
    if (!this.element) return;

    const card = this.element.querySelector('.workflow-progress-card');

    // Update gradients
    const gradientStart = meta.gradient?.split(' ')[0] || '#f8fafc';
    const gradientEnd = meta.gradient?.split(' ')[1] || '#ffffff';
    card.style.setProperty('--bg-gradient-start', gradientStart);
    card.style.setProperty('--bg-gradient-end', gradientEnd);

    // Update colors
    const primaryColor = meta.iconBg?.includes('blue') ? '#3b82f6' :
                        meta.iconBg?.includes('violet') ? '#8b5cf6' : '#6366f1';
    card.style.setProperty('--primary-color', primaryColor);

    // Update background
    card.style.background = `linear-gradient(to-br, ${gradientStart}, ${gradientEnd})`;
  }

  updateContent(state, requirement, meta) {
    if (!this.element) return;

    const header = this.element.querySelector('.workflow-progress-header');
    const content = this.element.querySelector('.workflow-progress-content');
    const progress = this.element.querySelector('.workflow-progress');

    // Update icon and badge
    const icon = header.querySelector('span');
    if (state === 'plan') {
      icon.innerHTML = '📋';
    } else if (state === 'generate') {
      icon.innerHTML = '✨';
    }

    const badge = header.querySelector('.workflow-badge');
    badge.textContent = meta.badgeText;
    badge.style.backgroundColor = `var(--${state === 'plan' ? 'primary' : 'secondary'}-color)`;

    // Update progress
    const progressFill = progress.querySelector('.progress-fill');
    progressFill.style.width = `${meta.progress}%`;
    progressFill.style.backgroundColor = `var(--${state === 'plan' ? 'primary' : 'secondary'}-color)`;

    // Toggle content visibility
    const statusContainer = content.querySelector('.status-container');
    const descriptionContainer = content.querySelector('.description-container');

    if (state === 'plan') {
      statusContainer.style.display = 'flex';
      descriptionContainer.style.display = 'none';

      const spinner = statusContainer.querySelector('.spinner');
      const skeleton = statusContainer.querySelector('.skeleton');
      spinner.style.opacity = '1';
      skeleton.style.opacity = '1';

    } else if (state === 'generate') {
      statusContainer.style.display = 'none';
      descriptionContainer.style.display = 'flex';

      const descriptionBox = descriptionContainer.querySelector('.description-box');
      const spinner = descriptionContainer.querySelector('span:first-child');

      if (requirement) {
        descriptionBox.textContent = requirement;
        descriptionBox.style.opacity = '1';
        spinner.style.opacity = '0';
      } else {
        descriptionBox.textContent = 'No requirements available yet.';
        descriptionBox.style.opacity = '0.6';
        spinner.style.opacity = '1';
      }
    }
  }

  show() {
    if (!this.element) return;
    this.isVisible = true;
    this.element.style.display = 'flex';
    this.element.style.opacity = '1';
  }

  hide() {
    if (!this.element) return;
    this.isVisible = false;
    this.element.style.opacity = '0';
    setTimeout(() => {
      if (!this.isVisible) {
        this.element.style.display = 'none';
      }
    }, 500);
  }

  destroy() {
    if (this.element && this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }
    this.element = null;
    this.isVisible = false;
  }
}

// Add required CSS animations
const style = document.createElement('style');
style.textContent = `
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  .skeleton {
    animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: .5; }
  }
`;
document.head.appendChild(style);

// Export for different module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = WorkflowProgressCard;
} else if (typeof define === 'function' && define.amd) {
  define([], () => WorkflowProgressCard);
} else {
  window.WorkflowProgressCard = WorkflowProgressCard;
}
