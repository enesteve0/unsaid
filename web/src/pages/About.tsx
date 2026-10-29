import { STAGES } from '../lib/stages'

export function About() {
  return (
    <article style={{ paddingTop: 48, maxWidth: 860 }} aria-labelledby="about-title">
      <p className="eyebrow">How it works</p>
      <h1 id="about-title" style={{ fontSize: 'clamp(2.4rem, 5vw, 4.2rem)' }}>
        Models write. Code decides.
      </h1>

      <section style={{ paddingTop: 36 }}>
        <h2 style={{ fontSize: '2rem' }}>The problem</h2>
        <p>
          Audio description (AD) is the narration that tells blind and low-vision viewers what is on screen. WCAG 2.1 level AA
          requires it for prerecorded video (success criterion 1.2.5), and US public universities must meet that standard from
          April 2027 under the ADA Title II rule. Lectures are hard: speakers say “as you can see, this curve…” and the curve is
          the lesson. In a study of 90 presentation videos, 72% of 610 visual elements were insufficiently described by the
          speaker (Peng et al., CHI 2021).
        </p>
      </section>

      <section style={{ paddingTop: 36 }}>
        <h2 style={{ fontSize: '2rem' }}>The pipeline</h2>
        <ol>
          {STAGES.map((s) => (
            <li key={s.key} style={{ marginBottom: 10 }}>
              <strong>{s.label}</strong> <span className="mono amber">({s.model})</span>: {s.text}
            </li>
          ))}
        </ol>
        <p>
          Every model call goes through Nebius Token Factory. Each call is logged with its tokens, cached tokens, latency and
          cost, so every description has a price and a reason.
        </p>
      </section>

      <section style={{ paddingTop: 36 }}>
        <h2 style={{ fontSize: '2rem' }}>Rules enforced in code</h2>
        <ul>
          <li>A description starts inside a silence and must finish before the lecturer speaks again, with a guard band.</li>
          <li>Planned at 2.5 words per second, slower than normal speech, as describers recommend.</li>
          <li>No number that is not printed on screen; no name that is not on screen, in the speech or on the video’s own page.</li>
          <li>No “we see”, “the image shows” or “in this video”; present tense; hedges are flagged for review.</li>
          <li>
            If nothing fits, the description becomes extended: the player pauses the video (WCAG 1.2.7), but only for essential
            facts or what the speaker points at. Anything else is left out rather than squeezed into a fragment.
          </li>
          <li>A description says what the picture shows, not only what kind of picture it is: “Title card shows title.” fails.</li>
          <li>A description that still breaks a rule after two repairs is held back, unspoken, until a person fixes it in the editor.</li>
          <li>People are never identified from their faces. A description that names someone without a source is withheld.</li>
          <li>If the frame check finds a claim the picture contradicts, the description is corrected and checked again; if that fails, it waits for a person.</li>
        </ul>
      </section>

      <section style={{ paddingTop: 36 }}>
        <h2 style={{ fontSize: '2rem' }}>Prior work we build on</h2>
        <ul>
          <li>
            <em>Say It All</em> (Peng et al., CHI 2021) gives presenters feedback on slide content they did not describe. Unsaid’s
            lecturer tips extend that idea to any recorded video.
          </li>
          <li>
            <em>Slidecho</em> (ASSETS 2021) aligns slides with speech to flag undescribed slide elements; <em>VeasyGuide</em>{' '}
            (ASSETS 2025) magnifies what instructors point at for low-vision learners.
          </li>
          <li>
            <em>Deictic</em> (2026) resolves “this” in lecture captions for caption users. Unsaid applies the same insight to
            spoken audio description for blind viewers.
          </li>
          <li>
            Commercial AI description (ViddyScribe, 3Play Media, Verbit, YuJa) describes scenes at $0.90 to $9 per minute. Unsaid
            focuses on the moments the speech points at, enforces timing and grounding in code, and shows every cost.
          </li>
        </ul>
      </section>

      <section style={{ paddingTop: 36 }}>
        <h2 style={{ fontSize: '2rem' }}>Limits</h2>
        <ul>
          <li>Descriptions are drafts with checks. A person should review anything marked “needs review” before publishing.</li>
          <li>English only: the Nemotron models used here do not support other languages yet.</li>
          <li>Math notation is read as printed; complex derivations need a human describer.</li>
          <li>Live runs take clips up to 3 minutes; longer lectures go to the overnight backlog job, built for Nebius Serverless Jobs.</li>
        </ul>
      </section>

      <section style={{ paddingTop: 36 }}>
        <h2 style={{ fontSize: '2rem' }}>Credits</h2>
        <p>
          Models: NVIDIA Nemotron 3 Ultra, Nemotron 3.5 Super VL, Nemotron 3.5 Lightning and Nemotron 3 Nano on Nebius Token
          Factory; NVIDIA Parakeet TDT 0.6B v2 (CC-BY-4.0) via onnx-asr. Typeface Atkinson Hyperlegible Next by the Braille
          Institute. Example videos are credited on their pages.
        </p>
      </section>
    </article>
  )
}
