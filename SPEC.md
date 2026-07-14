# Crash Detection & Emergency Alert App — Specification (Draft v0.2)

## 0. Decisions Locked In

- **Platform**: Android first (v1). iOS is a future phase — see §6.
- **Emergency services notification**: integrate with a third-party
  crash-dispatch API (RapidSOS-style) that pushes structured crash data to
  911 dispatch centers, rather than autodialing or relying on a native
  dialer handoff. See §4.
- **Project stage**: concept/spec only right now — no app code yet. This
  document is the artifact being iterated on.

## 1. Overview

A mobile app that runs in the background while a user is driving. It uses onboard
phone sensors to detect severe collisions/accidents, and — once a crash is
confirmed — automatically notifies emergency services and a user-defined list of
emergency contacts (friends/family) with the user's location and crash details.

Core value proposition: if the driver is incapacitated or unable to call for help,
help still gets called.

## 2. Goals / Non-Goals

**Goals**
- Detect severe collisions in near-real-time using sensor fusion.
- Minimize false positives (hard braking, potholes, dropped phone) while not
  missing real crashes (minimize false negatives).
- Give the user a window to cancel a false alarm before anything is sent.
- Notify emergency services (or route to a human-staffed response center) and
  personal contacts with location + crash context.
- Run reliably in the background on a phone mounted in a moving vehicle,
  respecting each OS's background execution limits and battery constraints.

**Non-Goals (for v1, unless you say otherwise)**
- Replacing a dedicated vehicle telematics/OBD-II crash system.
- Detecting minor fender-benders / low-speed parking-lot bumps as "severe."
- Being a full navigation or trip-logging product (though trip context helps
  detection and may be a natural adjacent feature).

## 3. Core Detection Pipeline

### 3.1 Signals used
| Signal | Sensor | Purpose |
|---|---|---|
| Sudden deceleration/acceleration | Accelerometer | Primary crash signature (large delta-v in a short window) |
| Orientation change / tumbling | Gyroscope | Detect rollover, spin, irregular motion after impact |
| Speed / speed delta | GPS (+ fused with accelerometer) | Confirm vehicle was in motion and lost speed abruptly |
| Impact sound | Microphone | Detect crash acoustic signature (glass, metal, tire screech) as corroborating signal |
| Post-event motion | Accelerometer/gyroscope | Detect stillness after impact (airbag deployed, occupant not moving) vs. continued driving |

### 3.2 Detection logic (proposed)
1. **Trip detection**: app only arms crash detection when it infers the user is
   driving (speed > threshold via GPS, or manual "start drive" toggle, or
   Bluetooth car-stereo connection, or motion classification API).
2. **Candidate event trigger**: a spike in acceleration magnitude beyond a
   threshold (e.g., >X g over <Y ms) opens a short evaluation window (~2–5 sec).
3. **Corroboration scoring**: within that window, combine:
   - Magnitude/shape of the acceleration spike
   - Speed drop rate from GPS
   - Gyroscope irregularity (tumbling/rotation)
   - Audio classifier confidence (crash sound vs. road noise/music/talking)
   - Post-impact stillness or erratic movement
   A weighted/ML confidence score determines severity tier.
4. **Tiering**:
   - **Low confidence** → log only, no alert.
   - **Medium confidence** → local notification asking "Are you OK?"
   - **High confidence** → start the cancellation countdown (see 3.3).
5. **On-device vs cloud**: initial classification should happen on-device
   (latency, works with poor signal, privacy) using a lightweight model;
   optionally corroborate/upgrade confidence via a backend ML model if
   connectivity allows.

### 3.3 False-alarm cancellation window
- On high-confidence detection: full-screen alert + loud siren-like sound +
  haptic, with a visible countdown (e.g., 15–30 seconds, configurable).
