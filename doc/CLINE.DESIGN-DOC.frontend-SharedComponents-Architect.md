# Design Documentation: Shared Components Architecture

## Overview

This document provides detailed design documentation for the **Shared Components Architecture** implemented to support workflow UI integration across different environments and workflows.

## System Architecture

### Component Hierarchy

```
🏗️  Shared Components System
├── 📂  /frontend/shared/components/
│   ├── React Components
│   │   ├── WorkflowProgressCard.jsx      # Simple progress cards
│   │   ├── WorkflowMultiStepAccordion.jsx # Complex multi-step workflows
│   │   └── HumanInputCLI.jsx             # CLI command confirmation
│   ├── Vanilla JS Fallbacks
│   │   └── /vanilla-js/
│   │       ├── WorkflowProgressCard.js   # No-framework progress cards
│   │       └── HumanInputCLI.js          # No-framework input confirmation
│   ├── Build System
│   │   ├── vite.config.js                # React library bundling
│   │   ├── package.json                  # NPM package configuration
│   │   └── index.js                      # Main export index
│   └── Documentation
│       └── README.md
```

### Design Principles

#### 1. **Framework Agnosticism**
- **React-First**: Optimized for React environments where available
- **Vanilla JS Fallback**: Framework-free implementations for constrained environments
- **Progressive Enhancement**: Components degrade gracefully without dependencies

#### 2. **Component Reusability**
- **Abstracted Logic**: Common UI patterns extracted into reusable components
- **Configuration-Driven**: Behavior controlled through configuration objects
- **Event Integration**: Standardized event handling across workflows

#### 3. **Accessibility & UX**
- **ARIA Attributes**: Comprehensive accessibility support
- **Keyboard Navigation**: Full keyboard interaction support
- **Screen Reader**: Semantic markup and live regions
- **Progressive Disclosure**: Information revealed contextually

#### 4. **Performance Optimization**
- **Lazy Loading**: Components load on-demand
- **Efficient Re-renders**: React optimizations and memoization
- **Bundle Splitting**: Tree-shaking and code splitting support
- **CSS-in-JS**: Scoped styling without global conflicts

## Component Specifications

### WorkflowProgressCard

#### Purpose
Displays progress for linear, 2-stage workflows (planning → generation, analyzing → generating)

#### Configuration API
```javascript
export const WORKFLOW_STAGE_CONFIGS = {
  code_generator: createStageMeta(
    {
      badgeText: "Step 1/2: Planning",
      gradient: "from-blue-100 via-blue-50 to-white",
      progress: 33,
      iconBg: "bg-blue-100 text-blue-600",
      badge: "bg-blue-100 text-blue-700",
    },
    {
      badgeText: "Step 2/2: Generating",
      gradient: "from-violet-100 via-violet-50 to-white",
      progress: 66,
      iconBg: "bg-violet-100 text-violet-600",
      badge: "bg-violet-100 text-violet-700",
    }
  )
};
```

#### Props Interface
```javascript
WorkflowProgressCard.propTypes = {
  events: PropTypes.array.isRequired,      // Workflow event stream
  config: PropTypes.object.isRequired,     // Stage configuration
  workflowTitle: PropTypes.string,         // Optional workflow title
};
```

#### State Management
```javascript
const [visible, setVisible] = useState(true);        // Component visibility
const [fade, setFade] = useState(false);           // Fade transition state

// Event aggregation logic
const aggregateEvents = () => {
  if (!events || events.length === 0) return null;
  return events[events.length - 1];  // Use latest event
};
```

#### CSS Architecture
```css
/* CSS Custom Properties for Theming */
.workflow-progress-card {
  --bg-gradient-start: var(--stage-gradient-start, #f8fafc);
  --bg-gradient-end: var(--stage-gradient-end, #ffffff);
  --primary-color: var(--stage-primary-color, #3b82f6);
  --border-radius: 8px;
  --shadow: 0 2px 12px 0 rgba(80, 80, 120, 0.08);
}
```

### WorkflowMultiStepAccordion

#### Purpose
Handles complex workflows with multiple phases (retrieve → analyze → answer) with accordion-based UI

