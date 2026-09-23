# Research: Hand-written /goal loop prompts (source examples)

## Metadata

**Date:** 2026-09-23
**Domain:** developer-experience
**Triggered by:** /hex-discuss autonomous-goal-loop — the source material for /hex-loop's template; copied verbatim from `.tmp/examples/loops/` (scratch that gets wiped)
**Expires:** N/A (verbatim source material)

## Direct Answer

These are the six prompts the user posted by hand to drive large goals through the hex modes. About 70% of each is the same invariant block; the rest is per run. They are the round-trip fixtures for /hex-loop.

## Example 1

````text
/goal

Go into full autonomous mode, do not prompt by any means.
Use /hex-architect, /hex-plan, /hex-execute, /hex-review and /hex-finalize to your liking.

Wait for the pending .claude/artifacts/adr_toolchain_activation.md refinement then /hex-plan high "Toolchain activation, per .claude/artifacts/adr_toolchain_activation.md" then fully implement the resulting plan.

You are the meta orchestrator. Forward as much work as possible to Opus 5 subagent orchestrators and keep the main context small.

If you find yourself in serious doubt, spawn a subagent orchestrator to reach a decisive recommendation by research — question, research, decision, all recorded.
Only in hard circumstances may it escalate and defer into a GitHub issue. Everything not deferred leads to an action that resolves the doubt.

!!RULES!!!!
- Do not get paranoid with security issues.
- You may diverge from our initial plan, but only on rare occasion and if justified with a very good reason, for example SOTA analysis or consistency with pre-existing code-base. Sparing implementation time by cutting features is NOT accepted.
- You should ensure solutions are state of the art.
- The target/ and /tmp directory are periodically wiped (every hour) to prevent memory outages. You may put no sensitive or work drafts in there. If something is temporarily critical put it into the project's .tmp directory but delete after. You are explicitly allowed to delete the .tmp directory.
- Always clean up stale temporary directories and worktress, you are explicitly allowed to delete them.
- Ensure to limit/monitor RAM usage, especially if rust-analyzer is not limited with concurrent usage, otherwise the WSL will abort.
- Call acceptance tests and taskfile test tasks explicitly to speed up workflow, circumventing the long acceptance test-suite in task verify, use task verify:mark to bypass commit hook. Do not use this hack on finalization.

Make explicitly sure that the implementation is well tested, incl. edge cases, therefore spawn explicitly subagents to looks for edge cases in your implementation and design tests before implementing.
The user documentation shall explicitly be use-case centric and showcase examples with ASCII casts highlighting the usage patterns and exemplary configuration snippets.
Ensure the documentation is consistent and complete, including the config/env var reference.

After the plan is implemented, run a self-refinement loop (max. 3 turns) with /hex-review and /hex-execute.
Thereafter create a single PR with all changes in on-draft mode and refine the feature branch until the pipeline runs through, incl. the manual Verify Deep workflow.
Once the branch is ready to merge/release use /hex-finalize.
You are explizitly allowed to force push to your feature branch.

Always take explicit care not to get stuck — wake-up routines that re-check state every 5 min, and pull any subagent that goes idle without reporting.

````

## Example 2

````text
/goal Go into full autonomous mode, do not prompt by any means. Use /hex-architect, /hex-plan, /hex-execute and /hex-review to your liking. 

You are the meta orchestrator. Forward as much work as possible to Opus 5 subagent orchestrators and keep the main context small.

If you find yourself in serious doubt, spawn a subagent orchestrator to reach a decisive recommendation by research — question, research, decision, all recorded. Only in hard circumstances may it escalate and defer into a GitHub issue. Everything not deferred leads to an action that resolves the doubt.

- Fully implement /home/mherwig/dev/ocx-mirror/.claude/state/plans/plan_mirror_signing.md
RULES!!!!
- do not get paranoid with security issues
- you may diverge from our initial plan, but only on rare occasion and if justified with a very good reason, for example SOTA analysis or consistency with pre-existing code-base. sparing impl time by cutting features is NOT accepted.
- you should ensure solutions are state of th art
- the target/ and /tmp directory are perdiodically wiped (every hour) to prevent memory outages. You may put no sensitive or work drafts in there. If sth. is temporarily critical put it into the projects .tmp directory but delete after. You are explcitly allowed to delete the .tmp directory.

