export const STAGES = [
  { key: 'listen', label: 'Listen', model: 'NVIDIA Parakeet TDT 0.6B · CPU', text: 'Transcribes the lecture with word timings and finds every silence.' },
  { key: 'segment', label: 'Segment', model: 'Code', text: 'Splits the video at slide changes and flags phrases like “as you can see” or “this curve”.' },
  { key: 'watch', label: 'Watch', model: 'Nemotron 3.5 Super VL', text: 'Watches each segment and reads slides, charts, equations and actions, with times.' },
  { key: 'resolve', label: 'Resolve', model: 'Nemotron 3 Nano', text: 'Decides what each “this” or “here” actually points at, and what the speech leaves out.' },
  { key: 'context', label: 'Context', model: 'Tavily', text: 'Looks up names from the video’s own page and works cited on slides, so names are never guessed.' },
  { key: 'understand', label: 'Understand', model: 'Nemotron 3 Ultra', text: 'Reads the whole lecture at once and plans what is unsaid, how important it is and which silence it fits.' },
  { key: 'write', label: 'Write & fit', model: 'Nemotron 3.5 Lightning + code gates', text: 'Writes each description; code rejects anything too long, spoken over, or with numbers and names not on screen.' },
  { key: 'check', label: 'Check', model: 'Nemotron 3.5 Super VL', text: 'Looks at the frames again and checks every claim in every description.' },
  { key: 'deliver', label: 'Deliver', model: 'Code + Lightning', text: 'Description track, captions, transcript, editor markers, and tips for the lecturer.' },
] as const
