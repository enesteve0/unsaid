# Feedback on Nebius Token Factory, Nebius AI Cloud and NVIDIA models

Written while building Unsaid (Oct 26–30, 2026). Every item was reproduced by us, and each has steps to reproduce it.
Items are ordered by how much time they cost us.

## NVIDIA models and the NVIDIA API catalog (build.nvidia.com)

We prototyped prompts on build.nvidia.com before our Token Factory account was ready. These notes concern that API,
not Token Factory.

1. **Strict structured output fails on Nemotron 3.5 Super VL with image input.**
   `POST https://integrate.api.nvidia.com/v1/chat/completions` with `model: nvidia/nemotron-3.5-super-vl-120b-a12b`,
   one `image_url` data URL, `chat_template_kwargs.enable_thinking: false` and
   `response_format: {type: json_schema, json_schema: {strict: true, schema: {...}}}` returns
   `HTTP 500 {"message": "Failed to generate completions"}` in under a second. The same request without
   `response_format` returns valid JSON when the schema is in the prompt. Our client now retries without constrained
   decoding when a server error follows a `json_schema` request, and remembers that for the model.
   *Suggestion:* return a 400 that names the unsupported parameter, or support `json_schema` for multimodal input.

2. **A model listed in `/v1/models` that the account cannot call.** `nvidia/nemotron-nano-3-30b-a3b` appears in
   `GET /v1/models`, but chat completions return
   `404 {"detail": "Function '...': Not found for account '...'"}`.
   *Suggestion:* list only models the key can call, or mark entitlement in the listing.

3. **Long reasoning calls hit gateway timeouts unless streamed.** Nemotron 3 Ultra with thinking on and a
   24k-token budget returned `HTTP 504` on a non-streamed request; the same request with `stream: true` completed
   in about 6.5 minutes. *Suggestion:* document "stream reasoning calls" next to the reasoning examples, or raise the
   gateway timeout for reasoning models.

4. **Model IDs differ between the NVIDIA catalog and Token Factory.**
   - Nano is `nvidia/nemotron-nano-3-30b-a3b` on build.nvidia.com but `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` on Token
     Factory.
   - Lightning is `nvidia/nemotron-3.5-lightning-30b-a3b` versus `nvidia/Nemotron-3_5-Lightning`.
   
   Moving a prototype between the two is a lookup-table exercise. *Suggestion:* a published alias table, or
   accepting the NVIDIA catalog IDs as aliases on Token Factory.

5. **Video understanding without audio.** Nemotron 3.5 Super VL reads slides, charts and actions well, but it has no
   audio input, so any task that depends on *when people speak* needs a separate speech model. We run NVIDIA Parakeet
   TDT 0.6B v2 on CPU for that. A vision-language model that also hears (Nemotron 3 Nano Omni was retired from Token
   Factory on Aug 31, 2026) would remove a whole stage.

6. **Word timestamps for Parakeet on CPU.** The community ONNX export we use returns token start times on an 80 ms grid,
   with no end times. *Suggestion:* official ONNX exports of Parakeet with word-level start and end times would make
   timing-sensitive accessibility work much easier.

## Nebius Token Factory

*(Added after testing with our Token Factory key; only reproduced items are listed.)*

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
