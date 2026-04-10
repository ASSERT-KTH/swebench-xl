# SWEBench XL Results

---

## 1. Overall Leaderboard — Top 5

| Rank | Label                                  | Agent               | Model           | Resolved | Total | Resolve % | Run ID      |
| ---: | -------------------------------------- | ------------------- | --------------- | -------: | ----: | --------: | ----------- |
|    1 | codex-cli / gpt-5.4 (xhigh reasoning)  | codex-cli           | gpt-5.4         |       29 |    58 |     50.0% | 24193212763 |
|    2 | github-copilot-cli / claude-opus-4-6   | github-copilot-cli  | claude-opus-4-6 |       27 |    58 |     46.6% | 24144127982 |
|    3 | openhands / claude-opus-4.6    | openhands   | claude-opus-4.6 |       26 |    58 |     44.8% | 24141934642 |
|    4 | claude-code / claude-opus-4.6  | claude-code | claude-opus-4.6 |       25 |    58 |     43.1% | 24146746219 |
|    5 | codex-cli / gpt-5.4 (medium reasoning) | codex-cli           | gpt-5.4         |       25 |    58 |     43.1% | 24143351653 |

### Top 5 Instance Coverage

Instances resolved by all/any of the top 5 runs.

| Metric                               | Count | Instances                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| ------------------------------------ | ----: | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Resolved by ALL top 5 (intersection) |    14 | `elastic__elasticsearch-140594`, `elastic__elasticsearch-141479`, `elastic__elasticsearch-141519`, `elastic__elasticsearch-142330`, `elastic__elasticsearch-142752`, `elastic__elasticsearch-142763`, `elastic__elasticsearch-143155`, `elastic__elasticsearch-143241`, `elastic__elasticsearch-143463`, `elastic__elasticsearch-143668`, `elastic__elasticsearch-143938`, `elastic__elasticsearch-144029`, `elastic__elasticsearch-144031`, `elastic__elasticsearch-144545` |
| Resolved by ANY top 5 (union)        |    37 | 37 instances                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Resolved ONLY outside top 5          |     6 | `elastic__elasticsearch-135899`, `elastic__elasticsearch-140394`, `elastic__elasticsearch-141815`, `elastic__elasticsearch-142117`, `elastic__elasticsearch-142386`, `elastic__elasticsearch-142401`                                                                                                                                                                                                                                                                         |

### Full Ranking

| Rank | Label                                  | Agent               | Model             | Resolved | Total | Resolve % | Run ID      |
| ---: | -------------------------------------- | ------------------- | ----------------- | -------: | ----: | --------: | ----------- |
|    1 | codex-cli / gpt-5.4 (xhigh reasoning)  | codex-cli           | gpt-5.4           |       29 |    58 |     50.0% | 24193212763 |
|    2 | github-copilot-cli / claude-opus-4-6   | github-copilot-cli  | claude-opus-4-6   |       27 |    58 |     46.6% | 24144127982 |
|    3 | openhands / claude-opus-4.6    | openhands   | claude-opus-4.6   |       26 |    58 |     44.8% | 24141934642 |
|    4 | claude-code / claude-opus-4.6  | claude-code | claude-opus-4.6   |       25 |    58 |     43.1% | 24146746219 |
|    5 | codex-cli / gpt-5.4 (medium reasoning) | codex-cli           | gpt-5.4           |       25 |    58 |     43.1% | 24143351653 |
|    6 | codex-cli / gpt-5.4 (high reasoning)   | codex-cli           | gpt-5.4           |       25 |    58 |     43.1% | 24144731080 |
|    7 | codex-cli / gpt-5.4-mini               | codex-cli           | gpt-5.4-mini      |       22 |    58 |     37.9% | 24129026792 |
|    8 | codex-cli / gpt-5.1                    | codex-cli           | gpt-5.1           |       22 |    58 |     37.9% | 24142889596 |
|    9 | openhands / gpt-5.4            | openhands   | gpt-5.4           |       19 |    58 |     32.8% | 24128725716 |
|   10 | openhands / claude-sonnet-4.5  | openhands   | claude-sonnet-4.5 |       18 |    58 |     31.0% | 24135852586 |
|   11 | github-copilot-cli / claude-sonnet-4-5 | github-copilot-cli  | claude-sonnet-4-5 |       18 |    58 |     31.0% | 24145530082 |
|   12 | github-copilot-cli / gpt-5-4           | github-copilot-cli  | gpt-5-4           |       18 |    58 |     31.0% | 24145570447 |
|   13 | github-copilot-cli / gpt-5-4-mini      | github-copilot-cli  | gpt-5-4-mini      |       16 |    58 |     27.6% | 24145607593 |
|   14 | codex-cli / gpt-5-mini                 | codex-cli           | gpt-5-mini        |       11 |    58 |     19.0% | 24142966094 |
|   15 | openhands / gpt-5.1            | openhands   | gpt-5.1           |        8 |    58 |     13.8% | 24142623293 |
|   16 | openhands / gpt-4              | openhands   | gpt-4             |        7 |    58 |     12.1% | 24142288830 |