After the plan is implemented, run a self-refinement loop (max. 3 turns) with /hex-review and /hex-execute.
Then /hex-finalize into a ready to merge PR. You are explicitly allowed to force-push to the feature branch. A PR must be created, merge-ready with green pipeline, incl. deep verify manual workflows.

Always take explicit care not to get stuck — wake-up routines that re-check state every 5 min, and pull any subagent that goes idle without reporting.

````

## Example 3

````text
/goal Go into full autonomous mode, do not prompt by any means. Use /hex-architect, /hex-plan, /hex-execute and /hex-review to your liking. You are the meta orchestrator. Forward as much work as possible to Opus 5 subagent orchestrators and keep the main context small.

If you find yourself in serious doubt, spawn a subagent orchestrator to reach a decisive recommendation by research — question, research, decision, all recorded. Only in hard circumstances may it escalate and defer into a GitHub issue. Everything not deferred leads to an action that resolves the doubt.

ocx 0.6.0 has been released. It is your goal to update the ocx-mirror to fully update the ocx-mirror to adopt the breaking changes and rendering.
Thereafter a new minor should be released and all @../ocx-contrib/ repositories should be updated to the new ocx version, this includes:
- not using ocx run anymore, the github action already does import the ocx env into the next action env, thus no ocx x/exec/run should be required

Rules
- Do not get paranoid with security issues, focus on your goal.
- The new signatures of ocx 0.6.0 are out of scope.
- Make sure to /hex-finalize before merging into main
- Use the Dev Deploy workflow to test a ocx-contib project using the dev.ocx.sh registry
- Do not loop /hex-review and /hex-execute too often, at most 3 times, if not converged earlier.

Explictily allowed
- Updating and realeasing a new patch of the GithubAction setup-ocx if it needs to be adjusted
- Force pushing onto a feature branch created
- Merging the feature branch and pushing on ocx-mirror main branch

Context
- /home/mherwig/dev/ocx-mirror/.claude/artifacts/handover_ocx_new_flag_removed.md
- /home/mherwig/dev/ocx-mirror/OCX-CLI-RENAME-HANDOVER.md
- https://github.com/ocx-sh/ocx-mirror/issues/58
- Changelog and repository of ocx cli

Always take explicit care not to get stuck — wake-up routines that re-check state every 5 min, and pull any subagent that goes idle without reporting.
````

## Example 4

````text
/goal

You are the meta-orchestrator. Forward as much work as possible to Opus 5 subagent orchestrators and keep the main context small.

Go fully autonomous, do not prompt by any means.

create the feature branch and commit the spec before any /hex-* runs.

Implement /home/mherwig/dev/ocx/.claude/artifacts/design_spec_cosign_parity.md
You probably should use /hex-architect to begin with or create a meta-plan of multiple inner loops.

You may use inner loops on subsets to parallelize the implementation. A inner smaller loop is (/hex-architect) -> /hex-plan -> /hex-execute -> /hex-review (limited to this inner loop work) -> /hex-execute (fix findings).
These inner loops should be executed by a Opus 5 sub-orchestrator.

If you find yourself in serious doubt, spawn a subagent orchestrator to reach a decisive recommendation by research — question, research, decision, all recorded. Only in hard circumstances may it escalate and defer into a GitHub issue. Everything not deferred leads to an action that resolves the doubt.

RULES!!!!
- do not get paranoid with security issues
- you may diverge from our initial plan, but only on rare occasion and if justified with a very good reason, for example SOTA analysis or consistency with pre-existing code-base. sparing impl time by cutting features is NOT accepted.
- you may refine the design spec but only during a initial /hex-architect /hex-review loop
- you should ensure solutions are state of th art
- the target/ and /tmp directory are perdiodically wiped (every hour) to prevent memory outages. You may put no sensitive or work drafts in there. If sth. is temporarily critical put it into the projects .tmp directory but delete after. You are explcitly allowed to delete the .tmp directory.

