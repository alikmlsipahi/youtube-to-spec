<!--
  Output document skeleton for the spec-distiller.

  Both engines emit the SAME shape:
   - The OpenAI engine generates this layout programmatically (render_markdown).
   - The Claude-native engine fills THIS template from the structured document.

  Keep this skeleton in sync with the OpenAI engine's rendered output so the two
  engines stay interchangeable. `<…>` marks content to fill; repeat the module,
  feature, and requirement blocks as needed. Omit the trace suffix when a
  requirement has no timestamp/segment.
-->

# <video_title>

- **URL:** <video_url>
- **Channel:** <channel>
- **Collection:** <collection_title>

## Summary

<one short paragraph: what the video covers and the scope of the requirements>

## Requirements

### <MODULE> — <Module title>

#### <FEATURE> — <Feature title>

- **<MODULE>-<FEATURE>-001**: <atomic, testable requirement statement> _(trace: timestamp <MM:SS>, segment <segment_index>)_
- **<MODULE>-<FEATURE>-002**: <next requirement> _(trace: timestamp <MM:SS>, segment <segment_index>)_

<!-- repeat #### feature blocks within a module, and ### module blocks as needed -->

## Assumptions

- <thing inferred that the video did not state explicitly>

## Open Questions

- <genuine ambiguity a human should resolve>
