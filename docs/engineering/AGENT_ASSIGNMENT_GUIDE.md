# Agent assignment guide

## Invoke the CTO

In a new Agent chat at the repository root:

```text
Use the cto subagent. Read .cursor/management/tasks.json and report the next eligible task.
```

Slash commands in `.cursor/commands/` do the same jobs. They appear in the `/` menu after Cursor loads the project. If a command is missing, paste its file body into the agent. That is the same workflow, not a failed assignment.

| Command | Action |
| --- | --- |
| `/cto-plan` | Read the repo and the registry, then propose tasks |
| `/cto-status` | Show status counts and active owners from `tasks.json` |
| `/cto-next` | Name the next task whose dependencies are completed |
| `/cto-assign RO-009` | Check ownership, then delegate that task |
| `/cto-review RO-009` | Check the report against the files and tests |
| `/cto-audit` | Run `python scripts/validate_agent_registry.py` and summarize |

## Invoke a specialist

```text
Use the security-engineer subagent for RO-009.
Read .cursor/skills/security-audit/SKILL.md.
Write only docs/engineering/reviews/RO-009-security.md.
Do not edit tasks.json.
```

If the product cannot start that subagent, keep the prompt and run it in another Agent chat. Do not record the task as `in_progress` until that session exists.

## Add a task

1. Choose the next free `RO-0xx` id.
2. Set `status` to `backlog` and `completion_report` to `null`.
3. Point `dependencies` at existing ids.
4. Set `files_allowed` so it does not overlap another active task.
5. Append a history row from `null` to `backlog`.
6. Run `python scripts/validate_agent_registry.py`.

## Assign, prioritize, or block

Assignment and priority edits belong to the CTO. Changing priority does not change status. Set `blocked` only with a reason and a resolution plan, then append history. The assignee does not write those fields.

## Request review and approve

Move work to `review`, then ask the `review_agents` to run. The implementing agent is not one of the approvers. Approval sets `testing` or `completed` only after the CTO runs `verification_commands` and stores the output in `completion_report`.

## Inspect history

Open the task's `history` array. It is the audit log. Do not rewrite old rows.

## Next assignment

RO-009 is the next security task. RO-013 is the next research task. Both have completed dependencies. RO-011 cannot start until RO-009 is completed. RO-012 stays in review until QA runs `python scripts/validate_project_management.py`.
