from __future__ import annotations

import json
from pathlib import Path


def build_review_html(payload: dict) -> str:
    data_json = json.dumps(payload, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{payload["title"]}</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --panel: rgba(255,255,255,0.82);
      --ink: #1d1a16;
      --muted: #6f6557;
      --accent: #0d7a5f;
      --accent-soft: #d8f2e7;
      --ayah: #faf7f2;
      --active: #ffe7a8;
      --selected: #a8ddff;
      --border: rgba(36, 29, 21, 0.12);
      --shadow: 0 18px 50px rgba(38, 30, 20, 0.08);
      --score-good: #d8f2e7;
      --score-mid: #ffe7a8;
      --score-bad: #f9c6bd;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Iowan Old Style", "Palatino Linotype", serif;
      background:
        radial-gradient(circle at top left, rgba(13,122,95,0.16), transparent 28%),
        radial-gradient(circle at bottom right, rgba(175,101,39,0.16), transparent 30%),
        linear-gradient(180deg, #f8f4eb 0%, #f1eadf 100%);
      color: var(--ink);
    }}
    .shell {{
      max-width: 1360px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      gap: 18px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 22px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(10px);
    }}
    .hero, .player, .text-panel, .side-panel {{
      padding: 20px 24px;
    }}
    h1, h2, h3 {{
      margin: 0;
      line-height: 1.1;
      align-self: start;
    }}
    .meta, .controls, .selected-controls, .toggles {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .meta, .info, .timing {{
      color: var(--muted);
      font-size: 0.95rem;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      background: var(--accent);
      color: white;
      cursor: pointer;
      font: inherit;
    }}
    button.secondary {{
      background: #e6efe9;
      color: #14382f;
    }}
    button:disabled {{
      opacity: 0.55;
      cursor: default;
    }}
    audio {{ width: 100%; }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.8fr) minmax(340px, 1fr);
      gap: 18px;
    }}
    .text-panel {{
      display: grid;
      gap: 16px;
    }}
    .ayah {{
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      background: var(--ayah);
    }}
    .ayah-head {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: baseline;
      color: var(--muted);
      margin-bottom: 12px;
    }}
    .ayah-body {{
      direction: rtl;
      text-align: right;
      font-size: 1.8rem;
      line-height: 2.2;
    }}
    .word {{
      border-radius: 10px;
      padding: 0.08em 0.25em;
      cursor: pointer;
      transition: background-color 120ms ease, opacity 120ms ease;
      display: inline-block;
    }}
    .word.active {{ outline: 2px solid rgba(13,122,95,0.4); }}
    .word.selected {{ box-shadow: inset 0 0 0 2px rgba(55,101,176,0.55); }}
    .word.score-good {{ background: var(--score-good); }}
    .word.score-mid {{ background: var(--score-mid); }}
    .word.score-bad {{ background: var(--score-bad); }}
    .word.only-suspicious-hidden {{ display: none; }}
    .word.suspicious {{ text-decoration: underline dotted rgba(29,26,22,0.55); }}
    .side-panel {{
      display: grid;
      gap: 16px;
      align-content: start;
    }}
    .selected-box, .summary-box {{
      border: 1px solid rgba(13,122,95,0.18);
      background: rgba(255,255,255,0.66);
      border-radius: 18px;
      padding: 16px;
      display: grid;
      gap: 10px;
    }}
    .decoder-box {{
      border: 1px solid rgba(13,122,95,0.18);
      background: rgba(255,255,255,0.66);
      border-radius: 18px;
      padding: 16px;
      display: grid;
      gap: 10px;
    }}
    .log-box {{
      border: 1px solid rgba(13,122,95,0.18);
      background: rgba(255,255,255,0.66);
      border-radius: 18px;
      padding: 16px;
      display: grid;
      gap: 10px;
    }}
    .comparison-box {{
      border: 1px solid rgba(13,122,95,0.18);
      background: rgba(255,255,255,0.66);
      border-radius: 18px;
      padding: 16px;
      display: grid;
      gap: 10px;
    }}
    .comparison-scroll {{
      overflow-x: auto;
      overflow-y: hidden;
      border: 1px solid var(--border);
      background: rgba(255,255,255,0.5);
      border-radius: 16px;
      padding: 10px;
    }}
    .comparison-inner {{
      display: grid;
      gap: 10px;
      min-width: 100%;
    }}
    .track-controls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .track-row {{
      display: grid;
      gap: 4px;
    }}
    .track-label {{
      font-size: 0.92rem;
      color: var(--muted);
    }}
    .timeline {{
      position: relative;
      height: 52px;
      background: linear-gradient(180deg, rgba(13,122,95,0.06), rgba(13,122,95,0.02));
      border: 1px solid var(--border);
      overflow: hidden;
    }}
    .timeline-word {{
      position: absolute;
      top: 6px;
      height: 38px;
      border-radius: 0;
      padding: 2px 4px;
      font-size: 0.82rem;
      line-height: 1.2;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      cursor: pointer;
      border: 1px solid rgba(29,26,22,0.08);
    }}
    .timeline-word.selected {{
      box-shadow: inset 0 0 0 2px rgba(55,101,176,0.55);
    }}
    .timeline-word.active {{
      outline: 2px solid rgba(13,122,95,0.4);
    }}
    .selected-word {{
      direction: rtl;
      text-align: right;
      font-size: 2rem;
    }}
    .list {{
      max-height: 24vh;
      overflow: auto;
      display: grid;
      gap: 8px;
    }}
    .list-row, .ayah-row {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(255,255,255,0.6);
    }}
    .decoder-grid {{
      display: grid;
      gap: 8px;
    }}
    .log-row {{
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 10px 12px;
      background: rgba(255,255,255,0.6);
      display: grid;
      gap: 6px;
    }}
    .log-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
      font-size: 0.95rem;
    }}
    .log-row code {{
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 0.82rem;
      background: rgba(29,26,22,0.04);
      padding: 6px 8px;
      display: block;
    }}
    .decision-accepted {{ color: #0b6b52; font-weight: 600; }}
    .decision-rejected {{ color: #a2422a; font-weight: 600; }}
    .ayah-list {{
      max-height: 28vh;
      overflow: auto;
      display: grid;
      gap: 10px;
    }}
    .ayah-row.active {{
      border-color: rgba(13,122,95,0.55);
      background: rgba(216,242,231,0.85);
    }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 8px;
      font-size: 0.8rem;
      background: rgba(13,122,95,0.1);
      color: #14382f;
    }}
    .analysis-panel {{
      padding: 20px 24px;
      display: grid;
      gap: 16px;
    }}
    .analysis-grid {{
      display: grid;
      grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.6fr);
      gap: 16px;
    }}
    .analysis-controls {{
      display: grid;
      gap: 12px;
      align-content: start;
    }}
    .analysis-chart-grid {{
      display: grid;
      gap: 12px;
    }}
    .analysis-chart-wrap {{
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 10px;
      background: rgba(255,255,255,0.66);
    }}
    .analysis-chart-wrap svg {{
      display: block;
      background: #fff;
    }}
    .analysis-empty {{
      color: var(--muted);
      border: 1px dashed var(--border);
      border-radius: 14px;
      padding: 12px;
      background: rgba(255,255,255,0.5);
    }}
    .range-box {{
      border: 1px solid rgba(13,122,95,0.18);
      background: rgba(255,255,255,0.66);
      border-radius: 18px;
      padding: 14px;
      display: grid;
      gap: 10px;
    }}
    .range-box input[type="range"] {{
      width: 100%;
    }}
    .range-box input[type="number"] {{
      width: 100%;
      max-width: 120px;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid var(--border);
      font: inherit;
    }}
    @media (max-width: 920px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .ayah-body {{ font-size: 1.55rem; }}
      .analysis-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="card hero">
      <h1>{payload["title"]}</h1>
      <div class="meta">
        <span>Surah {payload["surah_number"]}</span>
        <span>Backend: {payload["backend"]}</span>
        <span>Normalization: {payload["normalization_profile"]}</span>
        <span>Audio: {payload["audio"]["duration_label"]}</span>
      </div>
      <div class="toggles">
        <label><input id="show-suspicious-only" type="checkbox" {"checked" if payload["ui"]["show_suspicious_only"] else ""}> Show only suspicious words</label>
      </div>
    </section>

    <section class="card player">
      <audio id="audio" controls preload="metadata">
        <source src="{payload["audio"]["relative_path"]}" type="audio/mpeg" />
      </audio>
      <div class="controls">
        <button id="play-all">Play from start</button>
        <button id="play-selected" disabled>Play selected</button>
        <button id="play-selected-pre" class="secondary" disabled>Play 1s before</button>
      </div>
      <div class="timing" id="playback-status">00:00.000 / {payload["audio"]["duration_label"]}</div>
    </section>

    <div class="layout">
      <section class="card text-panel">
        <h2>Full Surah</h2>
        <div class="comparison-box">
          <h3>Alignment Comparison</h3>
          <div class="info" id="comparison-title">Full audio comparison</div>
          <div class="track-controls">
            <button id="zoom-out" class="secondary">Zoom out</button>
            <button id="zoom-reset" class="secondary">Reset zoom</button>
            <button id="zoom-in">Zoom in</button>
            <span class="info" id="zoom-label">Ribbon zoom: 1.0x</span>
          </div>
          <div class="comparison-scroll" id="comparison-scroll">
            <div class="comparison-inner" id="comparison-inner">
              <div class="track-row">
                <div class="track-label">Before refinement</div>
                <div class="timeline" id="before-timeline"></div>
              </div>
              <div class="track-row">
                <div class="track-label">After refinement</div>
                <div class="timeline" id="after-timeline"></div>
              </div>
            </div>
          </div>
        </div>
        <div id="surah-root"></div>
      </section>

      <aside class="card side-panel">
        <div class="selected-box">
          <div class="info">Selected word</div>
          <div class="selected-word" id="selected-word">Nothing selected yet</div>
          <div class="timing" id="selected-time">Click any word to inspect its alignment.</div>
          <div class="info" id="selected-score">Score: -</div>
          <div class="info" id="selected-flags">Flags: -</div>
          <div class="selected-controls">
            <button id="jump-selected" class="secondary" disabled>Jump to word</button>
          </div>
        </div>

        <div class="summary-box">
          <h3>Quality</h3>
          <div class="info">Coverage: {(payload["quality"]["coverage"] * 100):.1f}%</div>
          <div class="info">Avg confidence: {(payload["quality"]["average_word_score"] * 100):.1f}%</div>
          <div class="info">Low-score ratio: {(payload["quality"]["low_score_ratio"] * 100):.1f}%</div>
          <div class="info">Gap count: {payload["quality"]["gap_count"]}</div>
          <div class="info">Warnings: {", ".join(payload["quality"]["warnings"]) if payload["quality"]["warnings"] else "None"}</div>
        </div>

        <div class="summary-box">
          <h3>Worst 20 Words</h3>
          <div class="list" id="worst-word-list"></div>
        </div>

        <div class="summary-box">
          <h3>Largest 20 Gaps</h3>
          <div class="list" id="gap-list"></div>
        </div>

        <div class="summary-box">
          <h3>Lowest-Score Ayahs</h3>
          <div class="list" id="lowest-ayah-list"></div>
        </div>

        <div class="decoder-box">
          <h3>Decoder</h3>
          <div class="decoder-grid" id="decoder-summary"></div>
        </div>

        <div class="decoder-box">
          <h3>Phrase Trace</h3>
          <div class="list" id="phrase-trace-list"></div>
        </div>

        <div class="decoder-box">
          <h3>Word Runs</h3>
          <div class="list" id="word-run-list"></div>
        </div>

        <div class="decoder-box">
          <h3>Repeated Occurrences</h3>
          <div class="list" id="occurrence-list"></div>
        </div>

        <div class="log-box">
          <h3>Refinement Logs</h3>
          <div class="info" id="refinement-summary"></div>
          <div class="list" id="refinement-log-list"></div>
        </div>

        <div>
          <h2>Ayah timings</h2>
          <div class="ayah-list" id="ayah-list"></div>
        </div>
      </aside>
    </div>

    <section class="card analysis-panel">
      <h2>Region Analysis</h2>
      <div class="info">Select an audio region and a text range, then inspect the sliced score matrix, DP matrix, path, and playback here.</div>
      <div class="analysis-grid">
        <div class="analysis-controls">
          <div class="range-box">
            <h3>Audio Region</h3>
            <label>Start</label>
            <input id="analysis-start-ms" type="range" min="0" max="{payload["audio"]["duration_ms"]}" value="0" step="1" />
            <label>End</label>
            <input id="analysis-end-ms" type="range" min="0" max="{payload["audio"]["duration_ms"]}" value="{payload["audio"]["duration_ms"]}" step="1" />
            <div class="controls">
              <button id="analysis-set-start" class="secondary">Set start from audio</button>
              <button id="analysis-set-end" class="secondary">Set end from audio</button>
              <button id="analysis-play-region">Play analysis region</button>
            </div>
            <div class="info" id="analysis-audio-summary"></div>
          </div>
          <div class="range-box">
            <h3>Text Region</h3>
            <div class="controls">
              <label>Start word</label>
              <input id="analysis-word-start" type="number" min="1" max="{len(payload["words"])}" value="1" step="1" />
              <label>End word</label>
              <input id="analysis-word-end" type="number" min="1" max="{len(payload["words"])}" value="{len(payload["words"])}" step="1" />
            </div>
            <div class="controls">
              <button id="analysis-use-selected-start" class="secondary" disabled>Use selected as start</button>
              <button id="analysis-use-selected-end" class="secondary" disabled>Use selected as end</button>
            </div>
            <div class="info" id="analysis-word-summary"></div>
          </div>
          <div class="range-box">
            <h3>Selection</h3>
            <div class="info" id="analysis-selection-summary"></div>
            <div class="info">Click words above to select them, then use the buttons here to anchor the text range.</div>
          </div>
        </div>
        <div class="analysis-chart-grid">
          <div class="analysis-empty" id="analysis-empty">Decoder debug matrices are required for this view. Re-run the full alignment with the current code if this message remains.</div>
          <div class="analysis-chart-wrap">
            <h3>Score Matrix Slice</h3>
            <div class="info">Local bucket-to-state match scores for the selected region.</div>
            <div id="analysis-score-chart"></div>
          </div>
          <div class="analysis-chart-wrap">
            <h3>DP Matrix Slice</h3>
            <div class="info">Cumulative best-prefix DP scores for the same selected region.</div>
            <div id="analysis-dp-chart"></div>
          </div>
          <div class="analysis-chart-wrap">
            <h3>Silence Score Slice</h3>
            <div class="info">Bucket-specific silence scores derived from the CTC blank label.</div>
            <div id="analysis-silence-chart"></div>
          </div>
        </div>
      </div>
    </section>
  </div>

  <script id="alignment-data" type="application/json">{data_json}</script>
  <script>
    const data = JSON.parse(document.getElementById('alignment-data').textContent);
    const audio = document.getElementById('audio');
    const surahRoot = document.getElementById('surah-root');
    const ayahList = document.getElementById('ayah-list');
    const selectedWordEl = document.getElementById('selected-word');
    const selectedTimeEl = document.getElementById('selected-time');
    const selectedScoreEl = document.getElementById('selected-score');
    const selectedFlagsEl = document.getElementById('selected-flags');
    const playbackStatusEl = document.getElementById('playback-status');
    const playAllBtn = document.getElementById('play-all');
    const playSelectedBtn = document.getElementById('play-selected');
    const playSelectedPreBtn = document.getElementById('play-selected-pre');
    const jumpSelectedBtn = document.getElementById('jump-selected');
    const showSuspiciousOnlyInput = document.getElementById('show-suspicious-only');
    const worstWordList = document.getElementById('worst-word-list');
    const gapList = document.getElementById('gap-list');
    const lowestAyahList = document.getElementById('lowest-ayah-list');
    const decoderSummary = document.getElementById('decoder-summary');
    const phraseTraceList = document.getElementById('phrase-trace-list');
    const wordRunList = document.getElementById('word-run-list');
    const occurrenceList = document.getElementById('occurrence-list');
    const refinementSummary = document.getElementById('refinement-summary');
    const refinementLogList = document.getElementById('refinement-log-list');
    const beforeTimeline = document.getElementById('before-timeline');
    const afterTimeline = document.getElementById('after-timeline');
    const comparisonInner = document.getElementById('comparison-inner');
    const comparisonTitle = document.getElementById('comparison-title');
    const zoomOutBtn = document.getElementById('zoom-out');
    const zoomResetBtn = document.getElementById('zoom-reset');
    const zoomInBtn = document.getElementById('zoom-in');
    const zoomLabel = document.getElementById('zoom-label');
    const analysisStartInput = document.getElementById('analysis-start-ms');
    const analysisEndInput = document.getElementById('analysis-end-ms');
    const analysisWordStartInput = document.getElementById('analysis-word-start');
    const analysisWordEndInput = document.getElementById('analysis-word-end');
    const analysisSetStartBtn = document.getElementById('analysis-set-start');
    const analysisSetEndBtn = document.getElementById('analysis-set-end');
    const analysisPlayRegionBtn = document.getElementById('analysis-play-region');
    const analysisUseSelectedStartBtn = document.getElementById('analysis-use-selected-start');
    const analysisUseSelectedEndBtn = document.getElementById('analysis-use-selected-end');
    const analysisAudioSummary = document.getElementById('analysis-audio-summary');
    const analysisWordSummary = document.getElementById('analysis-word-summary');
    const analysisSelectionSummary = document.getElementById('analysis-selection-summary');
    const analysisEmpty = document.getElementById('analysis-empty');
    const analysisScoreChart = document.getElementById('analysis-score-chart');
    const analysisDpChart = document.getElementById('analysis-dp-chart');
    const analysisSilenceChart = document.getElementById('analysis-silence-chart');

    let selectedWordId = null;
    let activeWordId = null;
    let playUntilSeconds = null;
    let timelineZoom = 1;
    const wordMap = new Map();
    const timelineMap = new Map();
    const decoderDebug = data.decoder.debug || null;
    const decoderAnalysisFiles = data.decoder.analysis_files || {{}};
    const ayahAnalysisCache = window.__QURAN_ALIGNER_AYAH_ANALYSIS || (window.__QURAN_ALIGNER_AYAH_ANALYSIS = {{}});
    const analysisChartState = {{}};

    function formatMs(ms) {{
      const totalSeconds = Math.floor(ms / 1000);
      const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, '0');
      const seconds = String(totalSeconds % 60).padStart(2, '0');
      const millis = String(ms % 1000).padStart(3, '0');
      return `${{minutes}}:${{seconds}}.${{millis}}`;
    }}

    function scoreClass(confidence) {{
      if (confidence >= 0.7) return 'score-good';
      if (confidence >= 0.45) return 'score-mid';
      return 'score-bad';
    }}

    function findActiveWord(timeMs) {{
      return data.words.find((word) => timeMs >= word.start_ms && timeMs < word.end_ms) || null;
    }}

    function findActiveAyah(timeMs) {{
      return data.ayahs.find((ayah) => timeMs >= ayah.start_ms && timeMs < ayah.end_ms) || null;
    }}

    function updateSuspiciousFilter() {{
      const showOnly = showSuspiciousOnlyInput.checked;
      data.words.forEach((word) => {{
        const node = wordMap.get(word.id);
        if (!node) return;
        node.classList.toggle('only-suspicious-hidden', showOnly && !word.is_suspicious);
      }});
    }}

    function renderTimelineWords(container, words, prefix) {{
      container.innerHTML = '';
      const total = Math.max(1, data.audio.duration_ms);
      words.forEach((word) => {{
        const node = document.createElement('div');
        node.className = `timeline-word ${{scoreClass(word.confidence)}}`;
        node.textContent = word.text;
        const left = (word.start_ms / total) * 100;
        const width = Math.max(0.8, ((word.end_ms - word.start_ms) / total) * 100);
        node.style.left = `${{left}}%`;
        node.style.width = `${{width}}%`;
        node.title = `${{word.text}} | ${{formatMs(word.start_ms)}} - ${{formatMs(word.end_ms)}}`;
        node.addEventListener('click', (event) => {{
          selectWordByGlobalIndex(word.global_word_index, true);
          if (event.shiftKey) {{
            playWordSegmentByGlobalIndex(word.global_word_index);
          }}
        }});
        container.appendChild(node);
        timelineMap.set(`${{prefix}}-${{word.global_word_index}}`, node);
      }});
    }}

    function updateTimelineZoom() {{
      comparisonInner.style.width = `${{Math.max(100, timelineZoom * 100)}}%`;
      zoomLabel.textContent = `Ribbon zoom: ${{timelineZoom.toFixed(1)}}x`;
    }}

    function renderComparison() {{
      comparisonTitle.textContent = 'Full audio comparison';
      renderTimelineWords(beforeTimeline, data.comparison.before_words, 'before');
      renderTimelineWords(afterTimeline, data.comparison.after_words, 'after');
    }}

    function renderSummaries() {{
      const decoderRows = [
        `Mode: ${{data.decoder.mode || 'unknown'}}`,
        `Bucket size: ${{data.decoder.bucket_ms || 'n/a'}} ms`,
        `Max repair words: ${{data.decoder.max_repair_words || 'n/a'}}`,
        `Frame path buckets: ${{(data.frame_path || []).length}}`,
        `Collapsed runs: ${{(data.word_runs || []).length}}`,
        `Word occurrences: ${{(data.word_occurrences || []).length}}`,
      ];
      decoderRows.forEach((text) => {{
        const row = document.createElement('div');
        row.className = 'info';
        row.textContent = text;
        decoderSummary.appendChild(row);
      }});

      data.summaries.worst_words.forEach((item) => {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = `${{item.ayah_number}}:${{item.text}} | ${{(item.confidence * 100).toFixed(1)}}%`;
        worstWordList.appendChild(row);
      }});
      data.summaries.largest_gaps.forEach((item) => {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = `${{item.classification}} | ${{formatMs(item.duration_ms)}}`;
        gapList.appendChild(row);
      }});
      data.summaries.lowest_ayahs.forEach((item) => {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = `Ayah ${{item.ayah_number}} | ${{(item.confidence * 100).toFixed(1)}}%`;
        lowestAyahList.appendChild(row);
      }});

      const traceRows = data.decoder.phrase_trace || [];
      if (!traceRows.length) {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = 'No phrase-trace data was recorded.';
        phraseTraceList.appendChild(row);
      }}
      traceRows.forEach((item, index) => {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = `Step ${{index + 1}} | words ${{item.start_word_index}}-${{item.end_word_index}} | buckets ${{item.start_bucket}}-${{item.end_bucket}} | repair width ${{item.repair_width}}`;
        phraseTraceList.appendChild(row);
      }});

      const runRows = data.word_runs || [];
      if (!runRows.length) {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = 'No word runs were generated.';
        wordRunList.appendChild(row);
      }}
      runRows.forEach((item) => {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = `Run ${{item.run_index + 1}} | Ayah ${{item.ayah_number}} | ${{item.text}} | ${{formatMs(item.start_ms)}} - ${{formatMs(item.end_ms)}} | frames ${{item.frame_count}}`;
        wordRunList.appendChild(row);
      }});

      const repeated = (data.word_occurrences || []).filter((item) => item.visit_count > 1);
      if (!repeated.length) {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = 'No repeated word visits were detected.';
        occurrenceList.appendChild(row);
      }}
      repeated.forEach((item) => {{
        const ranges = (item.intervals || [])
          .map((interval) => `${{formatMs(interval.start_ms)}}-${{formatMs(interval.end_ms)}}`)
          .join(', ');
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = `Ayah ${{item.ayah_number}} | ${{item.text}} | visits ${{item.visit_count}} | ${{ranges}}`;
        occurrenceList.appendChild(row);
      }});

      const logs = data.refinement.region_logs || [];
      refinementSummary.textContent = `Changed words: ${{data.refinement.changed_word_count}} | Boundary shift: ${{data.refinement.total_boundary_shift_ms}} ms | Regions tried: ${{logs.length}}`;
      if (!logs.length) {{
        const row = document.createElement('div');
        row.className = 'list-row';
        row.textContent = 'No refinement regions were attempted.';
        refinementLogList.appendChild(row);
      }}
      logs.forEach((item, index) => {{
        const row = document.createElement('div');
        row.className = 'log-row';
        const decisionClass = item.decision === 'accepted' ? 'decision-accepted' : 'decision-rejected';
        const words = (item.words || []).map((word) => word.original_word).join(' ');
        row.innerHTML = `
          <div class="log-head">
            <strong>Region ${{index + 1}}</strong>
            <span class="${{decisionClass}}">${{item.decision || 'unknown'}}</span>
          </div>
          <div class="info">Trigger: words ${{item.trigger_region.start_word_index}}-${{item.trigger_region.end_word_index}} | ${{item.trigger_region.reason}}</div>
          <div class="info">Phrase: words ${{item.phrase_window.start_word_index}}-${{item.phrase_window.end_word_index}} | ${{formatMs(item.phrase_window.start_ms)}} - ${{formatMs(item.phrase_window.end_ms)}} | ${{item.phrase_window.duration_ms}} ms</div>
          <div class="info">Score: ${{item.old_local_score.toFixed(3)}} -> ${{item.new_local_score.toFixed(3)}} | Delta ${{item.score_improvement.toFixed(3)}} | Margin ${{item.acceptance_margin.toFixed(3)}}</div>
          <code>${{words || '(no words)'}}</code>
        `;
        refinementLogList.appendChild(row);
      }});
    }}

    function render() {{
      data.ayahs.forEach((ayah) => {{
        const ayahEl = document.createElement('article');
        ayahEl.className = 'ayah';

        const head = document.createElement('div');
        head.className = 'ayah-head';
        head.innerHTML = `<strong>Ayah ${{ayah.ayah_number}}</strong><span>${{formatMs(ayah.start_ms)}} - ${{formatMs(ayah.end_ms)}}</span>`;

        const body = document.createElement('div');
        body.className = 'ayah-body';
        ayah.words.forEach((word) => {{
          const span = document.createElement('span');
          span.className = `word ${{scoreClass(word.confidence)}}${{word.is_suspicious ? ' suspicious' : ''}}`;
          span.dataset.wordId = String(word.id);
          span.title = `Original: ${{word.text}}\\nNormalized: ${{word.normalized}}\\n${{formatMs(word.start_ms)}} - ${{formatMs(word.end_ms)}}\\nScore: ${{word.score.toFixed(3)}}\\nConfidence: ${{(word.confidence * 100).toFixed(1)}}%\\nFlags: ${{word.flags.join(', ') || 'none'}}`;
          span.textContent = word.text;
          span.addEventListener('click', (event) => {{
            selectWord(word.id, true);
            if (event.shiftKey) {{
              playWordSegment(word);
            }}
          }});
          body.appendChild(span);
          body.appendChild(document.createTextNode(' '));
          wordMap.set(word.id, span);
        }});

        ayahEl.appendChild(head);
        ayahEl.appendChild(body);
        surahRoot.appendChild(ayahEl);

        const row = document.createElement('div');
        row.className = 'ayah-row';
        row.id = `ayah-row-${{ayah.ayah_number}}`;
        row.innerHTML = `<strong>${{ayah.ayah_number}}</strong><div class="timing">${{formatMs(ayah.start_ms)}} - ${{formatMs(ayah.end_ms)}}</div>`;
        row.addEventListener('click', () => {{
          audio.currentTime = ayah.start_ms / 1000;
          audio.play();
        }});
        ayahList.appendChild(row);
      }});
      renderSummaries();
      updateSuspiciousFilter();
    }}

    function setSelectedButtons(enabled) {{
      playSelectedBtn.disabled = !enabled;
      playSelectedPreBtn.disabled = !enabled;
      jumpSelectedBtn.disabled = !enabled;
      analysisUseSelectedStartBtn.disabled = !enabled;
      analysisUseSelectedEndBtn.disabled = !enabled;
    }}

    function selectWord(wordId, scroll) {{
      if (selectedWordId !== null) {{
        wordMap.get(selectedWordId)?.classList.remove('selected');
      }}
      selectedWordId = wordId;
      const word = data.words.find((item) => item.id === wordId);
      const el = wordMap.get(wordId);
      el?.classList.add('selected');
      document.querySelectorAll('.timeline-word.selected').forEach((node) => node.classList.remove('selected'));
      timelineMap.get(`before-${{word.global_word_index}}`)?.classList.add('selected');
      timelineMap.get(`after-${{word.global_word_index}}`)?.classList.add('selected');
      selectedWordEl.textContent = word.text;
      selectedTimeEl.textContent = `${{formatMs(word.start_ms)}} - ${{formatMs(word.end_ms)}} | Ayah ${{word.ayah_number}}`;
      selectedScoreEl.textContent = `Score: ${{word.score.toFixed(3)}} | Confidence: ${{(word.confidence * 100).toFixed(1)}}%`;
      selectedFlagsEl.textContent = `Flags: ${{word.flags.join(', ') || 'none'}}`;
      setSelectedButtons(true);
      const currentRange = normalizedAnalysisWordRange();
      const currentStartWord = data.words[currentRange.start];
      const currentEndWord = data.words[currentRange.end];
      if (!currentStartWord || !currentEndWord || currentStartWord.ayah_number !== currentEndWord.ayah_number) {{
        setAnalysisRangeToAyah(word.ayah_number);
      }}
      if (scroll) {{
        el?.scrollIntoView({{ behavior: 'smooth', block: 'center', inline: 'center' }});
      }}
    }}

    function selectWordByGlobalIndex(globalWordIndex, scroll) {{
      const word = data.words.find((item) => item.global_word_index === globalWordIndex);
      if (!word) return;
      selectWord(word.id, scroll);
    }}

    function playWordSegment(word) {{
      if (!word) return;
      playUntilSeconds = word.end_ms / 1000;
      audio.currentTime = word.start_ms / 1000;
      audio.play();
    }}

    function playWordSegmentByGlobalIndex(globalWordIndex) {{
      const word = data.words.find((item) => item.global_word_index === globalWordIndex);
      playWordSegment(word);
    }}

    function updateActiveWord(timeMs) {{
      const activeWord = findActiveWord(timeMs);
      const previousActive = activeWordId !== null ? data.words.find((item) => item.id === activeWordId) : null;
      if (previousActive && previousActive.id !== activeWord?.id) {{
        wordMap.get(activeWordId)?.classList.remove('active');
        timelineMap.get(`before-${{previousActive.global_word_index}}`)?.classList.remove('active');
        timelineMap.get(`after-${{previousActive.global_word_index}}`)?.classList.remove('active');
      }}
      if (activeWord && activeWord.id !== activeWordId) {{
        wordMap.get(activeWord.id)?.classList.add('active');
        timelineMap.get(`before-${{activeWord.global_word_index}}`)?.classList.add('active');
        timelineMap.get(`after-${{activeWord.global_word_index}}`)?.classList.add('active');
        activeWordId = activeWord.id;
      }} else if (!activeWord) {{
        activeWordId = null;
      }}

      const activeAyah = findActiveAyah(timeMs);
      document.querySelectorAll('.ayah-row.active').forEach((node) => node.classList.remove('active'));
      if (activeAyah) {{
        document.getElementById(`ayah-row-${{activeAyah.ayah_number}}`)?.classList.add('active');
      }}
    }}

    function clampNumber(value, min, max) {{
      return Math.max(min, Math.min(max, value));
    }}

    function compressColumns(matrix, targetCols) {{
      if (!matrix.length || !matrix[0].length || matrix[0].length <= targetCols) {{
        return {{ matrix, ranges: matrix[0] ? matrix[0].map((_, index) => [index, index + 1]) : [] }};
      }}
      const cols = matrix[0].length;
      const step = Math.max(1, Math.ceil(cols / targetCols));
      const ranges = [];
      for (let start = 0; start < cols; start += step) {{
        ranges.push([start, Math.min(cols, start + step)]);
      }}
      const compressed = matrix.map((row) => ranges.map(([start, end]) => {{
        const values = row.slice(start, end).filter((value) => value !== null && Number.isFinite(value));
        if (!values.length) return null;
        return values.reduce((sum, value) => sum + value, 0) / values.length;
      }}));
      return {{ matrix: compressed, ranges }};
    }}

    function finiteValues(matrix) {{
      const values = [];
      matrix.forEach((row) => row.forEach((value) => {{
        if (value !== null && Number.isFinite(value)) values.push(value);
      }}));
      return values;
    }}

    function heatColor(value, min, max) {{
      if (value === null || !Number.isFinite(value)) return '#f3efe6';
      const ratio = max <= min ? 0.5 : (value - min) / (max - min);
      const hue = 42;
      const sat = 88;
      const light = 94 - ratio * 44;
      return `hsl(${{hue}} ${{sat}}% ${{light}}%)`;
    }}

    function drawAnalysisHeatmap(root, matrix, labels, pathPoints, key) {{
      root.innerHTML = '';
      if (!matrix.length || !matrix[0].length) {{
        root.textContent = 'No rows/columns in the current selection.';
        return;
      }}
      const cellW = 4;
      const cellH = 16;
      const padLeft = 260;
      const padTop = 24;
      const width = padLeft + matrix[0].length * cellW + 24;
      const height = padTop + matrix.length * cellH + 24;
      const svgNs = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(svgNs, 'svg');
      svg.setAttribute('width', String(width));
      svg.setAttribute('height', String(height));
      svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
      root.appendChild(svg);
      const values = finiteValues(matrix);
      let min = 0;
      let max = 1;
      if (values.length) {{
        min = Math.min(...values);
        max = Math.max(...values);
      }}
      for (let rowIndex = 0; rowIndex < matrix.length; rowIndex += 1) {{
        const label = document.createElementNS(svgNs, 'text');
        label.setAttribute('x', String(padLeft - 8));
        label.setAttribute('y', String(padTop + rowIndex * cellH + cellH / 2));
        label.setAttribute('text-anchor', 'end');
        label.setAttribute('dominant-baseline', 'middle');
        label.setAttribute('font-size', '11');
        label.setAttribute('fill', '#6f6557');
        label.textContent = labels[rowIndex];
        svg.appendChild(label);
        for (let colIndex = 0; colIndex < matrix[rowIndex].length; colIndex += 1) {{
          const rect = document.createElementNS(svgNs, 'rect');
          rect.setAttribute('x', String(padLeft + colIndex * cellW));
          rect.setAttribute('y', String(padTop + rowIndex * cellH));
          rect.setAttribute('width', String(cellW));
          rect.setAttribute('height', String(cellH));
          rect.setAttribute('fill', heatColor(matrix[rowIndex][colIndex], min, max));
          const title = document.createElementNS(svgNs, 'title');
          title.textContent = `${{labels[rowIndex]}} | bucket ${{colIndex}} | value ${{matrix[rowIndex][colIndex]}}`;
          rect.appendChild(title);
          svg.appendChild(rect);
        }}
      }}
      const guide = document.createElementNS(svgNs, 'line');
      guide.setAttribute('stroke', '#dc2626');
      guide.setAttribute('stroke-width', '2');
      guide.setAttribute('visibility', 'hidden');
      svg.appendChild(guide);
      const dot = document.createElementNS(svgNs, 'circle');
      dot.setAttribute('r', '5');
      dot.setAttribute('fill', '#dc2626');
      dot.setAttribute('stroke', '#ffffff');
      dot.setAttribute('stroke-width', '1.5');
      dot.setAttribute('visibility', 'hidden');
      svg.appendChild(dot);
      if (pathPoints.length) {{
        const polyline = document.createElementNS(svgNs, 'polyline');
        polyline.setAttribute('fill', 'none');
        polyline.setAttribute('stroke', '#0d7a5f');
        polyline.setAttribute('stroke-width', '2.4');
        polyline.setAttribute('points', pathPoints.map((point) => `${{padLeft + point.bucket * cellW + cellW / 2}},${{padTop + point.row * cellH + cellH / 2}}`).join(' '));
        svg.appendChild(polyline);
      }}
      analysisChartState[key] = {{ padLeft, padTop, cellW, cellH, rows: matrix.length, guide, dot }};
    }}

    function updateAnalysisMarkers(currentMs) {{
      const slice = analysisChartState.currentSlice;
      if (!slice) return;
      const relativeBucket = Math.floor((currentMs - slice.audioStartMs) / (data.decoder.bucket_ms || 40));
      ['score', 'dp'].forEach((key) => {{
        const chart = analysisChartState[key];
        if (!chart) return;
        if (relativeBucket < 0 || relativeBucket >= slice.bucketCount || slice.pathRowByBucket[relativeBucket] === undefined) {{
          chart.guide.setAttribute('visibility', 'hidden');
          chart.dot.setAttribute('visibility', 'hidden');
          return;
        }}
        const x = chart.padLeft + relativeBucket * chart.cellW + chart.cellW / 2;
        chart.guide.setAttribute('x1', String(x));
        chart.guide.setAttribute('x2', String(x));
        chart.guide.setAttribute('y1', String(chart.padTop));
        chart.guide.setAttribute('y2', String(chart.padTop + chart.rows * chart.cellH));
        chart.guide.setAttribute('visibility', 'visible');
        const row = slice.pathRowByBucket[relativeBucket];
        chart.dot.setAttribute('cx', String(x));
        chart.dot.setAttribute('cy', String(chart.padTop + row * chart.cellH + chart.cellH / 2));
        chart.dot.setAttribute('visibility', 'visible');
      }});
    }}

    function normalizedAnalysisAudioRange() {{
      const total = data.audio.duration_ms;
      const start = clampNumber(Number(analysisStartInput.value) || 0, 0, total);
      const end = clampNumber(Number(analysisEndInput.value) || total, start, total);
      analysisStartInput.value = String(start);
      analysisEndInput.value = String(end);
      return {{ start, end }};
    }}

    function normalizedAnalysisWordRange() {{
      const maxWord = Math.max(1, data.words.length);
      const start = clampNumber((Number(analysisWordStartInput.value) || 1) - 1, 0, maxWord - 1);
      const end = clampNumber((Number(analysisWordEndInput.value) || maxWord) - 1, start, maxWord - 1);
      analysisWordStartInput.value = String(start + 1);
      analysisWordEndInput.value = String(end + 1);
      return {{ start, end }};
    }}

    function setAnalysisRangeToAyah(ayahNumber) {{
      const ayah = data.ayahs.find((item) => item.ayah_number === ayahNumber);
      if (!ayah || !(ayah.words || []).length) return;
      const startWord = ayah.words[0];
      const endWord = ayah.words[ayah.words.length - 1];
      analysisWordStartInput.value = String(startWord.id);
      analysisWordEndInput.value = String(endWord.id);
      analysisStartInput.value = String(ayah.start_ms);
      analysisEndInput.value = String(ayah.end_ms);
    }}

    function loadAyahAnalysis(ayahNumber) {{
      if (!ayahNumber || !decoderAnalysisFiles[ayahNumber]) return Promise.resolve(null);
      if (ayahAnalysisCache[ayahNumber]) return Promise.resolve(ayahAnalysisCache[ayahNumber]);
      return new Promise((resolve, reject) => {{
        const script = document.createElement('script');
        script.src = decoderAnalysisFiles[ayahNumber];
        script.onload = () => resolve(ayahAnalysisCache[ayahNumber] || null);
        script.onerror = () => reject(new Error(`Failed to load ayah analysis for ayah ${{ayahNumber}}.`));
        document.body.appendChild(script);
      }});
    }}

    async function renderAnalysis() {{
      const audioRange = normalizedAnalysisAudioRange();
      const wordRange = normalizedAnalysisWordRange();
      analysisAudioSummary.textContent = `${{formatMs(audioRange.start)}} - ${{formatMs(audioRange.end)}}`;
      analysisWordSummary.textContent = `Words ${{wordRange.start + 1}}-${{wordRange.end + 1}}`;
      const startWord = data.words[wordRange.start];
      const endWord = data.words[wordRange.end];
      if (!startWord || !endWord) {{
        analysisEmpty.style.display = 'block';
        analysisScoreChart.innerHTML = '';
        analysisDpChart.innerHTML = '';
        analysisSilenceChart.innerHTML = '';
        analysisSelectionSummary.textContent = 'Could not resolve the selected word range.';
        return;
      }}
      const ayahRows = data.ayahs.filter((ayah) => ayah.ayah_number >= startWord.ayah_number && ayah.ayah_number <= endWord.ayah_number);
      if (!ayahRows.length) {{
        analysisEmpty.style.display = 'block';
        analysisScoreChart.innerHTML = '';
        analysisDpChart.innerHTML = '';
        analysisSilenceChart.innerHTML = '';
        analysisSelectionSummary.textContent = 'No ayahs matched the selected range.';
        return;
      }}
      if (ayahRows.length > 3) {{
        analysisEmpty.style.display = 'block';
        analysisScoreChart.innerHTML = '';
        analysisDpChart.innerHTML = '';
        analysisSilenceChart.innerHTML = '';
        analysisSelectionSummary.textContent = 'Detailed analysis currently supports up to 3 consecutive ayahs at a time.';
        return;
      }}
      analysisSelectionSummary.textContent = `Loading analysis for ayahs ${{ayahRows.map((item) => item.ayah_number).join(', ')}}...`;
      let analyses = [];
      try {{
        analyses = await Promise.all(ayahRows.map(async (ayah) => {{
          let analysis = ayahAnalysisCache[ayah.ayah_number];
          if (!analysis && decoderAnalysisFiles[ayah.ayah_number]) {{
            analysis = await loadAyahAnalysis(ayah.ayah_number);
          }}
          return analysis ? {{ ayahNumber: ayah.ayah_number, analysis }} : null;
        }}));
      }} catch (error) {{
        analysisEmpty.style.display = 'block';
        analysisScoreChart.innerHTML = '';
        analysisDpChart.innerHTML = '';
        analysisSilenceChart.innerHTML = '';
        analysisSelectionSummary.textContent = error.message;
        return;
      }}
      analyses = analyses.filter(Boolean);
      if (!analyses.length && decoderDebug) {{
        analyses = [{{ ayahNumber: startWord.ayah_number, analysis: decoderDebug }}];
      }}
      if (!analyses.length) {{
        analysisEmpty.style.display = 'block';
        analysisScoreChart.innerHTML = '';
        analysisDpChart.innerHTML = '';
        analysisSilenceChart.innerHTML = '';
        analysisSelectionSummary.textContent = 'Decoder debug data is not available for the selected ayah range.';
        return;
      }}
      analysisEmpty.style.display = 'none';
      const bucketMs = analyses[0].analysis.bucket_ms || data.decoder.bucket_ms || 40;
      const minBucket = Math.min(...analyses.map((item) => item.analysis.bucket_start || 0));
      const maxBucket = Math.max(...analyses.map((item) => item.analysis.bucket_end || 0));
      const absoluteBucketStart = clampNumber(Math.floor(audioRange.start / bucketMs), minBucket, maxBucket);
      const absoluteBucketEnd = clampNumber(Math.max(absoluteBucketStart, Math.ceil(audioRange.end / bucketMs) - 1), absoluteBucketStart, maxBucket);
      const totalSelectedBuckets = absoluteBucketEnd - absoluteBucketStart + 1;
      const selectedStates = [];
      const labels = [];
      const scoreSlice = [];
      const dpSlice = [];
      const silenceSlice = [new Array(totalSelectedBuckets).fill(null)];
      const stateIndexToRow = new Map();
      const absoluteBucketToState = new Array(totalSelectedBuckets).fill(null);

      analyses.forEach((analysisEntry) => {{
        const ayahNumber = analysisEntry.ayahNumber;
        const analysis = analysisEntry.analysis;
        if (!analysis || !analysis.scoring_matrix || !analysis.dp_scores || !analysis.state_rows) return;
        const localBucketStart = analysis.bucket_start || 0;
        const localBucketEnd = analysis.bucket_end || 0;
        const overlapStart = Math.max(absoluteBucketStart, localBucketStart);
        const overlapEnd = Math.min(absoluteBucketEnd, localBucketEnd);
        const selectedAyahStates = (analysis.state_rows || []).filter((row) => row.global_word_index >= startWord.global_word_index && row.global_word_index <= endWord.global_word_index);
        selectedAyahStates.forEach((row, selectedIndex) => {{
          const label = row.label;
          const rowIndex = selectedStates.length;
          selectedStates.push(row);
          labels.push(label);
          stateIndexToRow.set(`${{ayahNumber}}:${{row.state_index}}`, rowIndex);
          const scoreRow = new Array(totalSelectedBuckets).fill(null);
          const dpRow = new Array(totalSelectedBuckets).fill(null);
          const ayahRowIndex = (analysis.state_rows || []).findIndex((item) => item.state_index === row.state_index);
          if (ayahRowIndex >= 0 && overlapEnd >= overlapStart) {{
            for (let absoluteBucket = overlapStart; absoluteBucket <= overlapEnd; absoluteBucket += 1) {{
              const globalOffset = absoluteBucket - absoluteBucketStart;
              const localOffset = absoluteBucket - localBucketStart;
              scoreRow[globalOffset] = analysis.scoring_matrix[ayahRowIndex][localOffset];
              dpRow[globalOffset] = analysis.dp_scores[ayahRowIndex][localOffset];
            }}
          }}
          scoreSlice.push(scoreRow);
          dpSlice.push(dpRow);
        }});
        for (let absoluteBucket = overlapStart; absoluteBucket <= overlapEnd; absoluteBucket += 1) {{
          const globalOffset = absoluteBucket - absoluteBucketStart;
          const localOffset = absoluteBucket - localBucketStart;
          absoluteBucketToState[globalOffset] = {{ ayahNumber, stateIndex: analysis.bucket_to_state[localOffset] }};
          if ((analysis.bucket_silence_scores || []).length > localOffset) {{
            silenceSlice[0][globalOffset] = analysis.bucket_silence_scores[localOffset];
          }}
        }}
      }});
      if (!selectedStates.length || totalSelectedBuckets <= 0) {{
        analysisScoreChart.innerHTML = '';
        analysisDpChart.innerHTML = '';
        analysisSilenceChart.innerHTML = '';
        analysisSelectionSummary.textContent = 'No states or buckets matched the selected range.';
        return;
      }}
      const compressedScore = compressColumns(scoreSlice, 500);
      const compressedDp = compressColumns(dpSlice, compressedScore.ranges.length || 500);
      const pathPoints = [];
      const pathRowByBucket = {{}};
      compressedScore.ranges.forEach((range, compressedBucket) => {{
        const originalBucket = range[0];
        const pointer = absoluteBucketToState[originalBucket];
        const row = pointer ? stateIndexToRow.get(`${{pointer.ayahNumber}}:${{pointer.stateIndex}}`) : undefined;
        if (row !== undefined) {{
          pathPoints.push({{ bucket: compressedBucket, row }});
        }}
      }});
      for (let bucket = 0; bucket < totalSelectedBuckets; bucket += 1) {{
        const pointer = absoluteBucketToState[bucket];
        const row = pointer ? stateIndexToRow.get(`${{pointer.ayahNumber}}:${{pointer.stateIndex}}`) : undefined;
        if (row !== undefined) {{
          pathRowByBucket[bucket] = row;
        }}
      }}
      analysisSelectionSummary.textContent = `Ayahs ${{ayahRows.map((item) => item.ayah_number).join(', ')}} | Audio buckets ${{absoluteBucketStart}}-${{absoluteBucketEnd}} | States ${{selectedStates.length}} | Selected words ${{wordRange.start + 1}}-${{wordRange.end + 1}}`;
      drawAnalysisHeatmap(analysisScoreChart, compressedScore.matrix, labels, pathPoints, 'score');
      drawAnalysisHeatmap(analysisDpChart, compressedDp.matrix, labels, pathPoints, 'dp');
      const compressedSilence = compressColumns(silenceSlice, compressedScore.ranges.length || 500);
      drawAnalysisHeatmap(analysisSilenceChart, compressedSilence.matrix, ['silence'], [], 'silence');
      analysisChartState.currentSlice = {{
        audioStartMs: absoluteBucketStart * bucketMs,
        bucketCount: totalSelectedBuckets,
        pathRowByBucket,
      }};
      updateAnalysisMarkers(Math.round(audio.currentTime * 1000));
    }}

    playAllBtn.addEventListener('click', () => {{
      audio.currentTime = 0;
      audio.play();
    }});

    playSelectedBtn.addEventListener('click', () => {{
      const word = data.words.find((item) => item.id === selectedWordId);
      if (!word) return;
      audio.currentTime = word.start_ms / 1000;
      audio.play();
    }});

    playSelectedPreBtn.addEventListener('click', () => {{
      const word = data.words.find((item) => item.id === selectedWordId);
      if (!word) return;
      audio.currentTime = Math.max(0, (word.start_ms - 1000) / 1000);
      audio.play();
    }});

    jumpSelectedBtn.addEventListener('click', () => {{
      const word = data.words.find((item) => item.id === selectedWordId);
      if (!word) return;
      audio.currentTime = word.start_ms / 1000;
    }});

    zoomOutBtn.addEventListener('click', () => {{
      timelineZoom = Math.max(1, timelineZoom / 1.25);
      updateTimelineZoom();
    }});

    zoomResetBtn.addEventListener('click', () => {{
      timelineZoom = 1;
      updateTimelineZoom();
    }});

    zoomInBtn.addEventListener('click', () => {{
      timelineZoom = Math.min(8, timelineZoom * 1.25);
      updateTimelineZoom();
    }});

    analysisSetStartBtn.addEventListener('click', () => {{
      analysisStartInput.value = String(Math.floor(audio.currentTime * 1000));
      renderAnalysis();
    }});

    analysisSetEndBtn.addEventListener('click', () => {{
      analysisEndInput.value = String(Math.floor(audio.currentTime * 1000));
      renderAnalysis();
    }});

    analysisPlayRegionBtn.addEventListener('click', () => {{
      const audioRange = normalizedAnalysisAudioRange();
      playUntilSeconds = audioRange.end / 1000;
      audio.currentTime = audioRange.start / 1000;
      audio.play();
    }});

    analysisUseSelectedStartBtn.addEventListener('click', () => {{
      const word = data.words.find((item) => item.id === selectedWordId);
      if (!word) return;
      analysisWordStartInput.value = String(word.id);
      renderAnalysis();
    }});

    analysisUseSelectedEndBtn.addEventListener('click', () => {{
      const word = data.words.find((item) => item.id === selectedWordId);
      if (!word) return;
      analysisWordEndInput.value = String(word.id);
      renderAnalysis();
    }});

    [analysisStartInput, analysisEndInput, analysisWordStartInput, analysisWordEndInput].forEach((input) => {{
      input.addEventListener('input', renderAnalysis);
      input.addEventListener('change', renderAnalysis);
    }});

    showSuspiciousOnlyInput.addEventListener('change', updateSuspiciousFilter);

    audio.addEventListener('timeupdate', () => {{
      const timeMs = Math.floor(audio.currentTime * 1000);
      playbackStatusEl.textContent = `${{formatMs(timeMs)}} / ${{data.audio.duration_label}}`;
      updateActiveWord(timeMs);
      updateAnalysisMarkers(timeMs);
      if (playUntilSeconds !== null && audio.currentTime >= playUntilSeconds) {{
        audio.pause();
        playUntilSeconds = null;
      }}
    }});

    audio.addEventListener('pause', () => {{
      if (!audio.ended) {{
        playUntilSeconds = null;
      }}
    }});

    render();
    updateTimelineZoom();
    if (data.words.length) {{
      renderComparison();
      selectWord(data.words[0].id, false);
    }}
    renderAnalysis();
  </script>
</body>
</html>
"""


def write_review_html(output_path: Path, payload: dict) -> None:
    output_path.write_text(build_review_html(payload), encoding="utf-8")