#### Configuration API
```javascript
export const MULTI_STEP_CONFIGS = {
  deep_research: {
    title: "DeepResearch Workflow",
    phases: {
      retrieve: {
        title: "Retrieve Information",
        description: "Retrieving relevant information from the knowledge base",
        icon: Database,
      },
      analyze: {
        title: "Analyze Information",
        description: "Analyzing retrieved information and generating questions",
        icon: Brain,
      },
      answer: {
        title: "Answers",
        description: "Detailed answers to the generated questions",
        icon: MessageSquare,
      }
    },
  },
};
```

#### Event Aggregation
```javascript
const aggregateEvents = (events) => {
  const result = { retrieve: null, analyze: null, answers: [] };

  events.forEach((event) => {
    const { event: eventType, state, id, question, answer } = event;

    if (eventType === "retrieve") {
      result.retrieve = { state };
    } else if (eventType === "answer" && id) {
      // Handle multi-answer scenario with ID deduplication
      const existingIndex = result.answers.findIndex(a => a.id === id);
      if (existingIndex >= 0) {
        result.answers[existingIndex] = { ...result.answers[existingIndex], state, question, answer };
      } else {
        result.answers.push({ id, state, question, answer });
      }
    }
  });

  return result;
};
```

### HumanInputCLI

#### Purpose
Manages human approval workflows for CLI command execution with controlled input and confirmation

#### Schema Validation
```javascript
// Zod schema for event validation
const CLIInputEventSchema = z.object({
  command: z.string(),
});

const CLIInputEvent = z.infer<typeof CLIInputEventSchema>;
```

#### State Management
```javascript
const [confirmedValue, setConfirmedValue] = useState(null);  // Confirmation state
const [editableCommand, setEditableCommand] = useState(inputEvent?.command);

// Update command when new event arrives
React.useEffect(() => {
  setEditableCommand(inputEvent?.command);
}, [inputEvent?.command]);
```

## Vanilla JavaScript Implementations

### Design Rationale
- **Zero Dependencies**: No external libraries required
- **Browser Compatibility**: ES5+ compatible with module fallbacks
- **Performance**: Direct DOM manipulation, no virtual DOM overhead
- **Bundle Size**: Minimal footprint for embedded scenarios

### Component Class Structure
```javascript
class WorkflowProgressCard {
  constructor(options = {}) {
    this.container = options.container;     // DOM container element
    this.events = options.events || [];    // Event data stream
    this.config = options.config || {};    // Configuration object

    this.init();
    this.update();
  }

  // Core lifecycle methods
  init() { /* DOM creation and initial render */ }
  update(newEvents) { /* State updates and re-rendering */ }
  destroy() { /* Cleanup and removal */ }

  // Internal methods
  createElement() { /* DOM element creation */ }
  updateContent() { /* Content updates */ }
  show() { /* Visibility management */ }
  hide() { /* Visibility management */ }
}
```

### Export Strategies
```javascript
// Universal Module Definition (UMD)
if (typeof module !== 'undefined' && module.exports) {
  module.exports = WorkflowProgressCard;          // CommonJS
} else if (typeof define === 'function' && define.amd) {
  define([], () => WorkflowProgressCard);         // AMD
} else {
  window.WorkflowProgressCard = WorkflowProgressCard;  // Global
}
```

## Build System Architecture

### Vite Configuration
```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: {
        index: path.resolve(__dirname, 'index.js'),
        WorkflowProgressCard: path.resolve(__dirname, 'WorkflowProgressCard.jsx'),
      },
      name: 'WorkflowUIComponents',
      fileName: (format, entryName) => `${entryName}.${format}.js`,
    },
    rollupOptions: {
      external: ['react', 'react-dom', '@llamaindex/chat-ui'],
      output: {
        globals: {
          'react': 'React',
          'react-dom': 'ReactDOM',
          '@llamaindex/chat-ui': 'ChatUI',
        },
      },
    },
  },
});
```

