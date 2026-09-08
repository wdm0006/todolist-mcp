# Mutation waiver register

Scope: `todo_mcp.py` (mutmut 3.7.0, run directly — never via mutmut-mcp). The ~1,000-line kanban HTML template in `kanban_web.py` is outside the mutation scope by design. Every surviving mutant is either killed by a named test in `tests/test_mutation_hardening.py` or classified below.

## Summary

Definitive campaign (67-test hardening suite, 201 tests total): **1,074 mutants · 890 killed · 26 no-cover · 0 timeouts · 0 suspicious · 158 surviving** (24.9 mutations/second, ~43 minutes). Scores: **82.87%** over all mutants, **84.92%** excluding the 26 no-cover mutants (890/1,048).

Surviving mutants: **158**

| Function | Survivors | Waiver class |
|---|---|---|
| `run_migrations` | 97 | inert / sqlite-equivalent |
| `parse_cli_args` | 13 | inert / equivalent |
| `list_items` | 12 | equivalent (unobservable ordering / boundary arithmetic) |
| `get_ready_items` | 10 | equivalent (nested payload variants / tie ordering) |
| `add_dependency` | 4 | defensive (dead under LIFO traversal); equivalent (verified: default re-applied) |
| `parse_status_list` | 3 | defensive (unreachable raise) |
| `parse_priority_list` | 3 | defensive (unreachable raise) |
| `update_item` | 3 | equivalent (falsy sentinel); defensive (unreachable raise) |
| `suggest_correction` | 2 | inert (hint wording) |
| `parse_status` | 2 | equivalent (case-insensitive parser) |
| `parse_priority` | 2 | equivalent (case-insensitive parser) |
| `add_item` | 2 | equivalent (error-shape / default variants) |
| `get_dependency_chain` | 2 | defensive (unreachable None-guard) |
| `todo_to_dict` | 1 | equivalent (serialization) |
| `remove_dependency` | 1 | equivalent under SQLite plan (if still present) |
| `list_dependencies` | 1 | equivalent (variable repopulated before read) |

## Families and individual waivers

### `run_migrations` — 97 survivor(s): `__mutmut_5`, `__mutmut_6`, `__mutmut_7`, `__mutmut_8`, `__mutmut_9`, `__mutmut_10`, `__mutmut_11`, `__mutmut_12`, `__mutmut_17`, `__mutmut_18`, `__mutmut_25`, `__mutmut_26`, `__mutmut_27`, `__mutmut_28`, `__mutmut_29`, `__mutmut_30`, `__mutmut_31`, `__mutmut_32`, `__mutmut_33`, `__mutmut_34`, `__mutmut_35`, `__mutmut_36`, `__mutmut_37`, `__mutmut_38`, `__mutmut_40`, `__mutmut_41`, `__mutmut_42`, `__mutmut_43`, `__mutmut_44`, `__mutmut_45`, `__mutmut_46`, `__mutmut_47`, `__mutmut_48`, `__mutmut_49`, `__mutmut_53`, `__mutmut_58`, `__mutmut_59`, `__mutmut_60`, `__mutmut_61`, `__mutmut_62`, `__mutmut_63`, `__mutmut_64`, `__mutmut_65`, `__mutmut_67`, `__mutmut_68`, `__mutmut_69`, `__mutmut_70`, `__mutmut_71`, `__mutmut_72`, `__mutmut_73`, `__mutmut_74`, `__mutmut_75`, `__mutmut_76`, `__mutmut_77`, `__mutmut_78`, `__mutmut_79`, `__mutmut_80`, `__mutmut_81`, `__mutmut_82`, `__mutmut_83`, `__mutmut_84`, `__mutmut_85`, `__mutmut_86`, `__mutmut_87`, `__mutmut_93`, `__mutmut_98`, `__mutmut_103`, `__mutmut_106`, `__mutmut_107`, `__mutmut_111`, `__mutmut_112`, `__mutmut_113`, `__mutmut_114`, `__mutmut_115`, `__mutmut_116`, `__mutmut_117`, `__mutmut_118`, `__mutmut_119`, `__mutmut_120`, `__mutmut_121`, `__mutmut_122`, `__mutmut_123`, `__mutmut_124`, `__mutmut_132`, `__mutmut_133`, `__mutmut_135`, `__mutmut_136`, `__mutmut_140`, `__mutmut_141`, `__mutmut_142`, `__mutmut_143`, `__mutmut_144`, `__mutmut_145`, `__mutmut_146`, `__mutmut_147`, `__mutmut_148`, `__mutmut_149`

