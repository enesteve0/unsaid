# Feedback on Nebius Token Factory, Nebius AI Cloud and NVIDIA models

Written while building Unsaid (Oct 26–30, 2026). Every item was reproduced by us, and each has steps to reproduce it.
Items are ordered by how much time they cost us.

## NVIDIA models and the NVIDIA API catalog (build.nvidia.com)

We prototyped prompts on build.nvidia.com before our Token Factory account was ready. These notes concern that API,
not Token Factory.

1. **Intermittent bare 500s and stalled requests on Nemotron 3.5 Super VL.** Our perception request to
   `nvidia/nemotron-3.5-super-vl-120b-a12b` (`POST https://integrate.api.nvidia.com/v1/chat/completions`: a 40-second
   clip, three stills and the JSON schema in the prompt, about 6,100 prompt tokens, thinking off) usually returns in
   8–14 s. Sometimes the identical request instead:
   - returns `HTTP 500 {"message": "Failed to generate completions"}` within 1–2 s, often in bursts: three
     concurrent requests failed within 30 ms of each other, and one request failed three times in a row within a few
     seconds. Repeated minutes later, the same requests succeeded, apart from the stalls below;
   - or sends nothing at all: four requests had no response after 60–240 s, and their retries finished in about
     10 s.

   We first took one of these 500s for a `json_schema` limitation with image input and reported it as such here.
   Repeated tests (4 of 4 successful with an image and strict `json_schema`) showed that it is intermittent, so we
   withdrew that report. Our client now retries a 5xx once after 5 s and streams every call, so a stalled request is
   cut off after 60 s without a chunk instead of after the whole 180 s budget.
   *Suggestion:* answer capacity problems with 503 and `Retry-After`, so they can't be mistaken for a bad request,
   and include a request ID in error bodies.

2. **A model listed in `/v1/models` that the account cannot call.** `nvidia/nemotron-nano-3-30b-a3b` appears in
   `GET /v1/models`, but chat completions return
   `404 {"detail": "Function '...': Not found for account '...'"}`.
   *Suggestion:* list only models the key can call, or mark entitlement in the listing.

3. **Long reasoning calls hit gateway timeouts unless streamed.** Nemotron 3 Ultra with thinking on and a
   24k-token budget returned `HTTP 504` on a non-streamed request; the same request with `stream: true` completed
   in about 6.5 minutes. *Suggestion:* document "stream reasoning calls" next to the reasoning examples, or raise the
   gateway timeout for reasoning models.

4. **Reasoning length can be controlled, but only through an undocumented template flag.** On
   `nvidia/nemotron-3-ultra-550b-a55b`, `thinking_token_budget` returns
   `400 {"message": "Validation: Unsupported parameter(s): thinking_token_budget"}`. `reasoning_effort: "low"` is
   accepted, but a single test showed no clear effect. The chat template's `medium_effort` flag
   (`chat_template_kwargs: {"enable_thinking": true, "medium_effort": true}`) does work: over four runs each of the
   same planning puzzle, Ultra wrote a median of 1,478 tokens instead of 2,794, two to three times faster, with the
   same correct answer every time. *Suggestion:* document the effort flags per model, and accept a token budget.

5. **Model IDs differ between the NVIDIA catalog and Token Factory.**
   - Nano is `nvidia/nemotron-nano-3-30b-a3b` on build.nvidia.com but `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` on Token
     Factory.
   - Lightning is `nvidia/nemotron-3.5-lightning-30b-a3b` versus `nvidia/Nemotron-3_5-Lightning`.
   
   Moving a prototype between the two is a lookup-table exercise. *Suggestion:* a published alias table, or
   accepting the NVIDIA catalog IDs as aliases on Token Factory.

