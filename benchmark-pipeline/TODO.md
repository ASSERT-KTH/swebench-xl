# Benchmark Pipeline — TODOs

## Widen compilation error detection in instance_detector

**Status:** Pending  
**Files:** `gradle_runner.py`, `instance_detector.py`

### Problem

`extract_missing_methods()` in `gradle_runner.py` only matches `"cannot find symbol"` errors
where the symbol is a **method** (regex: `method\s+(\w+)\s*\(([^)]*)\)`). This misses
legitimate feature additions where the test references a new class, constant, enum value,
field, or constructor. All of these currently produce **"Compilation failed for unknown
reasons"** and the instance is skipped.

### What needs to change

1. **`gradle_runner.py` — `parse_compile_errors()` + `extract_missing_methods()`**
   - Also extract missing classes (`symbol: "class NewProcessor"`)
   - Also extract missing variables/fields (`symbol: "variable NEW_CONSTANT"`)
   - Also extract missing constructors
   - Consider renaming to `extract_missing_symbols()` since it's broader than methods

2. **`gradle_runner.py` — `run_gradle()` line ~121**
   - Only keeps last 80 lines of output — `"cannot find symbol"` errors with their
     `symbol:` / `location:` context lines are often early in the output and get truncated
   - Either increase the limit or specifically preserve error lines

3. **`instance_detector.py` line ~86**
   - Further truncates `compile_output` to last 3000 chars
   - Should preserve full output for error parsing; only truncate for storage

4. **`instance_detector.py` — `format_method_signatures()`**
   - Needs updating to handle broader symbol types (classes, fields, etc.) in
     `instruction.md` hints
