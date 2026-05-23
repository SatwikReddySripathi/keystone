# Keystone — 3-Minute Video Recording Plan

This document is everything you need to shoot and ship the 3-minute Keystone demo video.
It synchronizes the pitch deck (`pitch_deck.html`) with a live product demo driven by
`sdk/demo_recording.py`, so ~45 seconds of the video is slide content and ~135 seconds is
live product footage.

---

## Files that power this video

| File | Role |
|---|---|
| `pitch_deck.html` | Market + PMF pitch deck, 12 slides. Slides 1–3 and 12 appear in the video. |
| `sdk/demo_recording.py` | Interactive teleprompter + live SDK demo runner. |
| `VIDEO_RECORDING.md` | This file — plan, narration, and post-production notes. |

---

## 1. Equipment & software

### Hardware
- Computer capable of running Next.js dev server + FastAPI + screen recorder simultaneously
- **External microphone** (USB condenser — Blue Yeti, Shure MV7, or similar). Laptop mic is fine for internal review but not for a public demo.
- Quiet room. Close windows. Silence notifications.

### Software
- **Screen recorder** — pick one:
  - OBS Studio (free, most control, learning curve)
  - Screen Studio (Mac, paid, beautiful defaults)
  - Loom (browser, fastest turnaround, no post-editing)
- **Editor** (only if you use OBS):
  - DaVinci Resolve (free, overkill but great)
  - CapCut (free, fast for short cuts)
  - iMovie / Shotcut
- Browser: Chrome or Edge (consistent rendering)
- Terminal: any, but bump font to ~14–16pt for readability

### Recording settings
- **Resolution**: 1920 × 1080, 30fps (60fps if editor supports it)
- **Audio**: 48kHz, mono, -12 to -6 dB peaks
- **Zoom the browser to 110%** so text is readable at compressed video bitrate
- **Hide the bookmarks bar** (`Ctrl+Shift+B`)
- **Close all other tabs** before recording

---

## 2. Pre-recording checklist (10 min before you hit record)

### Terminal 1 — fresh backend
```bash
cd keystone/backend
rm -f keystone.db
uvicorn app.main:app --reload --port 8000
```
Wait for `Application startup complete.` Keep this terminal visible — OTP codes print here.

### Terminal 2 — UI
```bash
cd keystone/ui
npm run dev
```
Wait for `ready started server on 0.0.0.0:3000`.

### Browser setup
1. Navigate to `http://localhost:3000`
2. Log in as `sarah.chen@keystone.org` / `sarah-admin`
3. OTP is in Terminal 1 — copy, paste, submit
4. Confirm the dashboard loads and the sidebar backend dot is green
5. Open these tabs in **this order** (left to right):

| Tab | URL | Use |
|---|---|---|
| 1 | `pitch_deck.html` (fullscreen, slide 1) | Opening + closing slides |
| 2 | `http://localhost:3000/` | Dashboard |
| 3 | `http://localhost:3000/approvals` | Approval gate demo |
| 4 | `http://localhost:3000/audit` | Audit trail (backup shot) |

### Terminal 3 — the recording director
```bash
cd keystone/sdk
python demo_recording.py
```
Do **not** press ENTER yet — it will wait at the pre-flight screen.

### Final audio check
- Say one line aloud. Confirm microphone levels on the recorder peak at −12 to −6 dB.
- Disable Slack, Mail, iMessage, phone vibrations.

### Hit record on OBS / Screen Studio / Loom
Give yourself a **3-second buffer of silence** at the start (easier to trim in post).

---

## 3. The timeline — 180 seconds, synchronized

