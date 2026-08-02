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

| Release | Prompt file | Build plan |
|---------|-------------|------------|
| v0.2.0-alpha | [closed-loop-v0.2.0-alpha.md](./closed-loop-v0.2.0-alpha.md) | `build/v0.2.0-alpha-foundation.plan.md` |
| v0.2.0-beta | [closed-loop-v0.2.0-beta.md](./closed-loop-v0.2.0-beta.md) | `build/v0.2.0-beta-journey-dsl.plan.md` |
| v0.2.0-rc1 | *(add when needed)* | `build/v0.2.0-rc1-execution-engine.plan.md` |
| v0.2.0-rc2 | [closed-loop-v0.2.0-rc2.md](./closed-loop-v0.2.0-rc2.md) | `build/v0.2.0-rc2-tool-platform.plan.md` |
| v0.2.0 | [closed-loop-v0.2.0.md](./closed-loop-v0.2.0.md) | `build/v0.2.0-distributed-runtime.plan.md` |
| v0.3.0 | [closed-loop-v0.3.0.md](./closed-loop-v0.3.0.md) | `build/v0.3.0-journey-studio.plan.md` |
| v1.0.0 | [closed-loop-v1.0.0.md](./closed-loop-v1.0.0.md) | `build/v1.0.0-production-ga.plan.md` |

**Usage:** open Cursor **Agent** mode, attach `@docs/dev-plan/build/<release>.plan.md`, paste the **Prompt (copy from here)** section from the matching closed-loop doc.

**Prerequisite chain:** alpha → beta → rc1 → rc2 → v0.2.0 → v0.3.0 → v1.0.0 (each release must be tagged before the next closed-loop starts).
