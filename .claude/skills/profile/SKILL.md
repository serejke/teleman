---
name: profile
description: "Deep-profile participants from exported Telegram chats. Reads a user's FULL message history and produces: professional profile, top themes/interests, psychological profile, top jokes. Use when asked to profile, analyze personality, or understand a chat participant."
argument-hint: "<chat> [user_name | 'top N'] — e.g. 'Vibe Mikhail', 'Vibe top 5'"
allowed-tools: Bash, Read, Agent
---

**Task: Profile chat participants by reading their ENTIRE message history and producing qualitative LLM analysis.**

## How it works

1. Extract a user's full messages via: `uv run python -m analysis.extract_user <chat> "<user_name>"`
2. Read the extracted text into agent context (the FULL output — no truncation)
3. Produce a structured profile based on the messages

## Extraction tool

```bash
# Extract as readable text (for LLM ingestion)
uv run python -m analysis.extract_user <chat> "<user_name>"

# Extract as JSONL (for programmatic use)
uv run python -m analysis.extract_user <chat> "<user_name>" --format jsonl
```

- Chat resolution: by chat_id, title substring, username, or path
- User resolution: exact match first, then substring match on sender_name
- Output: chronological messages with timestamps, reply markers, media info, edit flags

## Identifying top users

Run the users skill to find the most active participants:

```bash
uv run python -m analysis users <chat>
```

This returns JSON with users ranked by message count. Use sender_name values as user identifiers.

## Profiling workflow

When the user asks to profile participants (e.g., "profile top 5 in Vibe"):

1. Run `uv run python -m analysis users <chat>` to identify top N users by message count
2. For EACH user, spawn a **parallel Agent** that:
   a. Runs `uv run python -m analysis.extract_user <chat> "<sender_name>"` and saves output to a temp file
   b. Reads the ENTIRE temp file into context (use Read tool — do NOT truncate)
   c. Analyzes the messages and produces the profile (see format below)
3. Collect all agent results and present them together

**Critical**: Each agent MUST read ALL messages. Do not sample, truncate, or summarize. The whole point is full-context analysis. Save extraction output to `/tmp/profile_<sanitized_name>.txt` so the agent can Read it.

## Profile output format

For each user, produce:

### <User Name> (N messages, date range)

**Professional Profile**

- Role/position, experience level, tech stack, companies mentioned
- If insufficient signal, say so — don't fabricate

**Top Themes & Interests**

- Ranked list of topics they discuss most, with representative quotes
- What they're passionate about vs. what they just react to

**Psychological Profile**

- Communication style (verbose vs. terse, analytical vs. emotional, initiator vs. responder)
- How they interact with others (confrontational, supportive, mentoring, lurking)
- Decision-making patterns, what triggers engagement, what makes them go quiet
- Notable behavioral patterns

**Top Jokes / Memorable Quotes**

- 3-5 funniest or most memorable messages (verbatim with dates)
- Humor style characterization

## Guidelines

- Write profiles in the SAME LANGUAGE as the user's messages (if messages are in Russian, profile is in Russian)
- Be specific — cite actual messages and dates, not vague generalizations
- Don't moralize or judge — describe observed behavior objectively
- If a user shares very few text messages (mostly media), note that the profile is limited
- For forwarded messages, distinguish between the user's own thoughts and what they share from others