### Discussion

The top of the leaderboard is tight: the best 4 runs span only ~7 percentage points (43–50%), and all use frontier-tier models (gpt-5.4 or claude-opus-4.6). The clear outlier is Codex CLI with xhigh reasoning at 50%, suggesting that extended thinking at inference time yields a meaningful but not dramatic gain over high/medium reasoning on this benchmark. The agent framework matters too, the same claude-opus-4.6 model scores 46.6% under github-copilot-cli but 44.8% under openhands and 43.1% under claude-code, pointing to non-trivial scaffolding effects. The tail of the ranking drops sharply: gpt-4 and gpt-5.1 under OpenHands resolve only 12–14%, suggesting that weaker models cannot compensate for the codebase's complexity even with a capable agent scaffold.

---

## 2. Per-Agent Model Leaderboard

Runs grouped by agent, ranked by resolve rate within each group.

### Agent: `codex-cli`

| Rank | Model        | Label                                  | Resolved | Total | Resolve % | Run ID      |
| ---: | ------------ | -------------------------------------- | -------: | ----: | --------: | ----------- |
|    1 | gpt-5.4      | codex-cli / gpt-5.4 (xhigh reasoning)  |       29 |    58 |     50.0% | 24193212763 |
|    2 | gpt-5.4      | codex-cli / gpt-5.4 (medium reasoning) |       25 |    58 |     43.1% | 24143351653 |
|    3 | gpt-5.4      | codex-cli / gpt-5.4 (high reasoning)   |       25 |    58 |     43.1% | 24144731080 |
|    4 | gpt-5.4-mini | codex-cli / gpt-5.4-mini               |       22 |    58 |     37.9% | 24129026792 |
|    5 | gpt-5.1      | codex-cli / gpt-5.1                    |       22 |    58 |     37.9% | 24142889596 |
|    6 | gpt-5-mini   | codex-cli / gpt-5-mini                 |       11 |    58 |     19.0% | 24142966094 |

### Agent: `github-copilot-cli`

| Rank | Model             | Label                                  | Resolved | Total | Resolve % | Run ID      |
| ---: | ----------------- | -------------------------------------- | -------: | ----: | --------: | ----------- |
|    1 | claude-opus-4-6   | github-copilot-cli / claude-opus-4-6   |       27 |    58 |     46.6% | 24144127982 |
|    2 | claude-sonnet-4-5 | github-copilot-cli / claude-sonnet-4-5 |       18 |    58 |     31.0% | 24145530082 |
|    3 | gpt-5-4           | github-copilot-cli / gpt-5-4           |       18 |    58 |     31.0% | 24145570447 |
|    4 | gpt-5-4-mini      | github-copilot-cli / gpt-5-4-mini      |       16 |    58 |     27.6% | 24145607593 |

### Agent: `claude-code`

| Rank | Model           | Label                                 | Resolved | Total | Resolve % | Run ID      |
| ---: | --------------- | ------------------------------------- | -------: | ----: | --------: | ----------- |
|    1 | claude-opus-4.6 | claude-code / claude-opus-4.6 |       25 |    58 |     43.1% | 24146746219 |

### Agent: `openhands`

| Rank | Model             | Label                                 | Resolved | Total | Resolve % | Run ID      |
| ---: | ----------------- | ------------------------------------- | -------: | ----: | --------: | ----------- |
|    1 | claude-opus-4.6   | openhands / claude-opus-4.6   |       26 |    58 |     44.8% | 24141934642 |
|    2 | gpt-5.4           | openhands / gpt-5.4           |       19 |    58 |     32.8% | 24128725716 |
|    3 | claude-sonnet-4.5 | openhands / claude-sonnet-4.5 |       18 |    58 |     31.0% | 24135852586 |
|    4 | gpt-5.1           | openhands / gpt-5.1           |        8 |    58 |     13.8% | 24142623293 |
|    5 | gpt-4             | openhands / gpt-4             |        7 |    58 |     12.1% | 24142288830 |

### Discussion