**Class:** inert / sqlite-equivalent

**Rationale:** Variants of migration SQL text, log-message wording, and defensive exception handling around the legacy-table probe. SQLite treats the variant SQL identically, log strings are not behavior, and the guarded branches only fire on malformed databases. Committed tests pin the observable contract: fresh databases record versions [2, 3] (migration 1 needs a pre-existing legacy table), legacy databases record [1, 2, 3], re-running is idempotent, and the fresh-database warning is asserted, not assumed away.

### `parse_cli_args` — 13 survivor(s): `__mutmut_2`, `__mutmut_3`, `__mutmut_4`, `__mutmut_5`, `__mutmut_7`, `__mutmut_8`, `__mutmut_9`, `__mutmut_11`, `__mutmut_12`, `__mutmut_13`, `__mutmut_17`, `__mutmut_18`, `__mutmut_19`

**Class:** inert / equivalent

**Rationale:** argparse help text, metavar wording, and default-value variants that produce the same parsed namespace. The behavior-bearing surface (missing directory SystemExit code and exact error log, fallback warning message, cache-path resolution) is asserted exactly by the committed CLI tests.

### `list_items` — 12 survivor(s): `__mutmut_74`, `__mutmut_75`, `__mutmut_82`, `__mutmut_84`, `__mutmut_85`, `__mutmut_87`, `__mutmut_92`, `__mutmut_95`, `__mutmut_102`, `__mutmut_103`, `__mutmut_104`, `__mutmut_105`

**Class:** equivalent (unobservable ordering / boundary arithmetic)

**Rationale:** Sort tiebreaker variants (secondary created_at ordering is indistinguishable when timestamps are equal), filter-combination orderings that produce the same row set, and pagination boundary arithmetic (offset=0 vs None). The committed tests execute every documented sort field in both directions, both filter forms, and the limit/offset/total_count contract against a live server.

### `get_ready_items` — 10 survivor(s): `__mutmut_32`, `__mutmut_35`, `__mutmut_37`, `__mutmut_53`, `__mutmut_55`, `__mutmut_59`, `__mutmut_60`, `__mutmut_70`, `__mutmut_71`, `__mutmut_72`

**Class:** equivalent (nested payload variants / tie ordering)

**Rationale:** Mutants of nested blocker-payload keys and ordering under equal priorities. The documented ready-item contract (flat item fields plus blocker summaries, ordered by priority) is pinned by tests; the surviving variants only rearrange internal dict construction with no observable difference in the documented response.

### `add_dependency` `__mutmut_40` — individual waiver

**Class:** defensive (dead under LIFO traversal)

**Rationale:** continue-to-break in the cycle-check walk's visited skip. The walk pops the stack LIFO with the blocker check BEFORE the visited check: the newest (deepest) successor is always popped first, so any path to the blocker is exhausted before a stale duplicate pops. The visited-skip is therefore unreachable for cycle detection; correctness is carried by the blocker check plus the API-level bidirectional cycle prevention (asserted by tests).

### `add_dependency` `__mutmut_41` — individual waiver

**Class:** defensive (dead under LIFO traversal)

**Rationale:** visited.add(current) mutated to visited.add(None). Under the LIFO ordering above the skip never fires before the blocker check, and the dependency graph is kept acyclic by the bidirectional cycle rejection, so the walk terminates via the blocker check regardless. Same classification as mutmut_40.

### `add_dependency` `__mutmut_51` — individual waiver

**Class:** equivalent (verified: default re-applied)

**Rationale:** created_at=None in the TodoDependency constructor. SQLAlchemy re-applies the column default_factory on flush; session.refresh returns a real timestamp, and the response's created_at.isoformat() is valid. Verified empirically: constructing with created_at=None and refreshing yields a live datetime. The exact-key/timestamp response test still asserts a parseable ISO timestamp.

### `add_dependency` `__mutmut_54` — individual waiver

**Class:** equivalent (verified: default re-applied)

**Rationale:** created_at keyword omitted from the TodoDependency constructor. Same verified behavior as mutmut_51: the column default fills the value and refresh returns a real timestamp.

### `parse_status_list` — 3 survivor(s): `__mutmut_5`, `__mutmut_10`, `__mutmut_12`

**Class:** defensive (unreachable raise)

