# Tool contracts (Vapi -> n8n)

The voice assistant calls two tools. Vapi POSTs a tool-call payload to the n8n webhook
(`/webhook/vapi-tools`); the `Parse Payload` node flattens it into `{ call_id, phone,
tool_call_id, tool_name, args }` and the `Tool Router` switches on `tool_name`.

Every response is returned in Vapi's expected shape:

```json
{ "results": [ { "toolCallId": "<id>", "result": { ... } } ] }
```

## 1. `consultar_manual_rag`

Retrieve the official, safe procedure for a technical symptom from the vector knowledge base.

**Arguments**

| Field | Type | Description |
|-------|------|-------------|
| `symptoms` | string | Free-text description of the problem (used as the query) |
| `category` | string | Detected category (plumbing/electrical/hvac), stored on the call |

**Result**

```json
{ "safety_warning": "<seguridad>", "solution_steps": "<solucion>" }
```

Flow: `Search Technical KB` (Pinecone + Gemini embeddings, topK=1) -> `Return RAG Data`
-> async `UPDATE calls SET incident_category, status='SUCCESS'`.

## 2. `gestionar_agenda_db`

Manage appointments. The `action` argument selects the sub-flow.

| `action` | Purpose |
|----------|---------|
| `check` | Offer available time slots |
| `book` | Reserve + create the appointment |
| `lookup` | Find the caller's active appointment (by phone) |
| `cancel` | Cancel the caller's active appointment |

**Arguments**

| Field | Type | Used by | Description |
|-------|------|---------|-------------|
| `action` | string | all | `check` \| `book` \| `lookup` \| `cancel` |
| `preferred_date` | ISO datetime | book | Requested slot start (Bogota, UTC-5) |
| `technician_name` | string | book | Technician to book |

The caller is identified automatically by their **phone number** (from the Vapi payload),
so `lookup`/`cancel` never ask for it.

**Results by action**

```jsonc
// check
{ "slots": [ { "date_iso": "...", "technician_name": "...", "calendar_id": "..." } ] }

// book (success)
{ "status": "confirmed", "confirmation_code": "CONF-1234" }

// book (slot taken in the meantime)
{ "status": "slot_unavailable", "message": "..." }

// lookup
{ "found": true, "technician_name": "...", "slot_start": "..." }

// cancel
{ "status": "cancelled" }      // or { "status": "not_found" }
```

## Booking concurrency (the important part)

`book` is protected against double-booking by a database lock, not by hope:

1. `Reserve Slot` - `INSERT ... ON CONFLICT (technician_id, slot_start) DO NOTHING` returns
   whether the row was actually reserved.
2. `IF Reserved?` - if another caller already holds it, respond `slot_unavailable`.
3. Re-check Google Calendar, then `Create an event`.
4. On any failure after reserving, the matching `Release Slot` frees the lock so it isn't
   left dangling.

This means two simultaneous callers can never both "confirm" the same time.

## Reprogramming order (book -> cancel)

The prompt enforces: when rescheduling, **book the new appointment first**, and only cancel
the previous one once the new booking is `confirmed`. `Lookup For Cancel` excludes the
current call's appointment so a reschedule never cancels the just-created booking.