| # | Time | Screen | What you do | Action |
|---|---|---|---|---|
| 1 | 0:00 – 0:10 | Pitch deck slide 1 | Hold on cover. Read the hook. | — |
| 2 | 0:10 – 0:25 | Pitch deck slide 2 | Scroll to "Why Now". Slowly trace the timeline with cursor. | — |
| 3 | 0:25 – 0:40 | Pitch deck slide 3 | Scroll to "The Pain". Let the quote land — don't rush. | — |
| 4 | 0:40 – 0:52 | Terminal 3 | Switch to terminal. Press ENTER. SDK call runs live. | `completed` |
| 5 | 0:52 – 1:15 | Browser — completed action detail | Open latest action. Point at: blast radius → decision → lifecycle → proof. | — |
| 6 | 1:15 – 1:28 | Terminal 3 | Quick switch. ENTER runs blocked scenario. | `blocked` |
| 7 | 1:28 – 1:40 | Browser — blocked action | Open blocked action. Point at Policy Reasons panel and `has_p1` flag. | — |
| 8 | 1:40 – 1:53 | Terminal 3 | ENTER runs approval scenario. | `approval` |
| 9 | 1:53 – 2:13 | Browser — /approvals | Go to approval queue. Show pending card. Click Approve. Watch status flip. | — |
| 10 | 2:13 – 2:30 | Terminal 3 + browser | ENTER runs contained. Switch to browser. Show tripped breaker + failed check. | `contained` |
| 11 | 2:30 – 2:45 | Browser — proof receipt | Open proof page of completed action. Point at signature + verification badge. | — |
| 12 | 2:45 – 3:00 | Pitch deck slide 12 | Switch to pitch deck. Scroll to last slide. Hold for closing line. | — |

`demo_recording.py` drives segments 4, 6, 8, 10 — it prints the narration + action label and runs the SDK call when you hit ENTER.

---

## 4. Narration script — read verbatim for a clean first take

> **[0:00, pitch deck slide 1]**
> AI agents are moving from chat to action. Enterprise systems are receiving real write traffic from models — and there is no governance layer to control it.

> **[0:10, pitch deck slide 2]**
> In the last eighteen months, function calling, computer use, and agent frameworks turned language models into autonomous workers. Gartner expects seventy percent of enterprises to deploy these by 2027. Governance tooling has not caught up.

> **[0:25, pitch deck slide 3]**
> This is what it looks like today. An agent runs a bulk update. It closes 340 tickets — three of them active P1 outages. No preview. No approval gate. No audit-grade record. Compliance is left reconstructing the decision after the fact.

> **[0:40, terminal]**
> Keystone is the governance layer between the agent and your systems. One SDK call. Full lifecycle. Let's watch it run.

> **[0:52, browser — completed action detail]**
> Here is the action. Blast radius: twenty records. Policy evaluates: canary. Keystone executes on five records first, runs five safety invariants, then expands to all twenty — and signs a tamper-evident receipt. The agent did not touch production until Keystone said go.

> **[1:15, terminal]**
> Same agent. Broader query — this time pulling in P1 critical incidents.

> **[1:28, browser — blocked action]**
> Policy says block. Zero records modified. The reason is versioned, logged, and bound to the exact preview the agent proposed.

> **[1:40, terminal]**
> This one impacts VIP accounts. Policy routes it to a human.

> **[1:53, browser — /approvals, click Approve]**
> The approver gets blast radius, diff preview, risk flags — full context in band. And the approval is cryptographically bound to this exact preview. If data changes before execution, the approval is void. You cannot approve one thing and execute another.

> **[2:13, contained action]**
> Policy allowed this one. But during canary, the target system's business rules modified fields the agent never asked to touch. Keystone's circuit breaker caught the divergence and halted. Five records modified. Fifteen protected.

> **[2:30, proof receipt page]**
> Every action ends with a signed proof receipt. HMAC SHA-256. Who proposed it. What policy decided. Who approved. What actually changed. This is the audit trail compliance has been asking for.

> **[2:45, pitch deck slide 12]**
> Keystone. Transaction governance for AI agents. MVP is live. SDK is published. We're taking design partners now. `pip install keystone-governance`.

**Word count**: ~395 words. At 140 wpm (comfortable pacing) that's 2:50 — leaves 10 seconds of breathing room.

---

## 5. Delivery notes

- **Cursor discipline**: move deliberately and slowly. Stop moving while you speak. Hesitant-looking cursor kills the take.
- **Don't narrate while clicking**: click → wait for visual → then speak. 250 ms of silence after a click reads as confidence, not hesitation.
- **Emphasis words**: `governance`, `preview`, `canary`, `breaker`, `proof`, `blocked`, `approved`. Hit them slightly harder.
- **Breathing room**: the narration is written with natural pauses. Do not rush the quote on slide 3 — it's the emotional beat.
- **Zoom**: if a metric on the UI is too small, zoom the browser via `Ctrl +` *before* the segment. Don't mid-sentence zoom.