Use /hex-architect, /hex-plan, /hex-execute and /hex-review to your needs. May /hex-review larger chunks independently of the whole PR, targeting a specfic commit range introducing a larger sub-work. Use the bugfix workflow where appropriate. Any finding whose fix exceeds ~1200 LOC of production code AND are not part of this implementation becomes a follow-up issue instead.

After all findings are addressed, run a self-refinement loop (max. 3 turns) with /hex-review and /hex-execute.

Then squash and /finalize. You are explicitly allowed to force-push to the feature branch. The PR must end merge-ready: green pipeline, plus passing Quality Gate including Acceptance Test and manual Deep Verify Workflow.

Always take explicit care not to get stuck — wake-up routines that re-check state every 5 min, and pull any subagent that goes idle without reporting.

````

## Example 5

````text
/goal

    You are the meta-orchestrator, you're task is to orchestrator subagents and keep the main context as small as possible by forwarding as much work as possible to subagent orchestrators using Opus 5.

    Go fully autnomous, do not prompt by any means.
    If you find yourself in serious doubt spawn a subagent orchestrator to come up with a decicive recommendation, by research.
    Only in hard cicumstances the subagent should be able to escalate and defer the issue, into a GitHub issue.
    The decision process, including question, research and decision.
    Everything that is not defered leads to an action taken that resolved the doubt.
    
    Address all open issues mentioned in https://github.com/ocx-sh/ocx/pull/339.
    Use /hex-architect, /hex-plan and /hex-execute to your needs.
    RULES!!!!
      - do not get peranoid with security issues
      - explcitly document my decision to always constent the global toolchain and do not change it.
      - stick to the .claude/artifacts/adr_shell_env_overhaul.md
    After all issues are addressed go into a self-refinement loop (max. 2 turns) using /hex-review and /hex-execute. Address all findings related to the ADR, as well as smaller findings that do not take more than 1200LOC of production code.
    For all other findings create a follow-up issue on GitHub.
    Once the PR is ready to merge and release make sure to squash and /finalize it.
    You are explicitly allowed to force-push to the feature branch.
    In the end the PR should be ready to be merged and released with a green pipeline as well as passing the manual Deep Verify Workflow.
    You must fullfill this, issue pre-existing should be fixed according to the in doubt workflow.
    Make sure to use the bugfix workflow where appropriate.
    
    If you find the need to update the oci-client fork.
    Create a single feature branch and pr targeting the ocx/integration branch.
    
    Always take explicit care to not get stuck. Ie. with wake-up routines that enforce to double check the state every 5min.

````

## Example 6

````text
/goal

    You are the meta-orchestrator, you're task is to orchestrator subagents and keep the main context as small as possible by forwarding as much work as possible to subagent orchestrators using Opus 5.

    Go fully autnomous, do not prompt by any means.
    If you find yourself in serious doubt spawn a subagent orchestrator to come up with a decicive recommendation, by research.
    Only in hard cicumstances the subagent should be able to escalate and defer the issue, into a GitHub issue.
    The decision process, including question, research and decision.
    Everything that is not defered leads to an action taken that resolved the doubt.
    
    Use /hex-plan and /hex-execute to implement "Shell environment overhaul, per .claude/artifacts/adr_shell_env_overhaul.md".
    You should fullfill all the ADR requirements in a single feature branch with a single PR pushed on GitHub.
    After the initial implementation go into a self-refinement loop (max. 5 turns) using /hex-review and /hex-execute. Address all findings related to the ADR, as well as smaller findings that do not take more than 500LOC of production code.
    For all other findings create a follow-up issue on GitHub.
    Once the PR is ready to merge and release make sure to squash and /finalize it.
    You are explicitly allowed to force-push to the feature branch.
    In the end the PR should be ready to be merged and released with a green pipeline as well as passing the manual Deep Verify Workflow.
    
    Make explicitly sure that the implementation is well tested, incl. a rich set of shell tests that include very edgy cases.
    Make an explicit analysis rounds on edge-cases but also known cases and make sure all are tested via acceptance tests.
    The user documentation shall have a dedicated section (not chapter) incl. examples and ASCII casts highlighting common usage patterns, adding a package and cd-ing into/out a project.
    
    If you find the need to update the oci-client fork.
    Create a single feature branch and pr targeting the ocx/integration branch.
````