- User can tap "I'm OK" / enter a PIN or biometric to cancel.
- If no response, or user explicitly confirms, the app proceeds to Section 4.
- If the phone is *unresponsive to touch* but the user is talking, consider a
  voice-based "I'm OK" cancel (stretch goal, needs voice liveness/anti-spoof
  design).

## 4. Emergency Response Flow

1. **Trigger** (countdown expires or user confirms "I need help").
2. **Gather context**: GPS coordinates + accuracy, timestamp, estimated speed
   at impact, address (reverse geocoded), device battery level, user's
   emergency medical info if provided (blood type, allergies — optional
   profile field).
3. **Notify emergency services** (decided: third-party dispatch API):
   - Integrate with a service in the RapidSOS family (or regional
     equivalent) that accepts structured crash telemetry (location,
     timestamp, speed at impact, confidence tier) and pushes it into the
     911 dispatch center's existing data pipeline (NG911), rather than the
     app placing a call itself.
   - This means the *dispatch center's own call-taker/system* is the one
     that decides whether/how to route a unit — the app's job is to hand
     off clean, structured, trustworthy data plus (if technically
     supported by the provider) an open audio channel or callback number
     so dispatch can attempt to reach the user directly.
   - Practical requirements this creates:
     - A backend account/contract with the dispatch-data provider (this is
       a B2B integration, not a public API key you drop into a mobile
       app — plan for a vetting/onboarding process with the vendor).
     - A fallback path for when the provider has no coverage in the
       user's location (some regions/counties aren't yet on NG911) — fall
       back to notifying contacts + surfacing a one-tap "Call 911" button
       to the user/bystanders.
     - Legal review of the integration terms (see §8, liability question
       still open).
4. **Notify emergency contacts**: SMS + push notification (if they also have
   the app) with:
   - "[Name] may have been in a car accident."
   - Location link (live-updating if possible).
   - Time of incident.
   - Button/link to call the user directly.
5. **Retry/redundancy**: if primary notification channel fails (no cell
   signal), queue and retry; consider fallback to SMS (lower bandwidth) if
   data connection is unavailable.
6. **Post-incident**: keep sending live location updates to contacts for a
   configurable period after the crash, in case first responders need it.

## 5. Setup / Onboarding

- Account creation (phone number and/or email).
- Emergency contacts: add 1–5 contacts (name, phone number, relationship);
  contacts get an SMS invite; optionally they can install the app to see
  live location once notified.
- Optional medical profile: blood type, allergies, conditions, emergency
  contact for medical staff.
- Permission requests, with clear rationale screens before each OS prompt:
  - Location (Always/background)
  - Motion & Fitness / Activity Recognition
  - Microphone (background use)
  - Notifications
  - Contacts (optional, for picking contacts)
  - Phone (to place emergency calls, if applicable on Android)
- Sensitivity calibration: choice of vehicle type (motorcycle vs. car affects
  thresholds), driving profile.
- Battery optimization exemption walkthrough (critical on Android — see §6).

## 6. Platform Constraints (critical design drivers)

**Android (v1 target)**
- Foreground service with a persistent (but low-key) notification is
  required to reliably keep sensors + GPS + mic running in the background
  for the whole drive.
- Must guide users through disabling battery optimization / granting
  "unrestricted battery" for the app — manufacturer-specific quirks
  (Samsung, Xiaomi, Huawei, OnePlus all have their own aggressive
  background-kill behavior on top of stock Android) will need a per-OEM
  onboarding help flow, since this is a common failure point for this
  category of app.
- Android permits apps to place emergency calls directly with
  `CALL_PHONE`, but per the decision in §0/§4 we are *not* using that path
  for v1 — the dispatch-API integration is the primary channel, with a
  one-tap manual "Call 911" button as a user-triggered fallback (using the
  native dialer, not silent autodial).
- Needs foreground-service type declarations (`location`, `microphone`,
  `connectedDevice` as applicable) per current Android background-service
  requirements, plus a clear runtime permission rationale flow for each.