Within Codex CLI, xhigh reasoning outperforms medium and high reasoning by 4 instances despite using the same model, with medium and high being effectively tied. This suggests diminishing returns between reasoning levels, with a meaningful jump only at the extreme end. Within github-copilot-cli, claude-opus-4-6 is far ahead of the next tier (46.6% vs 31%), and sonnet-4-5 and gpt-5-4 score identically, implying the agent framework is a performance bottleneck that equalizes mid-tier models. The same pattern appears in openhands: claude-opus-4.6 leads at 44.8% but gpt-5.4 drops to 32.8% despite being a strong model, suggesting OpenHands extracts less performance from GPT models than from Claude models relative to the Codex CLI agent.

---

## 3. Per-Instance Resolve Analysis

### Summary

| Metric                              | Count | % of Total |
| ----------------------------------- | ----: | ---------: |
| Total instances                     |    58 |     100.0% |
| Resolved by ALL runs (intersection) |     1 |       1.7% |
| Resolved by ANY run (union)         |    43 |      74.1% |
| Never resolved by any run           |    15 |      25.9% |

### Always Resolved (by ALL runs)

- `elastic__elasticsearch-141519`

### Never Resolved (by ANY run)

- `elastic__elasticsearch-139873`
- `elastic__elasticsearch-140094`
- `elastic__elasticsearch-141196`
- `elastic__elasticsearch-141371`
- `elastic__elasticsearch-141523`
- `elastic__elasticsearch-141592`
- `elastic__elasticsearch-141619`
- `elastic__elasticsearch-141811`
- `elastic__elasticsearch-141973`
- `elastic__elasticsearch-142450`
- `elastic__elasticsearch-142937`
- `elastic__elasticsearch-143249`
- `elastic__elasticsearch-143408`
- `elastic__elasticsearch-143810`
- `elastic__elasticsearch-144388`

### Uniquely Resolved (only by that run)

**codex-cli / gpt-5.4 (xhigh reasoning)** (`24193212763`): 3 unique
  - `elastic__elasticsearch-141482`
  - `elastic__elasticsearch-143533`
  - `elastic__elasticsearch-144040`

**github-copilot-cli / claude-opus-4-6** (`24144127982`): 1 unique
  - `elastic__elasticsearch-140217`

**codex-cli / gpt-5.1** (`24142889596`): 3 unique
  - `elastic__elasticsearch-140394`
  - `elastic__elasticsearch-142117`
  - `elastic__elasticsearch-142401`

**github-copilot-cli / gpt-5-4-mini** (`24145607593`): 1 unique
  - `elastic__elasticsearch-135899`

### Discussion

The theoretical ceiling of 74.1% indicates that roughly a quarter of the benchmark is currently unsolvable by any tested agent, representing a hard difficulty floor in the benchmark. Only 1 instance was solved by every single run, confirming that most tasks require specific model or scaffolding capabilities rather than being universally accessible. The uniquely resolved instances are particularly interesting: codex-cli/gpt-5.1 accounts for 3 unique solves on tasks that are structurally atypical (feature additions with explicit hints — see Section 3a), while codex-cli/gpt-5.4 xhigh uniquely solves 3 tasks that apparently require very deep reasoning. Two of the 4 uniquely solved runs are from weaker models (gpt-5.1, gpt-5-4-mini), which is counterintuitive and examined further in Section 3b.

---

### 3a. Never-Resolved Tasks — Analysis

Out of 58 total tasks, **15 tasks (26%) were never resolved by any agent**. The table below summarizes their properties.

| Task   | Subsystem     | Lines ±   | P2P Tests | Description                                                         |
| ------ | ------------- | --------- | --------- | ------------------------------------------------------------------- |
| 139873 | ES\|QL/PromQL | +518/−422 | 22        | Add parameter support in PromQL bracket durations (ANTLR grammar)   |
| 140094 | Vectors       | +304/−12  | 17        | Add base64 output format for dense_vector fields                    |
| 141196 | ES\|QL        | +10/−2    | 8         | Fix bucket() crash on renamed @timestamp in TS command              |
| 141371 | ES\|QL        | +24/−2    | 243       | Fix infinite analyzer loop for subquery on empty-mapping index      |
| 141523 | ES\|QL        | +104/−14  | 134       | Fix FUSE unbounded input validation with subqueries                 |
| 141592 | ES\|QL        | +26/−4    | 380       | Improve FUSE error messages for missing columns                     |
| 141619 | ES\|QL        | +95/−0    | 249       | Sort TS output by @timestamp DESC when no explicit SORT             |
| 141811 | Search        | +24/−1    | 1         | Return proper error for malformed PIT ID instead of 500             |
| 141973 | Search        | +9/−0     | 10        | Fix NPE when collapse field name is null                            |
| 142450 | Transform     | +16/−3    | 24        | Fix transforms producing empty index when query uses runtime fields |
| 142937 | GPU           | +19/−4    | 7         | Fix GPU stats serialization failure (negative long via writeVLong)  |
| 143249 | ES\|QL        | +225/−18  | 142       | Fix multi_match crash after MV_EXPAND on lookup index               |
| 143408 | SQL           | +19/−2    | 13        | Fix SQL client parsing of array-valued HTTP headers                 |
| 143810 | ES\|QL        | +28/−1    | 41        | Disallow full-text search with unmapped_fields="load"               |
| 144388 | ES\|QL        | +93/−6    | 156       | Handle NULL data type in CHANGE_POINT gracefully                    |