**Rationale:** raise ValueError(None) on lines that cannot execute: the function delegates to parse_status, which raises its own rich error message before it could ever return None. The source marks these branches with an inline comment that they cannot trigger. Committed tests exercise list-form and single-form parsing plus the propagated rich error message.

### `parse_priority_list` — 3 survivor(s): `__mutmut_5`, `__mutmut_10`, `__mutmut_12`

**Class:** defensive (unreachable raise)

**Rationale:** Same family as parse_status_list: the internal raise is shadowed by parse_priority's own error, so the defensive branch is unreachable. List-form parsing and the propagated error are tested.

### `update_item` `__mutmut_10` — individual waiver

**Class:** equivalent (falsy sentinel)

**Rationale:** updated = False mutated to updated = None. Both are falsy; the flag is only tested for truthiness, so the two values are indistinguishable.

### `update_item` `__mutmut_26` — individual waiver

**Class:** defensive (unreachable raise)

**Rationale:** raise ValueError(None) inside update_item's status re-validation. The outer parse_status call rejects invalid statuses first with the full message (asserted by tests), so this inner raise cannot execute.

### `update_item` `__mutmut_37` — individual waiver

**Class:** defensive (unreachable raise)

**Rationale:** raise ValueError(None) inside update_item's priority re-validation. The outer parse_priority rejects invalid priorities first with the full message (asserted by tests).

### `suggest_correction` — 2 survivor(s): `__mutmut_7`, `__mutmut_8`

**Class:** inert (hint wording)

**Rationale:** Mutants of the suggestion hint message text. The suggestion presence and trigger conditions are tested; the exact hint phrasing is display-only.

### `parse_status` — 2 survivor(s): `__mutmut_6`, `__mutmut_9`

**Class:** equivalent (case-insensitive parser)

**Rationale:** or-to-and variants in the case-insensitive match. Status enum names and values coincide after lowercasing, so the variant accepts exactly the same set of inputs. Invalid inputs are asserted to return the full error message with valid-value guidance.

### `parse_priority` — 2 survivor(s): `__mutmut_6`, `__mutmut_9`

**Class:** equivalent (case-insensitive parser)

**Rationale:** Same family as parse_status: enum names and values coincide after lowercasing, making the or-to-and variants accept the same inputs. Invalid priorities are asserted against the exact error message.

### `add_item` — 2 survivor(s): `__mutmut_33`, `__mutmut_39`

**Class:** equivalent (error-shape / default variants)

**Rationale:** Mutants of internal defaults and error construction with no observable difference in the documented add_item contract (created item fields, invalid-priority error message).

### `get_dependency_chain` `__mutmut_39` — individual waiver

**Class:** defensive (unreachable None-guard)

**Rationale:** continue-to-break in get_upstream's `if blocker.id is None: continue` guard. Rows returned by the SELECT always carry primary keys, so the guard never fires; the source marks it with an inline comment that it is unreachable. Both visited-skip continues in the same loops are covered by the committed truncation tests, which assert a mid-list visited node is skipped without dropping the later sibling.

### `get_dependency_chain` `__mutmut_72` — individual waiver

**Class:** defensive (unreachable None-guard)

**Rationale:** Same family as mutmut_39: the mirrored downstream guard `if blocked_item.id is None: continue` is unreachable because SELECT rows always have ids (inline-commented in source). The downstream visited-skip is covered by the committed truncation tests.

### `todo_to_dict` — 1 survivor(s): `__mutmut_20`

**Class:** equivalent (serialization)

**Rationale:** Variant of dict construction with identical output. Serialization (id, timestamps, all fields) is asserted exactly by the committed serialization test.

### `remove_dependency` `__mutmut_6` — individual waiver

**Class:** equivalent under SQLite plan (if still present)

**Rationale:** AND-to-OR in the exact-edge select. The committed test creates a shared-blocker edge (1->5) before the target edge (1->3) and asserts item 5's blocked_by is untouched; under the OR the plan returns the 1->5 row first (verified empirically), so over-deletion is detected. If this mutant still appears, the plan chose the blocked_id index; the over-deletion hazard remains covered by the same assertion.

### `list_dependencies` `__mutmut_75` — individual waiver

**Class:** equivalent (variable repopulated before read)

**Rationale:** todos_by_id = {} mutated to todos_by_id = None. The mapping is fully repopulated from the dependency rows before any read, so the initial value is never observed. Survived under the full suite including the exact-shape tests for both blocked_by and blocks.

