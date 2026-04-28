# Task: Fix ESLint Warnings in sim-ui

## Steps

- [x] Edit `sim-ui/.eslintrc.js`
  - [x] Bump `ecmaVersion` from `2018` to `2020` to support optional chaining (`?.`)
- [x] Edit `sim-ui/src/App.js`
  - [x] Fix import order: `axios` before `react`
  - [x] Fix import order: `./ContextForm` before `./TimelineView`
  - [x] Add empty line between external and local import groups
  - [x] Disable `no-alert` for the alert on line 24
- [x] Edit `sim-ui/src/TimelineView.js`
  - [x] Fix import order: `axios`, then `d3`, then `react`
  - [x] Move `emotionScoreMap` and `parseEmotion` outside the component to fix `react-hooks/exhaustive-deps`
  - [x] Disable `no-alert` for the alert on line 181
  - [x] Fix missing closing `</div>` for `year-selector`
  - [x] Fix missing closing `</div>` for modal input/button wrapper
  - [x] Fix missing closing `</div>` for `modal-overlay`
- [x] Edit `sim-ui/src/index.js`
  - [x] Add empty line between external and local import groups
- [x] Verify by running ESLint — **0 errors, 0 warnings**