**Root causes for zero-resolve rate:**

The dominant pattern is that 10 of 15 tasks (67%) involve ES|QL, Elasticsearch's proprietary pipe-based query language. ES|QL has a multi-stage compilation pipeline (Parser → Analyzer → Verifier → Optimizer → Planner → Executor) where the fix location frequently differs from the error location. For example, a runtime crash in the Executor often requires a guard clause in the Verifier; an infinite loop in `Analyzer$ResolveRefs` is fixed by patching `Analyzer.resolveFork()` in a different method. Agents following stacktraces end up in the wrong place. Six tasks carry 100–380 pass-2-pass regression tests, meaning even a small overfitting of the fix (e.g., an overly broad condition in `Analyzer.java`) silently breaks dozens of existing tests. One task (139873) requires modifying ANTLR `.g4` grammar files and then updating 9 generated files that cannot be regenerated without the ANTLR toolchain — effectively impossible in an agentic setting. The remaining non-ES|QL failures (141811, 141973, 142450, 142937, 143408) each have their own localization challenge: the fix location is not the symptom location, and no issue description gives directional guidance.

---

### 3b. Tasks Uniquely Solved by Simpler Models — Analysis

Four tasks are solved **only** by lower-ranked runs where top-tier models fail.

| Task   | Type             | Subsystem    | Patch Size | FTP | PTP | Guidance Type              |
| ------ | ---------------- | ------------ | ---------- | :-: | :-: | -------------------------- |
| 135899 | bug_fix          | Search       | +169/−1    |  1  | 22  | Code link to exact line    |
| 140394 | feature_addition | Repositories | +113/−88   |  1  | 25  | Hint: class name           |
| 142117 | bug_fix          | ES\|QL       | +286/−28   |  8  | 52  | "Refer to X as an example" |
| 142401 | feature_addition | ES\|QL       | +47/−9     |  2  | 15  | Hint: method signatures    |

These are the only 4 tasks in the benchmark that provide explicit directional guidance: two name exact symbols to implement, one links to the precise file and line number, and one names a reference implementation to copy. All other 54 tasks describe what is broken without saying where or how to fix it.

The consequence is that these become "recipe tasks", mechanical pattern replication rather than exploratory debugging. Simpler models appear to follow such recipes more faithfully, while frontier models are more likely to reason from first principles, attempt a more general solution than the test suite expects, or over-explore the codebase and exhaust their context before converging. The regression test count supports this: these 4 tasks average only 28.5 PTP tests vs 135.1 for the rest of the benchmark, so a slightly imprecise but directionally correct solution can still pass.

---

## 4. Read/Write File Recall/Precision

### Copilot CLI - GPT 5.4

| Split      |   N | Read Recall | Read Precision | Write Recall | Write Precision |
| ---------- | --: | :---------: | :------------: | :----------: | :-------------: |
| Overall    |  58 |    0.91     |      0.11      |     0.77     |      0.38       |
| Resolved   |  18 |    0.96     |      0.10      |     0.92     |      0.41       |
| Unresolved |  40 |    0.88     |      0.12      |     0.71     |      0.37       |

### Copilot CLI - Opus 4.6

| Split      |   N | Read Recall | Read Precision | Write Recall | Write Precision |
| ---------- | --: | :---------: | :------------: | :----------: | :-------------: |
| Overall    |  58 |    0.88     |      0.12      |     0.63     |      0.37       |
| Resolved   |  27 |    0.96     |      0.14      |     0.84     |      0.48       |
| Unresolved |  31 |    0.82     |      0.10      |     0.45     |      0.27       |

### Codex CLI - GPT 5.4

