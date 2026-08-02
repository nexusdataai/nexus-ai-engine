# Nexus AI Engine — Planning Prompt

Use this prompt when generating or updating delivery artifacts.

## Source specifications

All plans must align with: `/opt/mycode/nexus/nexus-ai-engine/docs/spec/`

## Planning artifacts (nexus-sre pattern)

| Artifact | Location |
|----------|----------|
| Dev plan index | `docs/dev-plan/README.md` |
| Master scrum plan | `docs/dev-plan/000-master-plan.md` |
| Sprint calendar | `docs/dev-plan/020-sprint-calendar.md` |
| Release plans | `docs/dev-plan/releases/v*.md` |
| Sprint plans | `docs/dev-plan/sprints/sprint-NN-*.md` |
| Build plans (Cursor todos) | `docs/dev-plan/build/*.plan.md` and `/root/.cursor/plans/` |
| UAT plans | `docs/delivery/NNN-*-uat.md` |
| User guide | `docs/user-guide/` |

## Every release GA must include

1. **Backend/UI** implementation per build plan todos
2. **UAT** document written before GA sprint; **executed** with sign-off matrix
3. **User guide** chapter(s) updated in `docs/user-guide/`

## Releases

v0.2.0-alpha → v0.2.0-beta → v0.2.0-rc2 → v0.2.0 → v0.3.0 → v1.0.0

See `docs/dev-plan/000-master-plan.md` for sprint mapping.

## Closed-loop agent prompts

| Release | Prompt file |
|---------|-------------|
| v0.2.0-alpha | [closed-loop-v0.2.0-alpha.md](./closed-loop-v0.2.0-alpha.md) |

Usage: open Cursor **Agent** mode, attach `@docs/dev-plan/build/v0.2.0-alpha-foundation.plan.md`, paste the prompt from the closed-loop doc.