6. **Usage does not report reasoning tokens for Ultra.** Streamed and non-streamed responses from
   `nvidia/nemotron-3-ultra-550b-a55b` contain only `prompt_tokens`, `completion_tokens` and `total_tokens`, with no
   `completion_tokens_details.reasoning_tokens`, although the reasoning arrives in `reasoning_content`. Costs can
   still be tracked, because reasoning is counted in `completion_tokens`, but not how much of a call was thinking.
   *Suggestion:* fill `completion_tokens_details.reasoning_tokens`, which the OpenAI-compatible schema provides for.

7. **Video understanding without audio.** Nemotron 3.5 Super VL reads slides, charts and actions well, but it has no
   audio input, so any task that depends on *when people speak* needs a separate speech model. We run NVIDIA Parakeet
   TDT 0.6B v2 on CPU for that. A vision-language model that also hears (Nemotron 3 Nano Omni was retired from Token
   Factory on Aug 31, 2026) would remove a whole stage.

8. **Word timestamps for Parakeet on CPU.** The community ONNX export we use returns token start times on an 80 ms grid,
   with no end times. *Suggestion:* official ONNX exports of Parakeet with word-level start and end times would make
   timing-sensitive accessibility work much easier.

## Nebius Token Factory

1. **Trial credit we could not see.** The billing docs say a first sign-up receives $1 of trial credit for 30
   days. On an account created and set up for billing on Oct 29, 2026, the console showed an account balance of
   $0.00, and the transaction list for October was empty. A participant who must not spend money cannot tell
   whether a first call will be free. *Suggestion:* show the trial credit and its expiry next to the balance.
2. **The hackathon activation code looks like a promo code, but is not one.** The Devpost resources page lists
   `NEBIUS-DEVPOST-GLOBAL26` for "$25 Token Factory credits". Entered in the console under Top up balance → With
   promo code, it returns "Invalid promo code. Please check the promo code symbols". It belongs to a separate form
   that emails a promo code, and that form works only when opened from the Devpost link, whose URL carries the event
   and the activation code. Opened as plain nebius.com/promo-code, it takes all the personal details and only then
   shows "Error: no event name found". Filled in again from the Devpost link on Oct 30, the deadline day, it
   answered "Form submitted", and a minute later an email said the promo code "could not be issued because the
   event in your request was incorrect". *Suggestion:* say "activation code, not a promo code" next to the console
   field, or accept event activation codes there directly; have the form ask for the event code before anyone fills
   it in, when the link has none; and check that the event code in the official link is accepted before it is
   published.
3. **Support only on Discord.** For credits that never arrive, the hackathon FAQ sends participants to the Nebius
   Discord. Discord is not accessible from Turkey, and the forum shows others waiting four to five days there. With
   no credit and no reachable support, this entry made no Token Factory inference call at all: every run used the
   same Nemotron models on NVIDIA's API catalog, at no cost. *Suggestion:* an email or console support path for
   credit problems, and a small hackathon credit granted automatically with the first API key.
4. **No hard spending limit.** Billing requires a card, and once the balance is negative the card is charged
   automatically, at the start of the month or at a threshold. For students and hackathon participants, a hard
   cap ("stop serving at $X") would make trying the API risk-free. Until then, our app enforces its own caps.
5. **What worked at once:** `GET /v1/models` with a new key listed all five NVIDIA models Unsaid uses, with the IDs
   our fallback chains expect.

## Nebius AI Cloud (Serverless Endpoints and Jobs)

*(Added after deployment.)*

## What worked well

- One OpenAI-compatible API for every Nemotron size made routing a configuration change.
- Super VL reads slide text, axis labels and values reliably from full-resolution stills, and handles a low-frame-rate
  clip together with several stills in one request.
- Ultra holding a whole lecture in one context produced better plans than any amount of local rewriting by smaller
  models.

## What we hope to see next from the Nemotron team

- A vision-language model with audio input, so lecture and meeting video can be understood from one model.
- Turkish and other languages in Nemotron 3.x, so accessibility tools are not English-only.
- Documented reasoning controls (thinking on/off, budgets, effort levels), with an error instead of HTTP 200 and empty
  content when a budget is too small.
