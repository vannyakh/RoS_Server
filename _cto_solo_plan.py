import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from copy import deepcopy

tz = timezone(timedelta(hours=7))
now = datetime.now(tz).replace(microsecond=0).isoformat()

# --- team.json: allow SOLO status path ---
team_path = Path(".cursor/management/team.json")
team = json.loads(team_path.read_text(encoding="utf-8"))
for agent in team["agents"]:
    if agent["id"] == "cto":
        paths = agent["allowed_paths"]
        if "docs/SOLO_GAMEPLAY_STATUS.md" not in paths:
            paths.append("docs/SOLO_GAMEPLAY_STATUS.md")
        agent["allowed_paths"] = paths
team["updated_at"] = now
team_path.write_text(json.dumps(team, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# --- tasks.json ---
tasks_path = Path(".cursor/management/tasks.json")
data = json.loads(tasks_path.read_text(encoding="utf-8"))
by_id = {t["id"]: t for t in data["tasks"]}

def hist(actor, fr, to, from_agent, to_agent, note):
    return {
        "at": now,
        "actor": actor,
        "from_status": fr,
        "to_status": to,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "note": note,
    }

# Promote RO-070 ready
t70 = by_id["RO-070"]
if t70["status"] == "backlog":
    t70["history"].append(hist("cto", "backlog", "ready", "api-engineer", "api-engineer",
        "RO-058 completed. Solo BR plan: match result report can be assigned when API capacity frees; not on first-playable critical path."))
    t70["status"] = "ready"
    t70["updated_at"] = now

# Bump RO-068 priority for first playable
t68 = by_id["RO-068"]
if t68.get("priority") != "high":
    t68["priority"] = "high"
    t68["history"].append(hist("cto", t68["status"], t68["status"], t68["assigned_agent"], t68["assigned_agent"],
        "Solo BR first playable: raise priority so bot research follows RO-057."))
    t68["updated_at"] = now

# Adjust RO-069 deps: island visibility before jump; add RO-110 later once created
t69 = by_id["RO-069"]
old_deps = list(t69.get("dependencies") or [])
new_deps = ["RO-059", "RO-061", "RO-068", "RO-110"]
if old_deps != new_deps:
    t69["dependencies"] = new_deps
    t69["priority"] = "high"
    t69["history"].append(hist("cto", t69["status"], t69["status"], t69["assigned_agent"], t69["assigned_agent"],
        "Solo BR first playable: bots visible after space+bot research+fill config; removed hard dep on RO-063 (parachute). Added RO-110."))
    t69["updated_at"] = now
    t69["description"] = (
        "Spawn fair AI-controlled bot entities in the gateway match so the original client shows other survivors "
        "(first playable: 9 bots with human). Use Robot (or researched type from RO-068). Movement must use "
        "documented sync messages only — no teleport, wallhack, or omniscience. LLM bots are forbidden. "
        "Minimum bar: bots visible on prep island / in AoI with names; advanced combat AI is RO-111+."
    )

# New gap tasks
new_tasks = [
    {
        "id": "RO-109",
        "title": "Solo BR gameplay status tracker",
        "phase": "09",
        "description": (
            "Maintain docs/SOLO_GAMEPLAY_STATUS.md as the Solo Battle Royale first-playable checklist. "
            "Statuses stay NOT_CHECKED until LDPlayer evidence exists. Proposed params (1+9 bots, warmup, maps) "
            "are labeled unverified. Map vision stages to RO-### without inventing opcodes or a parallel server tree."
        ),
        "category": "governance",
        "assigned_agent": "cto",
        "status": "ready",
        "priority": "high",
        "dependencies": ["RO-100"],
        "research_references": [
            "docs/SOLO_GAMEPLAY_STATUS.md",
            "docs/RESTORATION_STATUS.md",
            "docs/project/MASTER_ROADMAP.md",
        ],
        "files_allowed": [
            "docs/SOLO_GAMEPLAY_STATUS.md",
            "docs/project/MASTER_ROADMAP.md",
        ],
        "acceptance_criteria": [
            "docs/SOLO_GAMEPLAY_STATUS.md lists first-playable gates with NOT_CHECKED/VERIFIED rules",
            "Proposed solo config table marks params as unverified",
            "Architecture mapping names existing bigworld_gateway/ + app/ paths only",
            "No feature is marked compatible or VERIFIED without cited LDPlayer evidence",
        ],
        "verification_commands": [
            "python scripts/validate_project_management.py",
            "python -c \"from pathlib import Path; assert Path('docs/SOLO_GAMEPLAY_STATUS.md').is_file()\"",
        ],
        "review_agents": ["qa-engineer"],
        "test_evidence": [
            "CTO created initial stub 2026-11-26 with NOT_CHECKED defaults and first-playable wave",
        ],
        "compatibility_status": "not_applicable",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "completion_report": None,
        "block_reason": None,
        "resolution_plan": None,
        "history": [
            hist(None, None, "backlog", None, "cto", "Opened for Solo BR + AI bots milestone adoption."),
            hist("cto", "backlog", "ready", "cto", "cto", "Stub written; keep updated as Phase 09 gates move."),
        ],
    },
    {
        "id": "RO-110",
        "title": "Solo match fill config (1 human + N bots)",
        "phase": "09",
        "description": (
            "Document and implement gateway-local Solo fill settings for first playable: 1 human, start with 9 bots "
            "(configurable toward 29/59/119 later), proposed warmup ~30s, map id selection left unknown until researched. "
            "Lives under bigworld_gateway/server/battle/ (MatchSession modules/data) — not a new server/modules tree. "
            "Do not invent opcodes; do not import app/. Params are proposed until LDPlayer proves them."
        ),
        "category": "architecture",
        "assigned_agent": "backend-architect",
        "status": "backlog",
        "priority": "high",
        "dependencies": ["RO-058", "RO-107"],
        "research_references": [
            "docs/SOLO_GAMEPLAY_STATUS.md",
            "docs/engineering/GATEWAY_BATTLE_SESSION.md",
            "docs/engineering/RO-107-hall-start-match.md",
        ],
        "files_allowed": [
            "docs/engineering/SOLO_MATCH_FILL.md",
            "bigworld_gateway/server/battle/data/solo_fill.json",
            "bigworld_gateway/server/battle/modules/solo_fill.py",
            "tests/compatibility/gateway/solo_fill/**",
        ],
        "acceptance_criteria": [
            "SOLO_MATCH_FILL.md states proposed defaults (1 human, 9 bots, warmup) as unverified and names the JSON keys",
            "solo_fill.json loads and exposes N bots + warmup seconds without claiming original matchmaking rules",
            "Module register(session) hooks MatchSession without importing app/",
            "Unit tests cover default N=9 and that N can be raised without code edits to ros_server.py",
            "No Mercury opcode is invented; unknown map/mode ids are listed as remaining_issues",
        ],
        "verification_commands": [
            ".\\.venv\\Scripts\\python.exe -m pytest tests/compatibility/gateway/solo_fill -q --tb=line",
            "python scripts/validate_agent_registry.py",
            "python scripts/validate_project_management.py",
        ],
        "review_agents": ["qa-engineer"],
        "test_evidence": [],
        "compatibility_status": "unknown",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "completion_report": None,
        "block_reason": None,
        "resolution_plan": None,
        "history": [
            hist(None, None, "backlog", None, "backend-architect", "Gap task from Solo BR milestone: auto-fill config."),
        ],
    },
    {
        "id": "RO-111",
        "title": "Bot AI engine design (FSM/BT, fair perception)",
        "phase": "09",
        "description": (
            "Design non-LLM bot AI for the gateway match: behavior tree or FSM, perception limits, navmesh/collision "
            "assumptions, and combat rules that forbid teleport, wallhack, and omniscience. Map onto "
            "bigworld_gateway/server/battle/modules/ after RO-068/RO-069 entity sync is known. Research evidence only "
            "until wire/movement messages are documented — do not invent opcodes."
        ),
        "category": "architecture",
        "assigned_agent": "backend-architect",
        "status": "backlog",
        "priority": "medium",
        "dependencies": ["RO-068", "RO-069"],
        "research_references": [
            "docs/SOLO_GAMEPLAY_STATUS.md",
            "bigworld_gateway/docs/BOT_ENTITIES.md",
        ],
        "files_allowed": [
            "docs/engineering/BOT_AI_ENGINE.md",
            "bigworld_gateway/server/battle/data/bot_ai_notes.json",
        ],
        "acceptance_criteria": [
            "BOT_AI_ENGINE.md chooses FSM or behavior-tree and lists states/behaviors for loot, move, engage, flee",
            "Document defines fair perception (range/FOV or equivalent) and forbids teleport/wallhack/omniscience/LLM",
            "Nav/collision data sources are named or marked unknown with remaining_issues",
            "No opcode or property layout is invented; cites RO-068 evidence only",
        ],
        "verification_commands": [
            "python scripts/validate_project_management.py",
            "python -c \"import json;json.load(open('bigworld_gateway/server/battle/data/bot_ai_notes.json',encoding='utf-8'))\"",
        ],
        "review_agents": ["gameplay-test-engineer"],
        "test_evidence": [],
        "compatibility_status": "researching",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "completion_report": None,
        "block_reason": None,
        "resolution_plan": None,
        "history": [
            hist(None, None, "backlog", None, "backend-architect", "Gap task: fair bot AI beyond spawn/visibility."),
        ],
    },
    {
        "id": "RO-112",
        "title": "Solo bot scale gates 9 to 29/59/119",
        "phase": "09",
        "description": (
            "Define and measure performance/scale gates for bot counts 9 → 29 → 59 → 119 on the gateway process "
            "(CPU, memory, tick/send budget). Do not treat proposed caps as capacity until measured. No LLM bots."
        ),
        "category": "performance",
        "assigned_agent": "performance-engineer",
        "status": "backlog",
        "priority": "medium",
        "dependencies": ["RO-069", "RO-110"],
        "research_references": [
            "docs/SOLO_GAMEPLAY_STATUS.md",
            "docs/performance/PERFORMANCE_BASELINE.md",
        ],
        "files_allowed": [
            "docs/performance/SOLO_BOT_SCALE.md",
            "reports/performance/solo_bot_scale.json",
            "tests/performance/test_solo_bot_scale.py",
        ],
        "acceptance_criteria": [
            "SOLO_BOT_SCALE.md records a measured run or explicit skip reason for N=9",
            "Gates for 29/59/119 are listed as NOT measured until a disposable run exists",
            "Report JSON stores timestamps and machine notes without secrets",
            "No original-compatibility claim",
        ],
        "verification_commands": [
            "python scripts/validate_project_management.py",
        ],
        "review_agents": ["cto"],
        "test_evidence": [],
        "compatibility_status": "not_applicable",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "completion_report": None,
        "block_reason": None,
        "resolution_plan": None,
        "history": [
            hist(None, None, "backlog", None, "performance-engineer", "Gap task: scale gates for Solo BR bot counts."),
        ],
    },
    {
        "id": "RO-113",
        "title": "First-playable Solo BR LDPlayer acceptance",
        "phase": "09",
        "description": (
            "Acceptance run on LDPlayer with the original APK: Solo Start → match → observe 9 bots → aircraft → "
            "parachute → land. Capture gateway logs and screenshots. Do not invent opcodes. Failures list the owning RO-###."
        ),
        "category": "quality",
        "assigned_agent": "qa-engineer",
        "status": "backlog",
        "priority": "critical",
        "dependencies": ["RO-061", "RO-062", "RO-063", "RO-069", "RO-110"],
        "research_references": [
            "docs/SOLO_GAMEPLAY_STATUS.md",
            "docs/testing/hall_start_match.md",
        ],
        "files_allowed": [
            "docs/testing/solo_first_playable.md",
            "docs/SOLO_GAMEPLAY_STATUS.md",
            "tests/compatibility/gateway/solo_first_playable/**",
        ],
        "acceptance_criteria": [
            "solo_first_playable.md has a pass/fail checklist for Start, 9 bots visible, plane, parachute, land",
            "Each pass cites a log line or screenshot path; each fail cites owning task id",
            "SOLO_GAMEPLAY_STATUS.md first-playable row updated only with evidence (VERIFIED or BROKEN)",
            "No compatible claim for original server behavior",
        ],
        "verification_commands": [
            "python scripts/validate_project_management.py",
        ],
        "review_agents": ["cto", "game-compatibility-engineer"],
        "test_evidence": [],
        "compatibility_status": "unknown",
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
        "completion_report": None,
        "block_reason": None,
        "resolution_plan": None,
        "history": [
            hist(None, None, "backlog", None, "qa-engineer", "Gap task: first-playable Solo BR acceptance on LDPlayer."),
        ],
    },
]

# Fix RO-109 history first entry actor null - schema may require keys
for t in new_tasks:
    for h in t["history"]:
        if h["actor"] is None:
            h["actor"] = "cto"
        # first history from_status null is OK

# Promote RO-110 to ready (deps RO-058, RO-107 completed)
for t in new_tasks:
    if t["id"] == "RO-110":
        t["history"].append(hist("cto", "backlog", "ready", "backend-architect", "backend-architect",
            "Deps RO-058 and RO-107 completed. Ready after encoders/space; not assigned this turn (critical path is RO-059/057)."))
        t["status"] = "ready"

# Assign RO-059 and RO-057
for tid, agent, note in [
    ("RO-059", "protocol-test-engineer",
     "Solo BR critical path: assign entity encoders after RO-056/058. Evidence-only opcodes from RO-056 framing; no invent."),
    ("RO-057", "game-compatibility-engineer",
     "Solo BR parallel research: map in-match C2S ids to unblock RO-060. Prefer over RO-074 this wave. Evidence only."),
]:
    t = by_id[tid]
    assert t["status"] == "ready", (tid, t["status"])
    t["history"].append(hist("cto", "ready", "assigned", agent, agent, note))
    t["status"] = "assigned"
    t["assigned_agent"] = agent
    t["updated_at"] = now

# Expand backend-architect paths for RO-110 files
for agent in team["agents"]:
    if agent["id"] == "backend-architect":
        for p in [
            "bigworld_gateway/server/battle/modules/**",
            "bigworld_gateway/server/battle/data/**",
            "tests/compatibility/gateway/solo_fill/**",
        ]:
            if p not in agent["allowed_paths"]:
                agent["allowed_paths"].append(p)
team_path.write_text(json.dumps(team, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

# Expand performance-engineer for RO-112 if needed - check
for agent in team["agents"]:
    if agent["id"] == "performance-engineer":
        for p in ["docs/performance/**", "reports/performance/**", "tests/performance/**"]:
            if p not in agent["allowed_paths"]:
                agent["allowed_paths"].append(p)
    if agent["id"] == "qa-engineer":
        for p in ["docs/testing/**", "docs/SOLO_GAMEPLAY_STATUS.md", "tests/compatibility/gateway/solo_first_playable/**"]:
            if p not in agent["allowed_paths"]:
                agent["allowed_paths"].append(p)

team_path.write_text(json.dumps(team, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

data["tasks"].extend(new_tasks)
data["updated_at"] = now
tasks_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("tasks", len(data["tasks"]))
print("RO-059", by_id["RO-059"]["status"])
print("RO-057", by_id["RO-057"]["status"])
print("RO-070", by_id["RO-070"]["status"])
print("new", [t["id"] for t in new_tasks])
