-- ============================================================================
-- ManoExperta - Postgres / Supabase schema (voice agent backend)
-- ============================================================================
-- This is the actual schema behind the n8n "Vapi Core API" workflow. It stores
-- callers, technicians, the per-call state machine, the appointment slot lock,
-- the conversation transcript and a structured audit log.
--
-- WARNING: This file documents the current schema for context. It contains the
-- table DDL plus the indexes (see the INDEXES section at the bottom), but the
-- table order below is NOT valid for a clean run because of the foreign keys,
-- and the sequences used by the integer PKs (*_id_seq) are not defined here.
-- Logical creation order is:
--   1) technicians, customers      (no external FKs)
--   2) calls                       (FK -> customers, technicians)
--   3) chat_history, workflow_logs, appointment_slots  (FK -> calls / technicians)
--   4) indexes                     (after the tables exist)
--
-- Required Postgres extensions:
--   pgcrypto    -> gen_random_uuid()    (used by calls.id)
--   uuid-ossp   -> uuid_generate_v4()   (used by customers.id)
--
-- Relationships:
--   customers (1) --- (N) calls
--   technicians (1) --- (N) calls
--   technicians (1) --- (N) appointment_slots
--   calls (1) --- (N) chat_history        (via calls.call_id = chat_history.session_id)
--   calls (1) --- (N) workflow_logs        (via calls.call_id)
-- ============================================================================


-- ----------------------------------------------------------------------------
-- calls: one row per phone call; the per-call state machine.
--   - call_id is the Vapi call id and the natural key other tables reference.
--   - status drives the flow: IN_PROGRESS -> SUCCESS (RAG) / COMPLETED (booked)
--     / CANCELLED, or a FAILED_* value set by the fault-tolerance layer.
--   - incident_state / offered_slots hold transient JSON the agent builds during
--     the call (detected category, slots offered to the caller).
--   - gcal_event_id links the call to the Google Calendar event once booked.
-- ----------------------------------------------------------------------------
CREATE TABLE public.calls (
  id uuid NOT NULL DEFAULT gen_random_uuid(),         -- surrogate PK
  call_id text NOT NULL UNIQUE,                        -- Vapi call id (natural key used by FKs)
  phone_number text,                                  -- caller number; identifies returning clients
  incident_state jsonb DEFAULT '{}'::jsonb,           -- e.g. { "incident_category": "plumbing" }
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  offered_slots jsonb DEFAULT '[]'::jsonb,            -- slots presented to the caller (check action)
  confirmation_code character varying,                -- code returned on a successful booking
  customer_id uuid,                                   -- resolved customer, if known
  gcal_event_id character varying,                    -- Google Calendar event id once booked
  current_speaker_name character varying,             -- name captured during the conversation
  status character varying DEFAULT 'IN_PROGRESS'::character varying, -- IN_PROGRESS|SUCCESS|COMPLETED|CANCELLED|FAILED_*
  error_log jsonb,                                    -- last error context (set by fault layer)
  technician_id integer,                              -- assigned technician, if booked
  CONSTRAINT calls_pkey PRIMARY KEY (id),
  CONSTRAINT calls_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id),
  CONSTRAINT calls_technician_id_fkey FOREIGN KEY (technician_id) REFERENCES public.technicians(id)
);


-- ----------------------------------------------------------------------------
-- chat_history: full conversation transcript, one row per message.
--   - session_id == calls.call_id, so the transcript is grouped per call.
--   - message stores the message object (role/content) as JSON, which is the
--     shape LangChain / chat-memory integrations expect.
-- ----------------------------------------------------------------------------
CREATE TABLE public.chat_history (
  id integer NOT NULL DEFAULT nextval('chat_history_id_seq'::regclass),
  session_id text NOT NULL,                           -- = calls.call_id
  message jsonb NOT NULL,                             -- { "role": ..., "content": ... }
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT chat_history_pkey PRIMARY KEY (id),
  CONSTRAINT fk_call_session FOREIGN KEY (session_id) REFERENCES public.calls(call_id)
);


-- ----------------------------------------------------------------------------
-- technicians: the catalogue of field technicians that can be scheduled.
--   - calendar_id is the technician's Google Calendar used for availability and
--     event creation.
--   - status = 'available' is what "Fetch Technicians" filters on.
--   - zone supports routing/coverage logic by area.
-- ----------------------------------------------------------------------------
CREATE TABLE public.technicians (
  id integer NOT NULL DEFAULT nextval('technicians_id_seq'::regclass),
  full_name character varying NOT NULL,
  specialty character varying NOT NULL,               -- plumbing / electrical / hvac ...
  zone integer NOT NULL,                              -- coverage zone id
  status character varying DEFAULT 'available'::character varying, -- available | inactive
  calendar_id character varying,                      -- Google Calendar id for this technician
  phone_number character varying,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT technicians_pkey PRIMARY KEY (id)
);


-- ----------------------------------------------------------------------------
-- customers: known callers (a CRM-lite). Keyed by a unique phone_number so a
-- returning caller is recognized automatically without asking for their number.
-- ----------------------------------------------------------------------------
CREATE TABLE public.customers (
  id uuid NOT NULL DEFAULT uuid_generate_v4(),
  phone_number character varying NOT NULL UNIQUE,     -- lookup key for returning callers
  first_name character varying,
  email character varying,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT customers_pkey PRIMARY KEY (id)
);


