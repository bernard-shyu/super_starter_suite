/**
 * Vanilla JavaScript implementation of HumanInputCLI
 *
 * Provides a framework-free human input confirmation component
 * for CLI command execution workflows.
 */

class HumanInputCLI {
  constructor(options = {}) {
    this.container = options.container;
    this.events = options.events || [];
    this.onConfirm = options.onConfirm || (() => {});
    this.onCancel = options.onCancel || (() => {});

    this.currentEvent = null;
    this.confirmedValue = null;

    this.init();
    this.update();
  }

  init() {
    if (!this.container) {
      console.error('HumanInputCLI: Container element is required');
      return;
    }

    // Create component structure
    this.element = this.createElement();
    this.container.appendChild(this.element);
  }

  createElement() {
    const card = document.createElement('div');
    card.className = 'human-input-cli-card';
    card.setAttribute('role', 'region');
    card.setAttribute('aria-live', 'polite');
    card.setAttribute('aria-label', 'CLI command confirmation');

    card.style.cssText = `
      margin: 16px 0;
      border-radius: 6px;
      border: 1px solid #d1d5db;
      background-color: #ffffff;
    `;

    // Content
    const content = document.createElement('div');
    content.className = 'human-input-cli-content';
    content.style.cssText = 'padding: 24px 0 0 24px;';

    const promptText = document.createElement('p');
    promptText.className = 'human-input-cli-prompt';
    promptText.style.cssText = `
      font-size: 14px;
      color: #374151;
      margin-bottom: 8px;
    `;
    promptText.textContent = 'Do you want to execute the following command?';

    content.appendChild(promptText);

    // Command display/input
    const commandContainer = document.createElement('div');
    commandContainer.className = 'human-input-cli-command-container';
    commandContainer.style.cssText = 'margin-bottom: 8px;';

    const commandInput = document.createElement('input');
    commandInput.className = 'human-input-cli-command';
    commandInput.type = 'text';
    commandInput.disabled = true;
    commandInput.style.cssText = `
      width: 100%;
      overflow-x: auto;
      padding: 12px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      background-color: #f9fafb;
      font-family: 'Courier New', monospace;
      font-size: 12px;
      color: #1f2937;
      box-sizing: border-box;
    `;

    commandContainer.appendChild(commandInput);
    content.appendChild(commandContainer);
    card.appendChild(content);

    // Footer with buttons
    const footer = document.createElement('div');
    footer.className = 'human-input-cli-footer';
    footer.style.cssText = `
      padding: 0 24px 16px 24px;
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      opacity: 1;
      transition: opacity 0.3s ease;
    `;

    const yesButton = document.createElement('button');
    yesButton.className = 'human-input-cli-yes-btn';
    yesButton.textContent = 'Yes';
    yesButton.style.cssText = `
      padding: 8px 16px;
      border: none;
      border-radius: 6px;
      background-color: #3b82f6;
      color: white;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: background-color 0.2s ease;
    `;
    yesButton.addEventListener('click', () => this.handleConfirm());
    yesButton.addEventListener('mouseenter', () => {
      yesButton.style.backgroundColor = '#2563eb';
    });
    yesButton.addEventListener('mouseleave', () => {
      yesButton.style.backgroundColor = '#3b82f6';
    });

    const noButton = document.createElement('button');
    noButton.className = 'human-input-cli-no-btn';
    noButton.textContent = 'No';
    noButton.style.cssText = `
      padding: 8px 16px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      background-color: white;
      color: #374151;
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      transition: background-color 0.2s ease, border-color 0.2s ease;
    `;
    noButton.addEventListener('click', () => this.handleCancel());
    noButton.addEventListener('mouseenter', () => {
      noButton.style.backgroundColor = '#f9fafb';
      noButton.style.borderColor = '#9ca3af';
    });
    noButton.addEventListener('mouseleave', () => {
      noButton.style.backgroundColor = 'white';
      noButton.style.borderColor = '#d1d5db';
    });

    footer.appendChild(yesButton);
    footer.appendChild(noButton);
    card.appendChild(footer);

    return card;
  }

  update(newEvents) {
    if (newEvents !== undefined) {
      this.events = newEvents;
    }

    const events = this.events || [];

    // Find the latest CLI input event
    this.currentEvent = events
      .map((ev) => {
        // Check if this is a CLI input event
        if (ev && typeof ev === 'object' && ev.command) {
          return ev;
        }
        return null;
      })
      .filter((ev) => ev !== null)
      .at(-1); // Get the most recent

    if (!this.element) return;

    const commandInput = this.element.querySelector('.human-input-cli-command');
    const footer = this.element.querySelector('.human-input-cli-footer');

    if (this.currentEvent && this.confirmedValue === null) {
      commandInput.value = this.currentEvent.command || '';
      footer.style.display = 'flex';
      footer.style.opacity = '1';
      this.element.style.display = 'block';
    } else {
      footer.style.opacity = '0';
      setTimeout(() => {
        footer.style.display = 'none';
        this.element.style.display = 'none';
      }, 300);
    }
  }

  handleConfirm() {
    if (!this.currentEvent || this.confirmedValue !== null) return;

    this.confirmedValue = true;

    this.onConfirm({
      content: "Yes",
      role: "user",
      annotations: [
        {
          type: "human_response",
          data: {
            execute: true,
            command: this.element.querySelector('.human-input-cli-command').value,
          },
        },
      ],
    });
  }

  handleCancel() {
    if (!this.currentEvent || this.confirmedValue !== null) return;

    this.confirmedValue = false;

    this.onCancel({
      content: "No",
      role: "user",
      annotations: [
        {
          type: "human_response",
          data: {
            execute: false,
            command: this.currentEvent.command,
          },
        },
      ],
    });
  }

  reset() {
    this.confirmedValue = null;
    this.currentEvent = null;
    this.update();
  }

  destroy() {
    if (this.element && this.element.parentNode) {
      this.element.parentNode.removeChild(this.element);
    }
    this.element = null;
    this.confirmedValue = null;
    this.currentEvent = null;
  }
}

// Export for different module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = HumanInputCLI;
} else if (typeof define === 'function' && define.amd) {
  define([], () => HumanInputCLI);
} else {
  window.HumanInputCLI = HumanInputCLI;
}
