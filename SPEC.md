# Crash Detection & Emergency Alert App — Specification (Draft v0.1)

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
3. **Notify emergency services**:
   - Needs a decision: can the app call 911/local equivalent directly (see
     Open Questions §8), or does it hand off to the phone's native dialer
     with pre-filled info, or route through a third-party ERS
     (emergency-response-service) API/human dispatch center (similar to how
     Apple Watch Crash Detection / Android Car Crash Detection route through
     a service, or how ADT/RapidSOS-style APIs work)?
   - Recommendation: integrate with a service like RapidSOS (US) or an
     equivalent regional emergency-data platform, which can push structured
     crash data directly to 911 dispatch centers, rather than trying to
     "auto-dial 911" from the app (many countries restrict or complicate
     autodialing emergency numbers).
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

**Android**
- Foreground service with persistent notification required to reliably keep
  sensors + GPS + mic running in the background.
- Must guide users to disable battery optimization / "unrestricted battery"
  for the app (manufacturer-specific quirks: Samsung, Xiaomi, Huawei
  aggressively kill background apps).
- Can potentially auto-dial emergency numbers with `CALL_PHONE` permission
  (Android allows apps to call emergency numbers directly, unlike iOS).

**iOS**
- No true persistent background microphone/accelerometer sampling at full
  rate indefinitely — need to use significant-location-change, Core Motion
  background modes, and possibly the `background audio` or `location`
  background modes creatively; continuous raw mic access in background is
  heavily restricted.
- Cannot programmatically dial 911 from a third-party app — can only present
  the system call UI (`tel://`) which still requires user confirmation, or
  integrate with CallKit/an emergency-services API/data provider instead of
  direct dialing.
- Apple already ships Crash Detection (iPhone 14+) at the OS level — worth
  clarifying how this app differentiates or whether it should detect on
  older devices / Android where OS-level crash detection doesn't exist.

These constraints likely mean **the sound/mic-based signal and always-on
raw sensor sampling are realistically an Android-first capability**, with
iOS relying more on Core Motion + location fusion and possibly integrating
with Apple's own crash detection signal if exposed via API (it currently
isn't, publicly). This is an important open question — see §8.

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

## 8. Open Questions (need your input before detailed design)

I'll ask these as structured questions next, but listing them here for the
spec's completeness:

1. Platform priority: iOS, Android, or both from v1?
2. How should "notify emergency services" actually work — direct 911 dial,
   handoff to native dialer, or third-party dispatch-data API (e.g.
   RapidSOS-style)? This has real legal/liability implications.
3. What's the MVP scope — just crash detection + contact alerting, or do you
   also want emergency services integration in v1?
4. Do you have existing brand/product name, design assets, or is this
   greenfield?
5. Any target regions/countries (affects emergency number, carrier SMS
   fallback, regulations)?
6. Should the app also do live trip tracking/sharing outside of crash
   scenarios (e.g., "share my drive" like Life360), or purely dormant until
   a crash?
7. Who is legally responsible if the app fails to detect a real crash, or
   falsely alerts services repeatedly (false-alarm liability with 911
   dispatch is a real regulatory concern in some jurisdictions)?
8. Budget/timeline and team (solo dev, small team) — affects how ambitious
   v1 should be (e.g., ML crash classifier vs. simple thresholding first).

## 9. Suggested MVP (v0.1) Scope

To de-risk this, a leaner first version:
- Android-first (fewer background restrictions) or iOS using Core Motion +
  location only (skip mic in v1 to sidestep iOS mic-background limits).
- Threshold-based detection (acceleration spike + speed drop), no ML yet.
- Cancellation countdown UI.
- SMS-based emergency contact alerting (via a backend like Twilio) with a
  location link — no direct 911 integration yet (rely on contacts to call
  911 if needed, or present a one-tap "Call 911" button post-alert instead
  of auto-dialing).
- Manual "start/stop drive" toggle rather than automatic trip detection,
  to start.
- Iterate toward automatic trip detection, mic-based corroboration, and
  emergency-service API integration in v2+.