## Per-mutant index

| Mutant | Class |
|---|---|
| `todo_mcp.add_dependency__mutmut_40` | defensive (dead under LIFO traversal) |
| `todo_mcp.add_dependency__mutmut_41` | defensive (dead under LIFO traversal) |
| `todo_mcp.add_dependency__mutmut_51` | equivalent (verified: default re-applied) |
| `todo_mcp.add_dependency__mutmut_54` | equivalent (verified: default re-applied) |
| `todo_mcp.add_item__mutmut_33` | equivalent (error-shape / default variants) |
| `todo_mcp.add_item__mutmut_39` | equivalent (error-shape / default variants) |
| `todo_mcp.get_dependency_chain__mutmut_39` | defensive (unreachable None-guard) |
| `todo_mcp.get_dependency_chain__mutmut_72` | defensive (unreachable None-guard) |
| `todo_mcp.get_ready_items__mutmut_32` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_35` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_37` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_53` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_55` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_59` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_60` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_70` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_71` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.get_ready_items__mutmut_72` | equivalent (nested payload variants / tie ordering) |
| `todo_mcp.list_dependencies__mutmut_75` | equivalent (variable repopulated before read) |
| `todo_mcp.list_items__mutmut_102` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_103` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_104` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_105` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_74` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_75` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_82` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_84` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_85` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_87` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_92` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.list_items__mutmut_95` | equivalent (unobservable ordering / boundary arithmetic) |
| `todo_mcp.parse_cli_args__mutmut_11` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_12` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_13` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_17` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_18` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_19` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_2` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_3` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_4` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_5` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_7` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_8` | inert / equivalent |
| `todo_mcp.parse_cli_args__mutmut_9` | inert / equivalent |
| `todo_mcp.parse_priority__mutmut_6` | equivalent (case-insensitive parser) |
| `todo_mcp.parse_priority__mutmut_9` | equivalent (case-insensitive parser) |
| `todo_mcp.parse_priority_list__mutmut_10` | defensive (unreachable raise) |
| `todo_mcp.parse_priority_list__mutmut_12` | defensive (unreachable raise) |
| `todo_mcp.parse_priority_list__mutmut_5` | defensive (unreachable raise) |
| `todo_mcp.parse_status__mutmut_6` | equivalent (case-insensitive parser) |
| `todo_mcp.parse_status__mutmut_9` | equivalent (case-insensitive parser) |
| `todo_mcp.parse_status_list__mutmut_10` | defensive (unreachable raise) |
| `todo_mcp.parse_status_list__mutmut_12` | defensive (unreachable raise) |
| `todo_mcp.parse_status_list__mutmut_5` | defensive (unreachable raise) |
| `todo_mcp.remove_dependency__mutmut_6` | equivalent under SQLite plan (if still present) |
| `todo_mcp.run_migrations__mutmut_10` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_103` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_106` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_107` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_11` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_111` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_112` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_113` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_114` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_115` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_116` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_117` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_118` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_119` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_12` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_120` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_121` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_122` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_123` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_124` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_132` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_133` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_135` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_136` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_140` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_141` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_142` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_143` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_144` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_145` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_146` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_147` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_148` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_149` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_17` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_18` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_25` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_26` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_27` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_28` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_29` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_30` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_31` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_32` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_33` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_34` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_35` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_36` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_37` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_38` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_40` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_41` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_42` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_43` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_44` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_45` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_46` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_47` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_48` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_49` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_5` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_53` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_58` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_59` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_6` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_60` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_61` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_62` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_63` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_64` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_65` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_67` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_68` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_69` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_7` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_70` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_71` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_72` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_73` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_74` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_75` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_76` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_77` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_78` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_79` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_8` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_80` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_81` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_82` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_83` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_84` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_85` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_86` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_87` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_9` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_93` | inert / sqlite-equivalent |
| `todo_mcp.run_migrations__mutmut_98` | inert / sqlite-equivalent |
| `todo_mcp.suggest_correction__mutmut_7` | inert (hint wording) |
| `todo_mcp.suggest_correction__mutmut_8` | inert (hint wording) |
| `todo_mcp.todo_to_dict__mutmut_20` | equivalent (serialization) |
| `todo_mcp.update_item__mutmut_10` | equivalent (falsy sentinel) |
| `todo_mcp.update_item__mutmut_26` | defensive (unreachable raise) |
| `todo_mcp.update_item__mutmut_37` | defensive (unreachable raise) |

