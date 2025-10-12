# Vanilla JavaScript Fallbacks

This directory contains vanilla JavaScript implementations of the shared UI components, providing fallback implementations for environments that don't have React or other framework dependencies.

## When to use

- Environments without React/JSX support
- Browser environments with strict security policies
- Embedded systems or older browsers
- Progressive enhancement scenarios

## Components

### WorkflowProgressCard.js
Vanilla JS implementation of progress card component with the following features:
- No framework dependencies
- CSS custom properties for theming
- Event-driven updates
- Accessibility support

### WorkflowMultiStepAccordion.js
Vanilla JS implementation for multi-step workflows:
- Native DOM manipulation
- Keyboard navigation support
- ARIA attributes for screen readers

### HumanInputCLI.js
Vanilla JS human input component:
- Native form elements
- Event handling without external dependencies

## Usage

```html
<!-- Include the vanilla components -->
<script src="/static/shared/vanilla-js/WorkflowProgressCard.js"></script>
<script src="/static/shared/vanilla-js/HumanInputCLI.js"></script>

<script>
// Initialize components
const progressCard = new WorkflowProgressCard({
  container: document.getElementById('progress-container'),
  events: workflowEvents,
  config: WORKFLOW_CONFIG
});
</script>
```

## Building

Use the provided Vite configuration to bundle these for production:

```bash
npm run build:vanilla
```

This creates minified versions in `/dist/vanilla/`.