---

## 6. Common failure modes (and fixes)

| Symptom | Fix |
|---|---|
| OTP code doesn't arrive | It's in Terminal 1. Not the browser. |
| Dashboard shows empty state | You forgot to run at least one demo action first — hit ENTER in Terminal 3 to run the completed scenario. |
| Breaker doesn't trip in the contained scenario | Run scenarios in order. The contained scenario requires the Triage Team assignment from the completed scenario. |
| Approval queue is empty | Run the approval scenario first — it's segment 8. |
| Take goes over 3:00 | Trim the slide transitions in post. The pitch deck segments can be 1–2 seconds shorter each. |
| Cursor flickers between windows | Use OBS Studio Mode to pre-stage scenes and hot-swap, or simply re-take. |
| Typo or stumble in narration | Don't restart the whole take — the script is segment-isolated. Re-record just that segment, then cut it in. |

---

## 7. Post-production checklist

1. **Trim the head and tail** — remove silent buffer and anything past the closing line
2. **Captions** — YouTube auto-captions first, then manually fix jargon (`HMAC`, `SHA-256`, `blast radius`, `canary`, `circuit breaker`, `Keystone`, `preview hash`)
3. **On-screen text overlays** at each live-demo segment (optional but recommended):
   - "Preview" at 0:55
   - "Policy" at 1:28
   - "Approval" at 1:55
   - "Circuit breaker" at 2:13
   - "Proof" at 2:30
4. **No music** for a product demo at this stage — it distracts. Silent backing track only if you strongly prefer.
5. **Export settings**:
   - 1080p, H.264, ~8–10 Mbps bitrate
   - AAC audio at 192 kbps
6. **Thumbnail**: take a still frame from slide 5 of the pitch deck (lifecycle diagram) with "3-MIN DEMO" overlaid.
7. **Filename**: `keystone-demo-v1-YYYYMMDD.mp4`

---

## 8. Distribution

| Target | Where | Format |
|---|---|---|
| Design partner outreach | Email attachment or Loom share link | MP4 + PDF of pitch deck |
| Product Hunt | YouTube unlisted → embed | 3-minute video |
| Landing page hero | Silent MP4 loop of slides 1 + demo only | 1080p MP4 |
| Investors | Email with Loom link + pitch_deck.html | 3-min video + deck |
| GitHub README | YouTube embed | Public video |

---

## 9. Running the recording director

```bash
cd keystone/sdk
python demo_recording.py
```

What happens:
1. **Pre-flight** — verifies backend is up, prints the setup checklist. Press ENTER.
2. **12 segment screens** — each shows:
   - What to put on screen (pitch deck slide / terminal / specific browser tab)
   - Visual cue (where to click, what to point at)
   - **The narration, in bold** — read it verbatim
   - Whether a live SDK call will run
3. Press ENTER on each segment. If the segment has a live action, pressing ENTER both advances the segment AND runs the action.
4. **Take complete** screen — shows actual length vs target (180s).

The script never auto-advances — you always control pacing, so you can re-take a single segment without burning the whole take.

---

## 10. What's in the new pitch deck

For context — the video uses 4 slides but the deck has 12. Here's the full set:

| # | Slide | In video? |
|---|---|---|
| 1 | Cover | ✓ (0:00) |
| 2 | Why Now — 2022–2026 timeline, Gartner/IDC/McKinsey stats | ✓ (0:10) |
| 3 | The Pain — customer quote + 3 gaps | ✓ (0:25) |
| 4 | ICP — buyer profile, trigger events, pain intensity | — |
| 5 | Market Sizing — TAM ($2B) / SAM ($500M) / SOM ($50M) | — |
| 6 | Competitive Landscape — 2×2 positioning matrix | — |
| 7 | Our Position — category definition + moat | — |
| 8 | Product — SDK snippet | — |
| 9 | PMF Signals — 6 validation points | — |
| 10 | Go-to-Market — wedge + expand | — |
| 11 | Business Model — pricing tiers, gross margin, NRR | — |
| 12 | Team + Ask | ✓ (2:45) |

Slides 4–11 are for investor 1:1s, design partner calls, and written outreach. The video is a hook that gets people to ask for the full deck.