-- ----------------------------------------------------------------------------
-- workflow_logs: structured observability for the n8n flow.
--   - One row per logged event; the fault layer writes level='ERROR' rows with
--     the failing node_name, tool_name, status (e.g. FAILED_BOOKING) and payload.
--   - level defaults to 'INFO' so the same table can hold non-error telemetry.
-- ----------------------------------------------------------------------------
CREATE TABLE public.workflow_logs (
  id bigint NOT NULL DEFAULT nextval('workflow_logs_id_seq'::regclass),
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  call_id text,                                       -- FK -> calls.call_id (nullable: pre-parse errors)
  tool_name text,                                     -- consultar_manual_rag | gestionar_agenda_db
  node_name text,                                     -- n8n node that produced the log
  level text NOT NULL DEFAULT 'INFO'::text,           -- INFO | ERROR | ...
  status text,                                        -- e.g. FAILED_BOOKING, BOOKING_COLLISION
  payload jsonb,                                      -- { message, detail, ... }
  CONSTRAINT workflow_logs_pkey PRIMARY KEY (id),
  CONSTRAINT workflow_logs_call_id_fkey FOREIGN KEY (call_id) REFERENCES public.calls(call_id)
);


-- ----------------------------------------------------------------------------
-- appointment_slots: the concurrency lock that prevents double-booking.
--   - "Reserve Slot" does: INSERT ... ON CONFLICT (technician_id, slot_start)
--     DO NOTHING. That makes a slot reservable exactly once, so two simultaneous
--     callers can never grab the same technician + time.
--   - gcal_event_id is NULL until the calendar event is confirmed; failed
--     bookings release the row (DELETE ... WHERE gcal_event_id IS NULL).
-- ----------------------------------------------------------------------------
CREATE TABLE public.appointment_slots (
  id bigint NOT NULL DEFAULT nextval('appointment_slots_id_seq'::regclass),
  technician_id integer NOT NULL,
  slot_start timestamp with time zone NOT NULL,       -- appointment start (stored in UTC)
  call_id text,                                       -- the call that reserved the slot
  gcal_event_id text,                                 -- set once the calendar event exists
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT appointment_slots_pkey PRIMARY KEY (id),
  CONSTRAINT appointment_slots_tech_fk FOREIGN KEY (technician_id) REFERENCES public.technicians(id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================
-- Two groups below:
--   1) Implicit indexes  -> created automatically by the PRIMARY KEY / UNIQUE
--                           constraints declared in the tables above. They are
--                           listed here only for completeness; you do NOT need
--                           to create them by hand. (Names: *_pkey, *_key.)
--   2) Secondary indexes -> the ones you DO create to speed up the lookups the
--                           n8n workflow performs. These use IF NOT EXISTS so
--                           the file is safe to re-run.
-- ----------------------------------------------------------------------------

-- --- 1) Implicit (auto-created by constraints; documented, do not run) -------
--   appointment_slots_pkey         UNIQUE (id)                    <- PK
--   calls_pkey                     UNIQUE (id)                    <- PK
--   calls_call_id_key              UNIQUE (call_id)               <- UNIQUE column
--   chat_history_pkey              UNIQUE (id)                    <- PK
--   customers_pkey                 UNIQUE (id)                    <- PK
--   customers_phone_number_key     UNIQUE (phone_number)          <- UNIQUE column
--   technicians_pkey               UNIQUE (id)                    <- PK
--   workflow_logs_pkey             UNIQUE (id)                    <- PK


-- --- 2) Secondary indexes (create these) ------------------------------------

-- appointment_slots ----------------------------------------------------------
-- CONCURRENCY LOCK: this unique index is what makes the anti-double-booking
-- "INSERT ... ON CONFLICT (technician_id, slot_start) DO NOTHING" work. Without
-- it there is no conflict target and two callers could grab the same slot.
CREATE UNIQUE INDEX IF NOT EXISTS appointment_slots_unique
  ON public.appointment_slots USING btree (technician_id, slot_start);
-- Release/cleanup of unconfirmed reservations (WHERE gcal_event_id IS NULL).
CREATE INDEX IF NOT EXISTS appointment_slots_gcal_event_idx
  ON public.appointment_slots USING btree (gcal_event_id);
-- Look up the slot(s) reserved by a given call.
CREATE INDEX IF NOT EXISTS appointment_slots_call_id_idx
  ON public.appointment_slots USING btree (call_id);

-- calls ----------------------------------------------------------------------
-- Returning-caller lookup + state filtering (phone_number, status).
CREATE INDEX IF NOT EXISTS calls_phone_status_idx
  ON public.calls USING btree (phone_number, status);
-- Recent-calls ordering for dashboards / debugging.
CREATE INDEX IF NOT EXISTS calls_created_at_idx
  ON public.calls USING btree (created_at DESC);
-- Calls handled by a given technician.
CREATE INDEX IF NOT EXISTS calls_technician_id_idx
  ON public.calls USING btree (technician_id);
-- Non-unique lookup by call_id. NOTE: redundant with the implicit unique index
-- calls_call_id_key (also on call_id); kept here to mirror the live DB, but it
-- can be dropped to avoid a duplicate index.
CREATE INDEX IF NOT EXISTS idx_calls_call_id
  ON public.calls USING btree (call_id);

-- chat_history ---------------------------------------------------------------
-- Fetch a full transcript by session (= calls.call_id).
CREATE INDEX IF NOT EXISTS idx_chat_history_session_id
  ON public.chat_history USING btree (session_id);

-- workflow_logs --------------------------------------------------------------
-- Trace every log line for one call.
CREATE INDEX IF NOT EXISTS workflow_logs_call_id_idx
  ON public.workflow_logs USING btree (call_id);
-- Filter by severity (e.g. only ERROR rows).
CREATE INDEX IF NOT EXISTS workflow_logs_level_idx
  ON public.workflow_logs USING btree (level);
-- Recent-logs ordering.
CREATE INDEX IF NOT EXISTS workflow_logs_created_at_idx
  ON public.workflow_logs USING btree (created_at DESC);