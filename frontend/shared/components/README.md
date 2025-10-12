# Shared UI Components

This directory contains reusable React components for workflow UI elements that are shared across multiple workflows.

## 🚀 Quick Start

### Fresh Install Instructions

If you need to rebuild from scratch (recommended for new machines/deployments):

```bash
# 1. Remove old node_modules if it exists
rm -rf node_modules

# 2. Clean install dependencies
npm install

# 3. Build the vanilla JS components
npm run build

# That's it! React components are imported directly, vanilla ones are built.
```

## Components Overview

### WorkflowProgressCard (React)
Generic progress card component used by code generation and document generation workflows.

**Features:**
- Configurable stages with icons, badges, and colors
- Progress indicators with animations
- Support for different states (planning, generating, etc.)
- Accessibility-compliant with ARIA labels

### WorkflowMultiStepAccordion (React)
Complex multi-step workflow component used by deep research workflows.

**Features:**
- Accordion-based UI for multi-tiered workflows
- Support for retrieve/analyze/answer phases
- Status tracking for each step
- Progress indicators and completion tracking

### HumanInputCLI (React)
Human input component for CLI command approval workflows.

**Features:**
- Command display and editing capabilities
- Yes/No confirmation buttons
- Integration with chat UI annotations
- Form validation with Zod schemas

### Vanilla JS Components
For environments without React, vanilla JavaScript versions are provided:

- **vanilla-workflow-progress-card.js** - Framework-free progress cards
- **vanilla-human-input-cli.js** - Framework-free input confirmation

## Usage

### React Components (Direct Import)

```jsx
// In your React application
import WorkflowProgressCard from "./path/to/shared/components/WorkflowProgressCard.jsx";
import WorkflowMultiStepAccordion from "./path/to/shared/components/WorkflowMultiStepAccordion.jsx";
import HumanInputCLI from "./path/to/shared/components/HumanInputCLI.jsx";

// Use in workflow components
export default function MyWorkflowComponent({ events }) {
  return <WorkflowProgressCard events={events} config={STAGE_CONFIG} />;
}
```

### Vanilla JS Components (Built Bundles)

```html
<!-- In any HTML file -->
<script src="/path/to/dist/vanilla/vanilla-workflow-progress-card.js"></script>
<script>
const container = document.getElementById('workflow-container');
const progressCard = new WorkflowProgressCard({
  container: container,
  events: workflowEvents,
  config: WORKFLOW_CONFIG
});
</script>
```

## 🏗️ Build System Details

### Why Two Build Approaches?

**Original Issue:** Complex React dependencies (@llamaindex/chat-ui) and build conflicts made library bundling impractical.

**Solution:**
1. **React Components:** Imported directly in consuming applications (no library bundling)
2. **Vanilla JS Components:** Built as standalone UMD bundles for universal compatibility

### Build Scripts

```bash
# Build vanilla JS components only (what "npm run build" does)
npm run build
# Same as: npm run build:vanilla

# Build in development mode
npm run build:dev

# React components don't need building - they're source files
```

### File Structure After Build

```
super_starter_suite/frontend/shared/components/
├── dist/vanilla/
│   ├── vanilla-workflow-progress-card.js      # Built UMD bundle
│   └── vanilla-human-input-cli.js            # Built UMD bundle
├── WorkflowProgressCard.jsx                  # React component (source)
├── WorkflowMultiStepAccordion.jsx           # React component (source)
├── HumanInputCLI.jsx                         # React component (source)
└── vanilla-js/
    ├── WorkflowProgressCard.js              # Vanilla JS source
    └── HumanInputCLI.js                     # Vanilla JS source
```

## Configuration

### Component Config Examples

```javascript
// WorkflowProgressCard config
const WORKFLOW_CONFIGS = {
  code_generator: {
    plan: {
      badgeText: "Step 1/2: Planning",
      gradient: "from-blue-100 via-blue-50 to-white",
      progress: 33,
      // ... more config
    },
    generate: {
      badgeText: "Step 2/2: Generating",
      gradient: "from-violet-100 via-violet-50 to-white",
      progress: 66,
      // ... more config
    }
  }
};

// WorkflowMultiStepAccordion config
const MULTI_STEP_CONFIG = {
  title: "DeepResearch Workflow",
  phases: {
    retrieve: { title: "Retrieve", icon: Database },
    analyze: { title: "Analyze", icon: Brain },
    answer: { title: "Answer", icon: MessageSquare }
  }
};
```

## Browser Compatibility

| Component Type | React Version | Vanilla JS Version |
|---------------|---------------|-------------------|
| **Framework** | React ≥16.8 | ES5+ (IE11+) |
| **Async/Await** | ✅ Native | ❌ Polyfill needed |
| **CSS Custom Props** | ✅ Native | ✅ Native |
| **ARIA Support** | ✅ Full | ✅ Full |
| **Build Required** | ❌ No | ✅ Yes |
| **Dependencies** | Many external | ❌ Zero |

## Troubleshooting

### Build Fails
```bash
# Clear all cached files
rm -rf node_modules dist .vite

# Fresh install
npm install
npm run build
```

### React Components Not Found
- Ensure import paths are correct for your project structure
- React components are source files, not built bundles

### Vanilla JS Components Not Working
- Ensure the built bundles are included in your HTML
- Check browser console for JavaScript errors
- Verify DOM element IDs match component configuration

## Architecture Principles

1. **Framework Agnosticism** - Components work with or without React
2. **Progressive Enhancement** - Vanilla JS fallback for any environment
3. **Zero Dependencies** - Vanilla components have no external requirements
4. **Type Safety** - JSDoc comments provide inline type information
5. **Accessibility First** - All components support ARIA and keyboard navigation
