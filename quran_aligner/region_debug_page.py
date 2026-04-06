from __future__ import annotations

import json
from pathlib import Path


def _compress_matrix(matrix: list[list[float | None]], target_cols: int = 600) -> tuple[list[list[float | None]], list[tuple[int, int]]]:
    if not matrix or not matrix[0]:
        return matrix, []
    cols = len(matrix[0])
    if cols <= target_cols:
        return matrix, [(index, index + 1) for index in range(cols)]
    step = max(1, (cols + target_cols - 1) // target_cols)
    ranges: list[tuple[int, int]] = []
    for start in range(0, cols, step):
        ranges.append((start, min(cols, start + step)))
    compressed: list[list[float | None]] = []
    for row in matrix:
        compressed_row: list[float | None] = []
        for start, end in ranges:
            values = [value for value in row[start:end] if value is not None]
            compressed_row.append(round(sum(values) / len(values), 4) if values else None)
        compressed.append(compressed_row)
    return compressed, ranges


def _compress_path(bucket_to_state: list[int], ranges: list[tuple[int, int]]) -> list[dict[str, int]]:
    if not ranges:
        return [{"state": state_index, "bucket": bucket_index} for bucket_index, state_index in enumerate(bucket_to_state)]
    points: list[dict[str, int]] = []
    for compressed_bucket, (start, _end) in enumerate(ranges):
        if 0 <= start < len(bucket_to_state):
            points.append({"state": bucket_to_state[start], "bucket": compressed_bucket})
    return points


def _build_chart_payload(payload: dict) -> dict[str, object]:
    decoder = payload.get("decoder", {})
    scoring_matrix = decoder.get("scoring_matrix", [])
    raw_dp_scores = decoder.get("dp_scores", [])
    dp_scores = [row[1:] for row in raw_dp_scores] if raw_dp_scores else []
    compressed_scoring, column_ranges = _compress_matrix(scoring_matrix)
    compressed_dp, _ = _compress_matrix(dp_scores, target_cols=len(column_ranges) or 600)
    raw_bucket_to_state = decoder.get("bucket_to_state", decoder.get("bucket_to_word", []))
    return {
        "region": payload.get("region", {}),
        "audio": payload.get("audio", {}),
        "tokens": payload.get("tokens", []),
        "runs": payload.get("runs", []),
        "decoder": {
            "bucket_count": decoder.get("bucket_count"),
            "bucket_ms": decoder.get("bucket_ms"),
            "phrase_trace": decoder.get("phrase_trace", [])[:40],
            "state_rows": decoder.get("state_rows", []),
            "scoring_matrix": compressed_scoring,
            "dp_scores": compressed_dp,
            "bucket_to_state": _compress_path(raw_bucket_to_state, column_ranges),
            "column_ranges": column_ranges,
            "raw_scoring_matrix": scoring_matrix,
            "raw_dp_scores": raw_dp_scores,
            "raw_dp_bucket_scores": dp_scores,
            "raw_backpointers": decoder.get("backpointers", []),
            "raw_bucket_to_state": raw_bucket_to_state,
            "raw_bucket_to_word": decoder.get("bucket_to_word", []),
            "bucket_silence_scores": decoder.get("bucket_silence_scores", []),
        },
    }


def build_region_debug_html(payload: dict) -> str:
    region = payload["region"]
    audio = payload.get("audio", {})
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Region Inspect</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --card: rgba(255,255,255,0.92);
      --ink: #1f1913;
      --muted: #6d6255;
      --line: rgba(39,30,20,0.14);
      --accent: #0d7a5f;
      --accent-soft: rgba(13,122,95,0.12);
      --warn: #b45309;
      --active: #dc2626;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, sans-serif;
      background: linear-gradient(180deg, #f8f4eb 0%, #f1ebdf 100%);
      color: var(--ink);
    }}
    .shell {{
      max-width: 1600px;
      margin: 0 auto;
      padding: 20px;
      display: grid;
      gap: 16px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      overflow: hidden;
      box-shadow: 0 12px 32px rgba(56, 44, 29, 0.08);
    }}
    .meta {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 14px;
    }}
    .audio-panel {{
      display: grid;
      gap: 12px;
    }}
    .audio-grid {{
      display: grid;
      grid-template-columns: minmax(280px, 1.2fr) minmax(320px, 1fr);
      gap: 16px;
      align-items: start;
    }}
    .timeline-chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #fffdf8;
      color: var(--muted);
      font-size: 13px;
    }}
    audio {{
      width: 100%;
    }}
    .region-timeline {{
      display: grid;
      gap: 10px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fffdf9;
    }}
    .region-timeline label {{
      font-size: 13px;
      color: var(--muted);
    }}
    .range-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }}
    .time-selection-grid {{
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }}
    .range-grid .controls {{
      align-items: end;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .summary-box {{
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
      background: #fffdf9;
      min-height: 96px;
    }}
    .summary-box h3 {{
      margin: 0 0 8px;
      font-size: 14px;
    }}
    .mono {{
      font-family: ui-monospace, SFMono-Regular, monospace;
    }}
    .chart-wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fffdf8;
      padding: 12px;
    }}
    .legend {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
    }}
    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .swatch {{
      width: 12px;
      height: 12px;
      border-radius: 3px;
      border: 1px solid rgba(0,0,0,0.12);
      display: inline-block;
    }}
    .inspector {{
      display: grid;
      gap: 10px;
    }}
    .controls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }}
    input[type="number"], input[type="range"] {{
      font: inherit;
    }}
    input[type="number"] {{
      width: 120px;
      padding: 8px 10px;
      border-radius: 10px;
      border: 1px solid var(--line);
    }}
    input[type="range"] {{
      width: 100%;
    }}
    button {{
      padding: 8px 12px;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #fff;
      cursor: pointer;
      font: inherit;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 6px 8px;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }}
    th {{
      background: #faf6ee;
    }}
    .scroll-table {{
      overflow: auto;
      max-height: 460px;
      border: 1px solid var(--line);
      border-radius: 12px;
    }}
    .path-summary {{
      display: grid;
      gap: 4px;
      max-height: 220px;
      overflow: auto;
      font-size: 13px;
    }}
    svg {{
      display: block;
      background: #fff;
    }}
    .hint {{
      color: var(--muted);
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="card">
      <h1>Region Decoder Inspect</h1>
      <div class="meta">
        <span>Audio region: {region["start_ms"]} - {region["end_ms"]} ms</span>
        <span>Ayah: {region.get("ayah_number", "mixed")}</span>
        <span>Words: {len(payload.get("tokens", []))}</span>
        <span>States: {payload["decoder"].get("state_count", payload["decoder"].get("word_count", 0))}</span>
        <span>Buckets: {payload["decoder"]["bucket_count"]}</span>
        <span>Bucket ms: {payload["decoder"].get("bucket_ms", "")}</span>
        <span>Audio: {audio.get("duration_label", "")}</span>
      </div>
    </section>

    <section class="card audio-panel">
      <h2>Audio Sync</h2>
      <div class="audio-grid">
        <div>
          <audio id="audio" controls preload="metadata">
            <source src="{audio.get("relative_path", "")}" type="audio/mpeg" />
          </audio>
          <div class="controls">
            <button id="jump-region-start">Jump to region start</button>
            <button id="play-region">Play region</button>
            <button id="pause-audio">Pause</button>
          </div>
          <div class="region-timeline">
            <label for="time-slider">Region-only audio position</label>
            <input id="time-slider" type="range" min="{region["start_ms"]}" max="{region["end_ms"]}" value="{region["start_ms"]}" step="1" />
            <div class="hint">This large scrubber is limited to the inspected region for finer positioning.</div>
            <div class="time-selection-grid">
              <label for="selection-start-slider">Selection start</label>
              <input id="selection-start-slider" type="range" min="{region["start_ms"]}" max="{region["end_ms"]}" value="{region["start_ms"]}" step="1" />
              <label for="selection-end-slider">Selection end</label>
              <input id="selection-end-slider" type="range" min="{region["start_ms"]}" max="{region["end_ms"]}" value="{region["end_ms"]}" step="1" />
              <div class="controls">
                <button id="set-selection-start">Set start from current audio</button>
                <button id="set-selection-end">Set end from current audio</button>
                <button id="play-time-selection">Play selected time range</button>
              </div>
              <div class="hint" id="time-selection-summary"></div>
            </div>
          </div>
          <div class="range-grid">
            <div class="summary-box">
              <h3>Bucket Range Playback</h3>
              <div class="controls">
                <label for="range-start-bucket">Start</label>
                <input id="range-start-bucket" type="number" min="0" step="1" value="0" />
                <label for="range-end-bucket">End</label>
                <input id="range-end-bucket" type="number" min="0" step="1" value="0" />
              </div>
              <div class="controls">
                <button id="set-range-start">Set start from current</button>
                <button id="set-range-end">Set end from current</button>
                <button id="play-current-bucket">Play current bucket</button>
                <button id="play-bucket-range">Play selected bucket range</button>
              </div>
              <div class="hint" id="range-summary"></div>
            </div>
            <div class="summary-box">
              <h3>Chart Markers</h3>
              <div class="hint">Red vertical line: current bucket/time column.</div>
              <div class="hint">Red dot: the chosen path state at that same bucket.</div>
              <div class="hint">Green polyline: the decoder's selected path across buckets.</div>
            </div>
          </div>
          <div class="meta">
            <span class="timeline-chip" id="time-chip">00:00.000</span>
            <span class="timeline-chip" id="bucket-chip">Bucket -</span>
            <span class="timeline-chip" id="state-chip">State -</span>
            <span class="timeline-chip" id="word-chip">Word -</span>
          </div>
        </div>
        <div class="summary-grid">
          <div class="summary-box">
            <h3>Selection</h3>
            <div id="selection-summary" class="mono"></div>
          </div>
          <div class="summary-box">
            <h3>Backpointer</h3>
            <div id="backpointer-summary" class="mono"></div>
          </div>
          <div class="summary-box">
            <h3>Alignment</h3>
            <div id="alignment-summary" class="mono"></div>
          </div>
          <div class="summary-box">
            <h3>Hover Cell</h3>
            <div id="hover-summary" class="mono"></div>
          </div>
        </div>
      </div>
    </section>

    <section class="card inspector">
      <h2>Bucket Inspector</h2>
      <div class="controls">
        <label for="bucket-input">Bucket</label>
        <input id="bucket-input" type="number" min="0" step="1" value="0" />
        <button id="show-bucket">Show bucket</button>
      </div>
      <div class="hint">The table below shows the actual raw values used by the DP at the selected bucket.</div>
      <div id="bucket-summary"></div>
      <div class="scroll-table" id="bucket-table"></div>
    </section>

    <section class="card">
      <h2>Chosen Path Summary</h2>
      <div id="path-summary" class="path-summary"></div>
    </section>

    <section class="card">
      <h2>Scoring Matrix</h2>
      <div class="legend">
        <span><i class="swatch" style="background:#f3efe6"></i> Low score</span>
        <span><i class="swatch" style="background:#f59e0b"></i> High score</span>
        <span><i class="swatch" style="background:#0d7a5f"></i> Chosen path</span>
        <span><i class="swatch" style="background:#dc2626"></i> Current audio bucket</span>
        <span><i class="swatch" style="background:#dc2626;border-radius:999px"></i> Current path state</span>
      </div>
      <div class="hint">Chart interaction: click a cell to select that bucket and jump audio there. Shift-click a second bucket to define a bucket region. Drag across columns to select a bucket range directly on the chart.</div>
      <div class="chart-wrap">
        <div id="scoring-chart"></div>
      </div>
    </section>

    <section class="card">
      <h2>DP Matrix</h2>
      <div class="hint">This chart shows cumulative best-prefix DP scores for real buckets only. The hidden DP column 0 is the empty-prefix base case, so it is omitted here to keep the matrix aligned with the bucket axis.</div>
      <div class="chart-wrap">
        <div id="dp-chart"></div>
      </div>
    </section>

    <section class="card">
      <h2>Silence Scores</h2>
      <div class="hint">Bucket-specific silence scores derived from the CTC blank label.</div>
      <div class="chart-wrap">
        <div id="silence-chart"></div>
      </div>
    </section>
  </div>

  <script src="./region-inspect.data.js"></script>
  <script>
    const data = window.REGION_INSPECT_DATA;
    const svgNs = 'http://www.w3.org/2000/svg';
    const audio = document.getElementById('audio');
    const timeSlider = document.getElementById('time-slider');
    const selectionStartSlider = document.getElementById('selection-start-slider');
    const selectionEndSlider = document.getElementById('selection-end-slider');
    const timeChip = document.getElementById('time-chip');
    const bucketChip = document.getElementById('bucket-chip');
    const stateChip = document.getElementById('state-chip');
    const wordChip = document.getElementById('word-chip');
    const timeSelectionSummaryEl = document.getElementById('time-selection-summary');
    const rangeStartBucketInput = document.getElementById('range-start-bucket');
    const rangeEndBucketInput = document.getElementById('range-end-bucket');
    const rangeSummaryEl = document.getElementById('range-summary');
    const selectionSummaryEl = document.getElementById('selection-summary');
    const backpointerSummaryEl = document.getElementById('backpointer-summary');
    const alignmentSummaryEl = document.getElementById('alignment-summary');
    const hoverSummaryEl = document.getElementById('hover-summary');
    const bucketInput = document.getElementById('bucket-input');
    const showBucketBtn = document.getElementById('show-bucket');
    const bucketSummaryEl = document.getElementById('bucket-summary');
    const bucketTableEl = document.getElementById('bucket-table');
    const pathSummaryEl = document.getElementById('path-summary');
    const scoringChart = document.getElementById('scoring-chart');
    const dpChart = document.getElementById('dp-chart');
    const silenceChart = document.getElementById('silence-chart');
    const regionStartMs = data.region.start_ms || 0;
    const regionEndMs = data.region.end_ms || 0;
    const bucketMs = data.decoder.bucket_ms || 1;
    const rawBucketToState = data.decoder.raw_bucket_to_state || [];
    const rawBucketToWord = data.decoder.raw_bucket_to_word || [];
    const stateRows = data.decoder.state_rows || [];
    const tokens = data.tokens || [];
    const runs = data.runs || [];
    let playUntilSeconds = null;
    let selectionBucket = 0;
    let playbackRange = null;
    let chartRangeAnchorBucket = null;
    let chartDragState = null;
    const chartState = {{}};

    function formatMs(ms) {{
      const clamped = Math.max(0, Math.round(ms));
      const totalSeconds = Math.floor(clamped / 1000);
      const minutes = Math.floor(totalSeconds / 60);
      const seconds = totalSeconds % 60;
      const millis = clamped % 1000;
      return `${{String(minutes).padStart(2, '0')}}:${{String(seconds).padStart(2, '0')}}.${{String(millis).padStart(3, '0')}}`;
    }}

    function finiteValues(matrix) {{
      const values = [];
      for (const row of matrix) {{
        for (const value of row) {{
          if (value !== null && Number.isFinite(value)) values.push(value);
        }}
      }}
      return values;
    }}

    function colorFor(value, min, max) {{
      if (value === null || !Number.isFinite(value)) return '#f3efe6';
      const ratio = max <= min ? 0.5 : (value - min) / (max - min);
      const hue = 42;
      const sat = 88;
      const light = 94 - ratio * 44;
      return `hsl(${{hue}} ${{sat}}% ${{light}}%)`;
    }}

    function stateLabel(index) {{
      const row = stateRows[index];
      return row ? row.label : `state ${{index}}`;
    }}

    function wordLabel(index) {{
      const token = tokens[index];
      return token ? `${{index}}: ${{token.original_word}}` : `word ${{index}}`;
    }}

    function bucketToMs(bucketIndex) {{
      return regionStartMs + bucketIndex * bucketMs;
    }}

    function clampAudioToRegion() {{
      if (audio.currentTime * 1000 < regionStartMs) {{
        audio.currentTime = regionStartMs / 1000;
      }}
      if (audio.currentTime * 1000 > regionEndMs) {{
        audio.currentTime = regionEndMs / 1000;
      }}
    }}

    function msToBucket(ms) {{
      const local = Math.max(0, ms - regionStartMs);
      const bucketCount = data.decoder.bucket_count || 0;
      if (!bucketCount) return 0;
      return Math.max(0, Math.min(bucketCount - 1, Math.floor(local / bucketMs)));
    }}

    function bucketPathSummary(bucketIndex) {{
      const stateIndex = rawBucketToState[bucketIndex];
      const wordIndex = rawBucketToWord[bucketIndex];
      const row = stateRows[stateIndex];
      return {{
        stateIndex,
        wordIndex,
        row,
        token: tokens[wordIndex] || null,
      }};
    }}

    function findRunAt(ms) {{
      return runs.find((run) => run.start_ms <= ms && ms < run.end_ms) || null;
    }}

    function pointerFor(stateIndex, bucketIndex) {{
      return (((data.decoder.raw_backpointers || [])[stateIndex] || [])[bucketIndex + 1]) || null;
    }}

    function prevStateIndex(pointer) {{
      if (!pointer) return null;
      if (Object.prototype.hasOwnProperty.call(pointer, 'prev_state_index')) return pointer.prev_state_index;
      if (Object.prototype.hasOwnProperty.call(pointer, 'prev_word_index')) return pointer.prev_word_index;
      return null;
    }}

    function renderBucketInspector(bucketIndex) {{
      const bucketCount = data.decoder.bucket_count || 0;
      if (!Number.isFinite(bucketIndex) || bucketIndex < 0 || bucketIndex >= bucketCount) {{
        bucketSummaryEl.textContent = `Bucket must be between 0 and ${{Math.max(0, bucketCount - 1)}}.`;
        bucketTableEl.innerHTML = '';
        return;
      }}
      const path = bucketPathSummary(bucketIndex);
      bucketSummaryEl.textContent = `Bucket ${{bucketIndex}} | time ${{formatMs(bucketToMs(bucketIndex))}} | chosen state: ${{stateLabel(path.stateIndex)}} | chosen word: ${{wordLabel(path.wordIndex)}}`;
      const rows = stateRows.map((row, index) => {{
        const score = ((data.decoder.raw_scoring_matrix || [])[index] || [])[bucketIndex];
        const dp = ((data.decoder.raw_dp_scores || [])[index] || [])[bucketIndex + 1];
        const pointer = pointerFor(index, bucketIndex);
        const active = index === path.stateIndex ? ' style="background: var(--accent-soft);"' : '';
        return `
          <tr${{active}}>
            <th>${{row.label}}</th>
            <td>${{row.word}}</td>
            <td>${{score ?? ''}}</td>
            <td>${{dp ?? ''}}</td>
            <td>${{pointer ? stateLabel(prevStateIndex(pointer)) : ''}}</td>
            <td>${{pointer ? pointer.prev_bucket : ''}}</td>
          </tr>
        `;
      }}).join('');
      bucketTableEl.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>State</th>
              <th>Word</th>
              <th>Raw score_matrix[i][b]</th>
              <th>Raw DP[i][b+1]</th>
              <th>Back prev state</th>
              <th>Back prev bucket</th>
            </tr>
          </thead>
          <tbody>${{rows}}</tbody>
        </table>
      `;
    }}

    function normalizedRange() {{
      const bucketCount = data.decoder.bucket_count || 0;
      const rawStart = Number(rangeStartBucketInput.value);
      const rawEnd = Number(rangeEndBucketInput.value);
      const start = Math.max(0, Math.min(bucketCount - 1, Number.isFinite(rawStart) ? rawStart : 0));
      const end = Math.max(start, Math.min(bucketCount - 1, Number.isFinite(rawEnd) ? rawEnd : start));
      rangeStartBucketInput.value = String(start);
      rangeEndBucketInput.value = String(end);
      return {{ start, end }};
    }}

    function normalizedTimeSelection() {{
      const rawStart = Number(selectionStartSlider.value);
      const rawEnd = Number(selectionEndSlider.value);
      const start = Math.max(regionStartMs, Math.min(regionEndMs, Number.isFinite(rawStart) ? rawStart : regionStartMs));
      const end = Math.max(start, Math.min(regionEndMs, Number.isFinite(rawEnd) ? rawEnd : start));
      selectionStartSlider.value = String(start);
      selectionEndSlider.value = String(end);
      return {{ start, end }};
    }}

    function syncBucketRangeToTimeSelection() {{
      const selection = normalizedTimeSelection();
      const startBucket = msToBucket(selection.start);
      const endBucket = Math.max(startBucket, msToBucket(Math.max(selection.start, selection.end - 1)));
      rangeStartBucketInput.value = String(startBucket);
      rangeEndBucketInput.value = String(endBucket);
      return {{ selection, startBucket, endBucket }};
    }}

    function updateRangeSummary() {{
      const range = normalizedRange();
      const startMs = bucketToMs(range.start);
      const endMs = bucketToMs(range.end + 1);
      rangeSummaryEl.textContent = `Buckets ${{range.start}}-${{range.end}} | ${{formatMs(startMs)}} - ${{formatMs(endMs)}}`;
      return range;
    }}

    function updateTimeSelectionSummary() {{
      const selection = normalizedTimeSelection();
      timeSelectionSummaryEl.textContent = `Selection ${{formatMs(selection.start)}} - ${{formatMs(selection.end)}}`;
      return selection;
    }}

    function setBucketRange(startBucket, endBucket) {{
      const bucketCount = data.decoder.bucket_count || 0;
      if (!bucketCount) return {{ start: 0, end: 0 }};
      const start = Math.max(0, Math.min(bucketCount - 1, Math.min(startBucket, endBucket)));
      const end = Math.max(start, Math.min(bucketCount - 1, Math.max(startBucket, endBucket)));
      rangeStartBucketInput.value = String(start);
      rangeEndBucketInput.value = String(end);
      selectionStartSlider.value = String(bucketToMs(start));
      selectionEndSlider.value = String(bucketToMs(end + 1));
      updateTimeSelectionSummary();
      updateRangeSummary();
      updateChartRange('scoring', start, end);
      updateChartRange('dp', start, end);
      return {{ start, end }};
    }}

    function playBucketRange(startBucket, endBucket) {{
      const range = setBucketRange(startBucket, endBucket);
      playbackRange = range;
      audio.currentTime = bucketToMs(range.start) / 1000;
      playUntilSeconds = Math.min(regionEndMs, bucketToMs(range.end + 1)) / 1000;
      audio.play();
    }}

    function handleChartBucketSelection(bucketIndex, syncAudio, extendRange = false) {{
      if (extendRange && chartRangeAnchorBucket !== null) {{
        setBucketRange(chartRangeAnchorBucket, bucketIndex);
      }} else {{
        chartRangeAnchorBucket = bucketIndex;
        setBucketRange(bucketIndex, bucketIndex);
      }}
      selectBucket(bucketIndex, syncAudio);
    }}

    function startChartDrag(bucketIndex) {{
      chartDragState = {{ anchor: bucketIndex }};
      chartRangeAnchorBucket = bucketIndex;
      setBucketRange(bucketIndex, bucketIndex);
      selectBucket(bucketIndex, true);
    }}

    function updateChartDrag(bucketIndex) {{
      if (!chartDragState) return;
      setBucketRange(chartDragState.anchor, bucketIndex);
      selectBucket(bucketIndex, false);
    }}

    function endChartDrag(bucketIndex) {{
      if (!chartDragState) return;
      setBucketRange(chartDragState.anchor, bucketIndex);
      selectBucket(bucketIndex, false);
      chartDragState = null;
    }}

    function setHoverSummary(rowIndex, bucketIndex, value, matrixName) {{
      const path = bucketPathSummary(Math.max(0, Math.min(rawBucketToState.length - 1, bucketIndex)));
      hoverSummaryEl.innerHTML = `
        <div>${{matrixName}} row: <strong>${{stateLabel(rowIndex)}}</strong></div>
        <div>bucket: <strong>${{bucketIndex}}</strong> at <strong>${{formatMs(bucketToMs(bucketIndex))}}</strong></div>
        <div>cell value: <strong>${{value}}</strong></div>
        <div>path state here: <strong>${{stateLabel(path.stateIndex)}}</strong></div>
        <div>path word here: <strong>${{wordLabel(path.wordIndex)}}</strong></div>
      `;
    }}

    function drawHeatmap(root, matrix, pathPoints, yLabels, key, matrixName) {{
      const cellW = 4;
      const cellH = 18;
      const padLeft = 280;
      const padTop = 26;
      const padRight = 24;
      const padBottom = 28;
      const rows = matrix.length;
      const cols = rows ? matrix[0].length : 0;
      const width = padLeft + cols * cellW + padRight;
      const height = padTop + rows * cellH + padBottom;
      root.innerHTML = '';
      const svg = document.createElementNS(svgNs, 'svg');
      svg.setAttribute('width', String(width));
      svg.setAttribute('height', String(height));
      svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
      root.appendChild(svg);

      const vals = finiteValues(matrix);
      let min = 0;
      let max = 1;
      if (vals.length) {{
        min = vals[0];
        max = vals[0];
        for (const value of vals) {{
          if (value < min) min = value;
          if (value > max) max = value;
        }}
      }}

      const cellsByBucket = new Map();
      const cellsByCoord = new Map();

      for (let r = 0; r < rows; r += 1) {{
        const label = yLabels[r] || String(r);
        const labelNode = document.createElementNS(svgNs, 'text');
        labelNode.setAttribute('x', String(padLeft - 8));
        labelNode.setAttribute('y', String(padTop + r * cellH + cellH / 2));
        labelNode.setAttribute('text-anchor', 'end');
        labelNode.setAttribute('dominant-baseline', 'middle');
        labelNode.setAttribute('fill', '#6f6557');
        labelNode.setAttribute('font-size', '11');
        labelNode.textContent = label;
        svg.appendChild(labelNode);
        for (let c = 0; c < cols; c += 1) {{
          const rect = document.createElementNS(svgNs, 'rect');
          rect.setAttribute('x', String(padLeft + c * cellW));
          rect.setAttribute('y', String(padTop + r * cellH));
          rect.setAttribute('width', String(cellW));
          rect.setAttribute('height', String(cellH));
          rect.setAttribute('fill', colorFor(matrix[r][c], min, max));
          rect.dataset.row = String(r);
          rect.dataset.bucket = String(c);
          rect.dataset.matrix = matrixName;
          rect.style.cursor = 'crosshair';
          const title = document.createElementNS(svgNs, 'title');
          title.textContent = `${{matrixName}} | row=${{label}} | bucket=${{c}} | value=${{matrix[r][c]}}`;
          rect.appendChild(title);
          rect.addEventListener('mouseenter', () => setHoverSummary(r, c, matrix[r][c], matrixName));
          rect.addEventListener('click', (event) => handleChartBucketSelection(c, true, event.shiftKey));
          rect.addEventListener('mousedown', (event) => {{
            if (event.button !== 0) return;
            event.preventDefault();
            startChartDrag(c);
          }});
          rect.addEventListener('mousemove', () => {{
            if (!chartDragState) return;
            updateChartDrag(c);
          }});
          rect.addEventListener('mouseup', () => endChartDrag(c));
          svg.appendChild(rect);
          if (!cellsByBucket.has(c)) cellsByBucket.set(c, []);
          cellsByBucket.get(c).push(rect);
          cellsByCoord.set(`${{r}}:${{c}}`, rect);
        }}
      }}

      const bucketGuide = document.createElementNS(svgNs, 'line');
      bucketGuide.setAttribute('y1', String(padTop));
      bucketGuide.setAttribute('y2', String(padTop + rows * cellH));
      bucketGuide.setAttribute('stroke', '#dc2626');
      bucketGuide.setAttribute('stroke-width', '2');
      bucketGuide.setAttribute('opacity', '0.9');
      svg.appendChild(bucketGuide);

      let activePathDot = null;
      if (pathPoints.length) {{
        const polyline = document.createElementNS(svgNs, 'polyline');
        const points = [];
        pathPoints.forEach((point) => {{
          const x = padLeft + point.bucket * cellW + cellW / 2;
          const y = padTop + point.state * cellH + cellH / 2;
          points.push(`${{x}},${{y}}`);
        }});
        polyline.setAttribute('points', points.join(' '));
        polyline.setAttribute('fill', 'none');
        polyline.setAttribute('stroke', '#0d7a5f');
        polyline.setAttribute('stroke-width', '2.5');
        svg.appendChild(polyline);

        activePathDot = document.createElementNS(svgNs, 'circle');
        activePathDot.setAttribute('r', '5');
        activePathDot.setAttribute('fill', '#dc2626');
        activePathDot.setAttribute('stroke', '#ffffff');
        activePathDot.setAttribute('stroke-width', '1.5');
        svg.appendChild(activePathDot);
      }}

      chartState[key] = {{
        padLeft,
        padTop,
        cellW,
        cellH,
        rows,
        cols,
        cellsByBucket,
        cellsByCoord,
        bucketGuide,
        activePathDot,
        rangeOverlay: null,
      }};

      const rangeOverlay = document.createElementNS(svgNs, 'rect');
      rangeOverlay.setAttribute('y', String(padTop));
      rangeOverlay.setAttribute('height', String(rows * cellH));
      rangeOverlay.setAttribute('fill', 'rgba(13, 122, 95, 0.12)');
      rangeOverlay.setAttribute('stroke', 'rgba(13, 122, 95, 0.45)');
      rangeOverlay.setAttribute('stroke-width', '1');
      rangeOverlay.setAttribute('visibility', 'hidden');
      svg.insertBefore(rangeOverlay, bucketGuide);
      chartState[key].rangeOverlay = rangeOverlay;
    }}

    function updateChartRange(key, startBucket, endBucket) {{
      const chart = chartState[key];
      if (!chart || !chart.rangeOverlay) return;
      const x = chart.padLeft + startBucket * chart.cellW;
      const width = Math.max(chart.cellW, (endBucket - startBucket + 1) * chart.cellW);
      chart.rangeOverlay.setAttribute('x', String(x));
      chart.rangeOverlay.setAttribute('width', String(width));
      chart.rangeOverlay.setAttribute('visibility', 'visible');
    }}

    function updateChartSelection(key, bucketIndex, stateIndex) {{
      const chart = chartState[key];
      if (!chart) return;
      for (const [bucket, cells] of chart.cellsByBucket.entries()) {{
        const isActiveBucket = Number(bucket) === bucketIndex;
        cells.forEach((cell) => {{
          cell.setAttribute('stroke', isActiveBucket ? '#dc2626' : 'none');
          cell.setAttribute('stroke-width', isActiveBucket ? '0.9' : '0');
        }});
      }}
      if (chart.bucketGuide) {{
        const x = chart.padLeft + bucketIndex * chart.cellW + chart.cellW / 2;
        chart.bucketGuide.setAttribute('x1', String(x));
        chart.bucketGuide.setAttribute('x2', String(x));
      }}
      if (chart.activePathDot && Number.isFinite(stateIndex) && stateIndex >= 0) {{
        const x = chart.padLeft + bucketIndex * chart.cellW + chart.cellW / 2;
        const y = chart.padTop + stateIndex * chart.cellH + chart.cellH / 2;
        chart.activePathDot.setAttribute('cx', String(x));
        chart.activePathDot.setAttribute('cy', String(y));
      }}
      const selectedCell = chart.cellsByCoord.get(`${{stateIndex}}:${{bucketIndex}}`);
      if (selectedCell) {{
        selectedCell.setAttribute('stroke', '#0d7a5f');
        selectedCell.setAttribute('stroke-width', '2');
      }}
    }}

    function updateSelectionSummary(bucketIndex) {{
      const path = bucketPathSummary(bucketIndex);
      const stateIndex = path.stateIndex;
      const wordIndex = path.wordIndex;
      const score = ((data.decoder.raw_scoring_matrix || [])[stateIndex] || [])[bucketIndex];
      const dp = ((data.decoder.raw_dp_scores || [])[stateIndex] || [])[bucketIndex + 1];
      const silence = (data.decoder.bucket_silence_scores || [])[bucketIndex];
      const pointer = pointerFor(stateIndex, bucketIndex);
      const bucketStartMs = bucketToMs(bucketIndex);
      const bucketEndMs = bucketStartMs + bucketMs;
      const run = findRunAt(bucketStartMs);

      timeChip.textContent = formatMs(Math.round(audio.currentTime * 1000));
      bucketChip.textContent = `Bucket ${{bucketIndex}}`;
      stateChip.textContent = `State ${{stateLabel(stateIndex)}}`;
      wordChip.textContent = `Word ${{wordLabel(wordIndex)}}`;
      selectionSummaryEl.innerHTML = `
        <div>time: <strong>${{formatMs(bucketStartMs)}}</strong> - <strong>${{formatMs(bucketEndMs)}}</strong></div>
        <div>state: <strong>${{stateLabel(stateIndex)}}</strong></div>
        <div>word: <strong>${{wordLabel(wordIndex)}}</strong></div>
        <div>score_matrix[state][bucket]: <strong>${{score}}</strong></div>
        <div>dp[state][bucket+1]: <strong>${{dp}}</strong></div>
        <div>silence_score[bucket]: <strong>${{silence}}</strong></div>
      `;
      backpointerSummaryEl.innerHTML = pointer
        ? `
          <div>prev state: <strong>${{stateLabel(prevStateIndex(pointer))}}</strong></div>
          <div>prev bucket: <strong>${{pointer.prev_bucket}}</strong></div>
          <div>segment: <strong>${{pointer.prev_bucket}} -> ${{bucketIndex}}</strong></div>
        `
        : '<div>start state for this segment</div>';
      alignmentSummaryEl.innerHTML = `
        <div>current run: <strong>${{run ? `${{run.word}} (${{formatMs(run.start_ms)}} - ${{formatMs(run.end_ms)}})` : 'none'}}</strong></div>
        <div>region ms: <strong>${{formatMs(regionStartMs)}} - ${{formatMs(regionEndMs)}}</strong></div>
        <div>bucket local ms: <strong>${{formatMs(bucketStartMs - regionStartMs)}}</strong></div>
      `;
      updateTimeSelectionSummary();
      syncBucketRangeToTimeSelection();
      updateRangeSummary();
    }}

    function selectBucket(bucketIndex, syncAudio = false) {{
      if (!Number.isFinite(bucketIndex)) return;
      const bucketCount = data.decoder.bucket_count || 0;
      selectionBucket = Math.max(0, Math.min(bucketCount - 1, bucketIndex));
      bucketInput.value = String(selectionBucket);
      const stateIndex = rawBucketToState[selectionBucket] ?? -1;
      updateChartSelection('scoring', selectionBucket, stateIndex);
      updateChartSelection('dp', selectionBucket, stateIndex);
      updateSelectionSummary(selectionBucket);
      renderBucketInspector(selectionBucket);
      if (syncAudio) {{
        audio.currentTime = bucketToMs(selectionBucket) / 1000;
      }}
      timeSlider.value = String(bucketToMs(selectionBucket));
    }}

    function syncSelectionFromAudio() {{
      const timeMs = Math.round(audio.currentTime * 1000);
      if (timeMs < regionStartMs || timeMs > regionEndMs) {{
        timeChip.textContent = formatMs(timeMs);
        return;
      }}
      selectBucket(msToBucket(timeMs), false);
    }}

    const pathPoints = data.decoder.bucket_to_state || [];
    const labels = stateRows.map((row) => row.label);
    const trace = data.decoder.phrase_trace || [];
    pathSummaryEl.innerHTML = trace.map((item, index) => `
      <div>
        Step ${{index + 1}}: prev state = ${{(item.previous_state_index ?? item.previous_word_index) === null ? 'start' : stateLabel(item.previous_state_index ?? item.previous_word_index)}},
        state word = ${{item.start_word_index}},
        buckets = ${{item.start_bucket}}-${{item.end_bucket}},
        repair width = ${{item.repair_width}}
      </div>
    `).join('');
    drawHeatmap(scoringChart, data.decoder.scoring_matrix || [], pathPoints, labels, 'scoring', 'score_matrix');
    drawHeatmap(dpChart, data.decoder.dp_scores || [], pathPoints, labels, 'dp', 'dp');
    drawHeatmap(
      silenceChart,
      [data.decoder.bucket_silence_scores || []],
      [],
      ['silence'],
      'silence',
      'silence_score'
    );
    updateTimeSelectionSummary();
    const initialRange = syncBucketRangeToTimeSelection();
    updateRangeSummary();
    updateChartRange('scoring', initialRange.startBucket, initialRange.endBucket);
    updateChartRange('dp', initialRange.startBucket, initialRange.endBucket);

    document.getElementById('jump-region-start').addEventListener('click', () => {{
      audio.currentTime = regionStartMs / 1000;
      selectBucket(0, false);
    }});
    document.getElementById('play-region').addEventListener('click', () => {{
      playBucketRange(0, Math.max(0, (data.decoder.bucket_count || 1) - 1));
    }});
    document.getElementById('pause-audio').addEventListener('click', () => {{
      playUntilSeconds = null;
      playbackRange = null;
      audio.pause();
    }});
    timeSlider.addEventListener('input', () => {{
      const ms = Number(timeSlider.value);
      audio.currentTime = ms / 1000;
      selectBucket(msToBucket(ms), false);
    }});
    selectionStartSlider.addEventListener('input', () => {{
      const state = syncBucketRangeToTimeSelection();
      chartRangeAnchorBucket = state.startBucket;
      updateTimeSelectionSummary();
      updateRangeSummary();
      updateChartRange('scoring', state.startBucket, state.endBucket);
      updateChartRange('dp', state.startBucket, state.endBucket);
    }});
    selectionEndSlider.addEventListener('input', () => {{
      const state = syncBucketRangeToTimeSelection();
      chartRangeAnchorBucket = state.startBucket;
      updateTimeSelectionSummary();
      updateRangeSummary();
      updateChartRange('scoring', state.startBucket, state.endBucket);
      updateChartRange('dp', state.startBucket, state.endBucket);
    }});
    rangeStartBucketInput.addEventListener('input', () => {{
      const range = updateRangeSummary();
      chartRangeAnchorBucket = range.start;
      selectionStartSlider.value = String(bucketToMs(range.start));
      selectionEndSlider.value = String(bucketToMs(range.end + 1));
      updateTimeSelectionSummary();
      updateChartRange('scoring', range.start, range.end);
      updateChartRange('dp', range.start, range.end);
    }});
    rangeEndBucketInput.addEventListener('input', () => {{
      const range = updateRangeSummary();
      chartRangeAnchorBucket = range.start;
      selectionStartSlider.value = String(bucketToMs(range.start));
      selectionEndSlider.value = String(bucketToMs(range.end + 1));
      updateTimeSelectionSummary();
      updateChartRange('scoring', range.start, range.end);
      updateChartRange('dp', range.start, range.end);
    }});
    document.getElementById('set-range-start').addEventListener('click', () => {{
      rangeStartBucketInput.value = String(selectionBucket);
      const range = updateRangeSummary();
      chartRangeAnchorBucket = range.start;
      selectionStartSlider.value = String(bucketToMs(range.start));
      selectionEndSlider.value = String(bucketToMs(range.end + 1));
      updateTimeSelectionSummary();
      updateChartRange('scoring', range.start, range.end);
      updateChartRange('dp', range.start, range.end);
    }});
    document.getElementById('set-range-end').addEventListener('click', () => {{
      rangeEndBucketInput.value = String(selectionBucket);
      const range = updateRangeSummary();
      chartRangeAnchorBucket = range.start;
      selectionStartSlider.value = String(bucketToMs(range.start));
      selectionEndSlider.value = String(bucketToMs(range.end + 1));
      updateTimeSelectionSummary();
      updateChartRange('scoring', range.start, range.end);
      updateChartRange('dp', range.start, range.end);
    }});
    document.getElementById('play-bucket-range').addEventListener('click', () => {{
      const range = updateRangeSummary();
      playBucketRange(range.start, range.end);
    }});
    document.getElementById('play-current-bucket').addEventListener('click', () => {{
      playBucketRange(selectionBucket, selectionBucket);
    }});
    document.getElementById('set-selection-start').addEventListener('click', () => {{
      selectionStartSlider.value = String(Math.round(audio.currentTime * 1000));
      const state = syncBucketRangeToTimeSelection();
      chartRangeAnchorBucket = state.startBucket;
      updateTimeSelectionSummary();
      updateRangeSummary();
      updateChartRange('scoring', state.startBucket, state.endBucket);
      updateChartRange('dp', state.startBucket, state.endBucket);
    }});
    document.getElementById('set-selection-end').addEventListener('click', () => {{
      selectionEndSlider.value = String(Math.round(audio.currentTime * 1000));
      const state = syncBucketRangeToTimeSelection();
      chartRangeAnchorBucket = state.startBucket;
      updateTimeSelectionSummary();
      updateRangeSummary();
      updateChartRange('scoring', state.startBucket, state.endBucket);
      updateChartRange('dp', state.startBucket, state.endBucket);
    }});
    document.getElementById('play-time-selection').addEventListener('click', () => {{
      const selection = normalizedTimeSelection();
      const range = syncBucketRangeToTimeSelection();
      chartRangeAnchorBucket = range.startBucket;
      updateTimeSelectionSummary();
      updateRangeSummary();
      updateChartRange('scoring', range.startBucket, range.endBucket);
      updateChartRange('dp', range.startBucket, range.endBucket);
      audio.currentTime = selection.start / 1000;
      playbackRange = {{ start: range.startBucket, end: range.endBucket }};
      playUntilSeconds = Math.min(regionEndMs, selection.end) / 1000;
      audio.play();
    }});
    showBucketBtn.addEventListener('click', () => selectBucket(Number(bucketInput.value), false));
    document.addEventListener('mouseup', () => {{
      chartDragState = null;
    }});
    document.addEventListener('keydown', (event) => {{
      if (event.target && ['INPUT', 'TEXTAREA'].includes(event.target.tagName)) return;
      if (event.key === 'ArrowLeft') {{
        event.preventDefault();
        selectBucket(selectionBucket - 1, true);
      }} else if (event.key === 'ArrowRight') {{
        event.preventDefault();
        selectBucket(selectionBucket + 1, true);
      }} else if (event.key === '[') {{
        event.preventDefault();
        rangeStartBucketInput.value = String(selectionBucket);
        const range = updateRangeSummary();
        chartRangeAnchorBucket = range.start;
        selectionStartSlider.value = String(bucketToMs(range.start));
        selectionEndSlider.value = String(bucketToMs(range.end + 1));
        updateTimeSelectionSummary();
        updateChartRange('scoring', range.start, range.end);
        updateChartRange('dp', range.start, range.end);
      }} else if (event.key === ']') {{
        event.preventDefault();
        rangeEndBucketInput.value = String(selectionBucket);
        const range = updateRangeSummary();
        chartRangeAnchorBucket = range.start;
        selectionStartSlider.value = String(bucketToMs(range.start));
        selectionEndSlider.value = String(bucketToMs(range.end + 1));
        updateTimeSelectionSummary();
        updateChartRange('scoring', range.start, range.end);
        updateChartRange('dp', range.start, range.end);
      }} else if (event.key === 'p' || event.key === 'P') {{
        event.preventDefault();
        playBucketRange(selectionBucket, selectionBucket);
      }} else if (event.key === 'r' || event.key === 'R') {{
        event.preventDefault();
        const range = normalizedRange();
        playBucketRange(range.start, range.end);
      }}
    }});
    audio.addEventListener('play', clampAudioToRegion);
    audio.addEventListener('timeupdate', () => {{
      clampAudioToRegion();
      if (audio.currentTime * 1000 >= regionEndMs) {{
        audio.pause();
        audio.currentTime = regionEndMs / 1000;
        playUntilSeconds = null;
        playbackRange = null;
        return;
      }}
      if (playUntilSeconds !== null && audio.currentTime >= playUntilSeconds) {{
        audio.pause();
        playUntilSeconds = null;
        playbackRange = null;
      }}
      syncSelectionFromAudio();
    }});
    audio.addEventListener('seeked', () => {{
      clampAudioToRegion();
      syncSelectionFromAudio();
    }});
    audio.addEventListener('pause', () => {{
      if (!audio.ended) {{
        playUntilSeconds = null;
        playbackRange = null;
      }}
    }});
    selectBucket(0, false);
  </script>
</body>
</html>
"""


def write_region_debug_html(output_path: Path, payload: dict) -> None:
    output_path.write_text(build_region_debug_html(payload), encoding="utf-8")


def write_region_debug_data_js(output_path: Path, payload: dict) -> None:
    output_path.write_text(
        "window.REGION_INSPECT_DATA = " + json.dumps(_build_chart_payload(payload), ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