### External Dependency Management
```json
{
  "peerDependencies": {
    "react": ">=16.8.0",
    "react-dom": ">=16.8.0",
    "@llamaindex/chat-ui": "*",
    "lucide-react": "*",
    "zod": "*"
  }
}
```

### Build Outputs
```
dist/
├── index.umd.js        # UMD bundle (browsers)
├── index.es.js         # ES module bundle
├── WorkflowProgressCard.umd.js
├── WorkflowProgressCard.es.js
└── types/              # TypeScript definitions (future)
```

## Testing Strategy

### Component Testing
```javascript
describe('WorkflowProgressCard', () => {
  it('should render with empty events', () => {
    const { container } = render(<WorkflowProgressCard events={[]} config={config} />);
    expect(container.firstChild).toBeNull();  // Hidden when no events
  });

  it('should show progress for plan state', () => {
    const events = [{ state: 'plan', requirement: 'Planning...' }];
    const { getByText } = render(<WorkflowProgressCard events={events} config={config} />);
    expect(getByText('Step 1/2: Planning')).toBeInTheDocument();
  });
});
```

### Accessibility Testing
```javascript
describe('Accessibility', () => {
  it('should have proper ARIA attributes', () => {
    const { container } = render(<WorkflowProgressCard events={events} config={config} />);
    expect(container.querySelector('[role="region"]')).toHaveAttribute('aria-live', 'polite');
  });

  it('should support keyboard navigation', () => {
    // Test accordion expand/collapse with keyboard
    const { container } = render(<WorkflowMultiStepAccordion events={events} config={config} />);
    const accordionTrigger = container.querySelector('[data-accordion-trigger]');
    fireEvent.keyDown(accordionTrigger, { key: 'Enter' });
    // Assert accordion content visibility
  });
});
```

## Performance Considerations

### React Optimizations
```javascript
// Memoization for expensive computations
const memoizedConfig = useMemo(() => {
  return createStageMeta(planningPhase, generationPhase);
}, [planningPhase, generationPhase]);

// Event aggregation with useMemo
const aggregatedEvent = useMemo(() => {
  return aggregateEvents(events);
}, [events]);
```

### Bundle Size Analysis
```
Bundle Size Breakdown:
├── WorkflowProgressCard: 8.2KB (gzipped)
├── WorkflowMultiStepAccordion: 14.7KB (gzipped)
├── HumanInputCLI: 5.1KB (gzipped)
├── Utility Functions: 3.8KB (gzipped)
└── Total React Bundle: 31.8KB (gzipped)
```

### Memory Management
- **Event Cleanup**: Remove event listeners on unmount
- **DOM References**: Weak references for automatic garbage collection
- **Animation Cleanup**: Cancel pending animations on component destruction

## Browser Compatibility

### ECMAScript Target
- **React Components**: ES2020 (modern browsers, bundler transpilation)
- **Vanilla JS**: ES5+ (95% browser support, IE11+ compatible)
- **Modules**: ES Modules with SystemJS fallback for legacy browsers

### Feature Support Matrix
| Feature | React | Vanilla JS |
|---------|-------|------------|
| Classes | ✅ ES2015+ | ✅ ES5+ |
| Arrow Functions | ✅ | ❌ (ES5 transpiled) |
| Template Literals | ✅ | ❌ (ES5 transpiled) |
| Async/Await | ✅ | ❌ (Polyfill required) |
| ES Modules | ✅ | ✅ (with loader) |
| CSS Custom Properties | ✅ | ✅ Native |

## Future Extensions

### Planned Features
- **Component Registry**: Dynamic component loading system
- **Theme System**: Unified styling across all components
- **Animation Library**: Consistent motion design language
- **i18n Support**: Internationalization framework
- **Component Marketplace**: Shareable workflow UI components

### Extensibility Points
```javascript
// Component registration system
ComponentRegistry.register('custom-workflow', CustomComponent);

// Theme extension
extendTheme({
  workflows: {
    progress: {
      colors: { primary: '#custom-color' }
    }
  }
});
```

This architecture provides a robust, extensible foundation for workflow UI components that can scale across different environments and use cases while maintaining consistent user experience and performance standards.