| Split      |   N | Read Recall | Read Precision | Write Recall | Write Precision |
| ---------- | --: | :---------: | :------------: | :----------: | :-------------: |
| Overall    |  58 |    0.85     |      0.11      |     0.73     |      0.37       |
| Resolved   |  24 |    0.97     |      0.11      |     0.90     |      0.40       |
| Unresolved |  34 |    0.76     |      0.11      |     0.62     |      0.35       |

### Claude Code - Opus 4.6

| Split      |   N | Read Recall | Read Precision | Write Recall | Write Precision |
| ---------- | --: | :---------: | :------------: | :----------: | :-------------: |
| Overall    |  57 |    0.87     |      0.13      |     0.71     |      0.38       |
| Resolved   |  25 |    0.98     |      0.14      |     0.93     |      0.45       |
| Unresolved |  32 |    0.78     |      0.11      |     0.54     |      0.33       |

### Codex CLI - GPT 5.4 - XHigh Reasoning

| Split      |   N | Read Recall | Read Precision | Write Recall | Write Precision |
| ---------- | --: | :---------: | :------------: | :----------: | :-------------: |
| Overall    |  58 |    0.94     |      0.08      |     0.78     |      0.37       |
| Resolved   |  29 |    0.98     |      0.08      |     0.92     |      0.39       |
| Unresolved |  29 |    0.91     |      0.09      |     0.65     |      0.35       |

### Codex CLI - GPT 5.4 Mini

| Split      |   N | Read Recall | Read Precision | Write Recall | Write Precision |
| ---------- | --: | :---------: | :------------: | :----------: | :-------------: |
| Overall    |  58 |    0.83     |      0.11      |     0.64     |      0.37       |
| Resolved   |  22 |    0.93     |      0.13      |     0.88     |      0.45       |
| Unresolved |  36 |    0.78     |      0.10      |     0.50     |      0.32       |

### Discussion

Read recall is consistently high across all agents (0.83–0.94 overall), indicating that agents generally find the relevant files. Read precision is uniformly low (~0.08–0.13), meaning agents read many irrelevant files, this is expected given the scale of the codebase and is not a bottleneck on its own. The more informative signal is write recall and its gap between resolved and unresolved splits. For Opus 4.6 under Copilot CLI, write recall drops from 0.84 on resolved instances to 0.45 on unresolved, a 39-point gap, the largest among all agents. This suggests that for unresolved tasks, the agent identifies the symptom but fails to propagate changes to all necessary files (incomplete write coverage). Codex CLI xhigh shows a similar pattern (0.92 → 0.65) but with a higher floor. Write precision is fairly flat across resolved/unresolved splits for most agents (~0.35–0.45), meaning the files agents do write to are roughly as targeted regardless of outcome, the failure mode is more about missing files than writing to wrong ones. The agent often write to more files than in the gold patch as it writes to existing or create new test files very often.

---

## 5. Hand-Holding Runs

The agent received the following appended to each problem statement:

```
## Source Files to Edit

The following source files are relevant to this task and should be the focus of your changes:
- path/to/file1
- path/to/file2
  .
  .
  . 
```

| Agent     | Model    | Resolve Rate | Resolve Rate Before Hints |
| --------- | -------- | ------------ | ------------------------- |
| Codex CLI | GPT 5.4  | 52%          | 41%                       |
| OpenHands | GPT 5.4  | 36%          | 33%                       |
| OpenHands | Opus 4.6 | 31%          | 45%                       |

### Discussion

The detail that stands out is that Codex CLI + GPT 5.4 benefits from the hints while OpenHands + Opus 4.6 suffers from them. Codex CLI gains 11 percentage points, consistent with the read/write analysis showing that file navigation is a real bottleneck, eliminating it unlocks meaningful performance. OpenHands + GPT 5.4 sees a modest 3-point gain, suggesting the scaffolding makes less effective use of the hints. Most surprising, OpenHands + Opus 4.6 drops 14 points with hints, from 45% to 31%. A plausible explanation is that Opus 4.6 under OpenHands relies on exploratory reasoning to build context about the codebase before committing to changes; injecting file paths short-circuits that exploration, causing the agent to converge on an incomplete solution without the broader context it would otherwise acquire. This interaction effect suggests that hint utility is agent-architecture-dependent, not just model-dependent.

---

## 6. Synthetic Issue Descriptions

**WIP**

My hypothesis is that some instances are hard due to the issue description being vague in respect to the tests. Looking at the never resolved instances as well, a common factor seems to be the error location not being the same as the fix location. If the issue is synthesised partly based on the patch diff, it might be clearer. 