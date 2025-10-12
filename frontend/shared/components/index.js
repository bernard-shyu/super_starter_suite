// Shared UI Components for Workflow Integration
//
// This module exports all reusable React components for workflow UI elements.
// It provides a centralized import point for all shared components.
//
// Usage:
// import { WorkflowProgressCard, WorkflowMultiStepAccordion, HumanInputCLI } from '@/shared/components';

export { default as WorkflowProgressCard, createStageMeta, WORKFLOW_STAGE_CONFIGS } from './WorkflowProgressCard.jsx';
export { default as WorkflowMultiStepAccordion, MULTI_STEP_CONFIGS } from './WorkflowMultiStepAccordion.jsx';
export { default as HumanInputCLI } from './HumanInputCLI.jsx';

// Legacy export compatibility (can be removed after updating all imports)
export default {
  WorkflowProgressCard: () => import('./WorkflowProgressCard.jsx'),
  WorkflowMultiStepAccordion: () => import('./WorkflowMultiStepAccordion.jsx'),
  HumanInputCLI: () => import('./HumanInputCLI.jsx'),
};
