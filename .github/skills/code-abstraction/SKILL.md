---
name: code-abstraction
description: Use this skill, when user requests abstraction of codebase or a prompt requires large changes/additions. This skill guides structural decisions whether code already exists or is being designed from scratch.
---

***Important:*** This is a *planning* skill, not an implementation one. The output should be a detailed instruction set for the coder agent to execute, not the code itself.

**Key Insight:** Proper abstraction is one which has clear justification and minimal interfaces. Avoid fragmenting code into too many small pieces without a clear reuse case.

**Key Pitfall:** Over-abstracting leads to tangled dependencies, circular imports, and a codebase that's hard to navigate. Under-abstracting leads to duplicated logic, tight coupling, and harder maintenance.

**This skill should be applied iteratively.** As the codebase evolves, revisit abstraction decisions to ensure they still hold true against the 4 triggers and guardrails.

**If in doubt: code is small, prefer a direct implementation. code is large, ask user** Only abstract when one of the 4 triggers is clearly met and the guardrails can be followed.

## 1. When to Use / When Not to Use

### When to Use
Apply this skill when the planning context (prompt request or existing codebase analysis) reveals at least one of these 4 triggers:
1. **Cross-Module Utility:** The logic is needed (or will be needed) by multiple independent domains or modules.
2. **Isolated Functionality:** A specific code block performs a single, self-contained task, has no external dependencies, and can be cleanly separated from the primary control flow.
3. **Minimal Interface Exposure:** The underlying mechanics are complex or highly detailed, but the behavior can be managed via a very small, simple set of inputs and outputs (Information Hiding).
4. **Clear Boundary Line:** A natural physical or logical barrier exists—specifically when separating pure business logic from I/O side-effects (e.g., database persistence, third-party network APIs).

### When NOT to Use
* **Speculative Design:** The logic *might* be reused in the future, but currently has only one caller or one distinct use case.
* **Leaky Complexity:** Abstracting a block requires passing an excessive number of contextual arguments or exposing internal module states to the caller.
* **High-Churn Business Logic:** The rules are changing rapidly; abstracting too early will lock the system into a rigid, hard-to-modify structure.

---

## 2. Decision Flowchart (Quick Check)

```
START: Should we abstract this code?
  │
  ├─→ Does it match ANY of the 4 triggers? → NO → STOP. Keep code inline.
  │   (See "When to Use" section above)
  │
  └─→ YES → Check for pitfalls:
      │
      ├─→ Is it speculative (might reuse, but only 1 caller today)? → YES → STOP. Wait.
      │
      ├─→ Does abstraction require excessive args or leak internal state? → YES → STOP. Simplify first.
      │
      ├─→ Is business logic high-churn (rules change rapidly)? → YES → STOP. Let it stabilize.
      │
      └─→ NO pitfalls detected → PROCEED to Planning Workflow below.
```

---

## 3. Planning Workflow (Step-by-Step)

* **Step 1: Context & Dependency Check**
  * *If code exists:* Map the existing dependency tree. Ensure the new abstraction will not introduce circular imports.
  * *If greenfield:* Layout the module hierarchy on paper first, moving from lowest dependency (pure utilities) to highest (orchestration layers).
* **Step 2: Define the Interface Contract**
  * Explicitly declare the function signatures, required data structures (`dataclasses`, types), and expected exceptions of the boundary line *before* drafting any implementation steps.
* **Step 3: Enforce State Isolation**
  * Ensure abstracted components are stateless (prefer pure functions or immutable structures) to prevent hidden side-effects across domains.
* **Step 4: Establish Dependency Direction**
  * Enforce a strict one-way dependency flow. Higher-level domain modules import lower-level abstractions; lower-level abstractions must never import higher-level callers.

---

## 3. Guardrails

* **The Rule of Avoidance:** Do not centralize code into a shared module unless it serves 3+ distinct callers, OR it strictly matches **Trigger 4 (Clear Boundary Line)**.
* **API Stability:** When refactoring existing code, public-facing APIs must remain unchanged. Wrap the new abstraction in a Facade or Adapter pattern to maintain absolute backward compatibility.
* **No "Utils" Dumping Grounds:** Do not create or plan a generic `utils.py` file. Every abstraction must live in a explicitly named, cohesive domain module (e.g., `crypto.py`, `validators.py`, `formatting.py`).