**iOS (future phase, not v1)**
- No true persistent background microphone/accelerometer sampling at full
  rate indefinitely — background modes and always-on raw mic access are
  heavily restricted.
- Cannot programmatically dial 911 from a third-party app.
- Apple already ships OS-level Crash Detection (iPhone 14+), which is
  worth revisiting once we get to iOS — the app may differentiate via the
  dispatch-API integration and multi-contact alerting rather than trying
  to out-detect the OS.
- Parking this until Android v1 is validated; revisit sensor/permission
  APIs at that time since iOS's background capabilities evolve yearly.

## 7. Non-Functional Requirements

- **Latency**: detection-to-alert should be under ~30–60 seconds total
  including the cancellation window.
- **Battery**: background sensing must not drain a full charge in a normal
  commute; target budget TBD (needs prototyping/measurement).
- **Reliability**: alert pipeline must work with degraded connectivity
  (SMS fallback, retry queues, offline location caching).
- **Privacy/security**:
  - Location and audio snippets are sensitive data — define retention
    policy (e.g., only retain audio buffer transiently in memory unless a
    crash is confirmed).
  - Encrypt data in transit and at rest.
  - Clear consent flows for microphone/location "always" access.
  - Compliance: GDPR/CCPA at minimum; consider HIPAA-adjacent handling if
    medical profile data is stored.
- **Accuracy targets**: define acceptable false-positive rate (alerts per
  N driving hours) and false-negative rate (missed real crashes) —
  needs a labeled dataset / test methodology (e.g., closed-course testing,
  partnering with a crash-test data source, or referencing published crash
  accelerometry research).

## 8. Open Questions (remaining)

Platform, dispatch-integration approach, and project stage are decided
(§0). Still need your input on:

1. Do you have an existing brand/product name, design assets, or is this
   fully greenfield?
2. Any target regions/countries for launch? This matters a lot now that
   we've committed to a dispatch-data-API approach — coverage is
   regional/county-by-county (NG911 rollout is not nationwide/global), so
   the launch region determines whether the primary emergency-services
   path even has coverage on day one, versus needing the contacts-only
   fallback more often initially.
3. Which specific dispatch-data provider do you want to pursue (e.g.
   RapidSOS specifically, or are we open to alternatives/regional
   equivalents)? This is a vendor/business decision (contracts, cost,
   onboarding timeline) as much as a technical one, and it's on the
   critical path for §4.
4. Should the app also do live trip tracking/sharing outside of crash
   scenarios (e.g., "share my drive" like Life360), or stay purely dormant
   until a crash?
5. Who is legally responsible if the app fails to detect a real crash, or
   falsely alerts the dispatch API repeatedly? False-alarm volume is a
   real concern for dispatch centers/providers and likely affects vendor
   contract terms — worth involving counsel before committing to a
   provider.
6. Budget/timeline and team size — affects how ambitious v1's detection
   logic should be (simple threshold-based rules vs. an ML classifier from
   day one).

## 9. Suggested MVP (v0.1) Scope

To de-risk this, a leaner first version, consistent with the decisions in
§0:
- **Android only.**
- Threshold-based detection (acceleration spike + speed drop + gyroscope
  irregularity), no ML yet — mic-based corroboration can follow once the
  core pipeline is validated.
- Cancellation countdown UI ("I'm OK" / PIN or biometric cancel).
- On confirmed crash: send structured crash data to the chosen
  dispatch-data API integration, and simultaneously SMS/push-notify
  emergency contacts (via a backend like Twilio) with a location link.
- One-tap manual "Call 911" button surfaced post-alert as a fallback for
  the user or a bystander — never a silent autodial.
- Manual "start/stop drive" toggle rather than automatic trip detection,
  to start; iterate toward automatic trip detection in v2+.
- Get the dispatch-provider relationship (vendor selection, contract,
  sandbox/test access) moving early — it's likely the longest lead-time
  item and gates end-to-end testing of the core value proposition.