---

## 4. Expected Output

The output of this planning phase must be a structured instruction set for the implementation engine/coder agent containing:

1. **The Objective:** Which of the 4 triggers is being addressed and the technical justification.
2. **The File Target:** The exact file path and placement of the new abstraction within the codebase hierarchy.
3. **The Interface Contract:** The precise public API surface (method names, input parameters, type hints, and return structures).
4. **The Impact Radius:** A list of existing files, modules, or call-sites that must be updated to consume the new interface.

---

## 5. Examples

### Example 1: Trigger 4 (Clear Boundary Line) — Greenfield Planning
* **Context:** A prompt requests a new feature that calculates customer loyalty discounts and saves the transaction receipt to a database.
* **Plan:** Isolate the calculation from the database I/O entirely.
  * *Abstraction:* Create a pure `loyalty_engine.py` module.
  * *Contract:* `calculate_discount(profile: CustomerProfile, cart: ShoppingCart) -> DiscountResult`
  * *Boundary:* The orchestration layer calls this engine to get the result, then hands the result to the database repository. The engine itself remains 100% blind to the database.

### Example 2: Trigger 1 & 3 (Cross-Module + Minimal Interface) — Existing Code Refactor
* **Context:** Both the `billing` module and the `shipping` module contain duplicate, highly complex regex patterns and string manipulation to validate international phone numbers.
* **Plan:** Centralize and hide the validation complexity.
  * *Abstraction:* Extract the logic into a shared core module: `core/telephony.py`.
  * *Contract:* `parse_phone_number(raw_input: str, country_code: str) -> NormalizedPhone`
  * *Impact Radius:* Update `billing/validators.py` and `shipping/models.py` to import `parse_phone_number`, deleting the legacy inline regex blocks completely.


### Example 3: Trigger 1 & 3 (Cross-Module + Minimal Interface) — Existing Code Refactor
* **Context:** Both the `billing` module and the `shipping` module contain duplicate, highly complex regex patterns and string manipulation to validate international phone numbers.
* **Plan:** Centralize and hide the validation complexity.
  * *Abstraction:* Extract the logic into a shared core module: `core/telephony.py`.
  * *Contract:* `parse_phone_number(raw_input: str, country_code: str) -> NormalizedPhone`
  * *Impact Radius:* Update `billing/validators.py` and `shipping/models.py` to import `parse_phone_number`, deleting the legacy inline regex blocks completely.

### Example 3: Trigger 3 & 4 (Minimal Interface + Boundary Line) — Frontend / Middleware / Backend
* **Context:** A prompt requests a desktop configuration dashboard where changing a slider instantly updates a visual gauge, sends a telemetry payload via an open socket, and logs the action.
* **Plan:** Isolate the presentation state from the network and I/O middleware.
  * *Abstraction:* Create a decoupled state mediator (`state_manager.py`) and an independent network controller (`telemetry_client.py`).
  * *Contract:* 
    * `TelemetryClient.send_metric(metric_id: str, value: float) -> bool`
    * `StateManager.update_value(new_value: float) -> UIState`
  * *Boundary:* The UI layer handles rendering and captures user input. It calls the `StateManager`, which updates the UI state contract and triggers the `TelemetryClient` asynchronously. Neither the UI nor the State Manager contains raw TCP or socket socket logic.

### Example 4: Trigger 2 & 4 (Isolated Functionality + Boundary Line) — Transport vs. Application Layer
* **Context:** A custom lightweight TCP server has a monolithic event loop handling packet byte-stream framing, header parsing, session authentication, and database routing inside a single file.
* **Plan:** Isolate the physical transport stream protocol from application layer processing.
  * *Abstraction:* Extract the transport stream into a dedicated protocol framing parser (`transport/framing.py`).
  * *Contract:* `PacketStreamParser.feed(chunk: bytes) -> List[RawPacket]`
  * *Boundary:* The networking event loop reads raw bytes from the socket, feeds them blindly to the `PacketStreamParser`, and receives fully formed packets. The parser is a pure state-machine with zero dependencies on sockets, async loops, authentication, or databases.