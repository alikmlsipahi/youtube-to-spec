# YouTube Intelligence Pipeline — Implementation Guide

> Bu döküman, `IMPLEMENTATION_PLAN_v2.md` planını adım adım implemente etmek için gereken session'ları, prompt'ları ve progress tracking'i içerir. Takip ederek sıfırdan tamamlanmış pipeline'a ulaşabilirsin.

---

## Ön Hazırlık (Bir Kerelik)

### H1. spec-writer skill'ini kur

`dannwaneri/spec-writer` (10 star, Agent Skills standard uyumlu) — spec yazarken assumption'ları otomatik flag'ler, Given/When/Then acceptance criteria üretir.

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/dannwaneri/spec-writer.git ~/.claude/skills/spec-writer
```

### H2. Progress tracker'ı sıfırla

`docs/IMPLEMENTATION_PLAN-progress.md` dosyasındaki tüm satırların `[pending]` olduğunu doğrula (clean reset zaten yapıldıysa hazır).

---

## Session Yapısı

Plan 5 ayrı agent rolü tanımlıyor ama pratikte **2 session'a** indirgenebilir. Kural tek: **test'i gören agent ≠ kodu yazan agent.**

| Session | Rol | Ne yapar | Ne okuyabilir | Ne okuyamaz |
|---------|-----|----------|---------------|-------------|
| **Session 1** | Spec Author + Test Writer | Spec yazar, test + fixture yazar | Her şey (plan, schema, brief, reuse source) | — |
| **Session 2** | Blind Implementer + Verifier + Reviser | Spec'ten kod yazar, test çalıştırır, fix'ler | Spec, schema, reuse source, CLAUDE.md | `**/tests/**`, `**/conftest.py`, `**/fixtures/**` |

Bu 2-session döngüsü her A bloğu için tekrarlanır (A1, A2, A3, A4, A5 = toplam 10 session). Phase C ve B için farklı session'lar eklenir.

---

## Detaylı Adımlar

### ═══════════════════════════════════════════
### BLOK A1 — Skill 1 Pure Helpers (T-S1-01..04)
### ═══════════════════════════════════════════

**Kapsam:** `extract_video_id`, `format_timestamp`, `classify_input`, `slugify`/`collection_dir_name`

---

#### A1 — SESSION 1: Spec + Test Yazımı

**Prompt:**

```
Read these files first:
- docs/IMPLEMENTATION_PLAN_v2.md (the authoritative plan — focus on §Skill 1, §Testable requirements T-S1-01 through T-S1-04, §Canonical per-video JSON schema, §Reuse from the existing skill)
- docs/02_PRODUCT_BRIEF.md (§Girdi Modeli, §Transcript Artifact'i)
- docs/03_ROADMAP.md (§Görsel Artifact — for understanding why segment index matters)
- .claude/skills/youtube-transcript/scripts/get_transcript.py (reuse source)
- CLAUDE.md

Now do two things, in order:

STEP 1 — Write behavioral specs for T-S1-01 through T-S1-04.
Use the /spec-writer skill's methodology: for each unit, produce:
- One-line purpose
- Function signature (from the plan's §Functions)
- Inputs with types
- Expected behavior in prose (not code)
- Edge cases
- Given/When/Then acceptance scenarios
- Assumptions (flag with [ASSUMPTION: ...] anything the plan doesn't explicitly state)
- Key entities (relevant canonical schema excerpt)
- [NEEDS CLARIFICATION: ...] markers for anything ambiguous

Save each spec to: docs/specs/A1-T-S1-0X-<unit_name>.spec.md

STEP 2 — Write unit tests + fixtures for T-S1-01 through T-S1-04.
Follow the plan's test strategy:
- pytest, invoked via `uv run --with pytest pytest`
- Fixtures in tests/fixtures/inputs/ (captured real data) and tests/fixtures/expected/ (golden outputs)
- conftest.py for shared setup
- All tests offline/deterministic (no network)
- Save to: .claude/skills/youtube-artifact-collector/tests/

After completing, report ONLY:
- File paths created
- Test count per file
- Do NOT share any assertion text or test code content

Then update docs/IMPLEMENTATION_PLAN-progress.md:
- T-S1-01 → [spec]
- T-S1-02 → [spec]
- T-S1-03 → [spec]
- T-S1-04 → [spec]

After tests are written, update to [test-written] for each.
```

**Beklenen çıktı:**
- 4 spec dosyası: `docs/specs/A1-T-S1-01-extract_video_id.spec.md` vb.
- Test dosyaları: `tests/test_pure_helpers.py`, `tests/conftest.py`, `tests/fixtures/inputs/video_id_urls.json` vb.
- Progress: T-S1-01..04 → `[test-written]`

---

#### A1 — SESSION 2: Blind Implementation + Verification

**Prompt:**

```
You are a BLIND IMPLEMENTER. You must follow these rules strictly:

DENYLIST — You must NEVER open or read any file under:
- **/tests/**
- **/conftest.py
- **/fixtures/**

You may read:
- docs/specs/A1-T-S1-01-extract_video_id.spec.md
- docs/specs/A1-T-S1-02-format_timestamp.spec.md
- docs/specs/A1-T-S1-03-classify_input.spec.md
- docs/specs/A1-T-S1-04-slugify.spec.md
- docs/IMPLEMENTATION_PLAN_v2.md (§Skill 1 Functions, §Canonical JSON, §CLI)
- .claude/skills/youtube-transcript/scripts/get_transcript.py (reuse source — copy extract_video_id and format_timestamp verbatim from lines 19-29 and 32-39)
- CLAUDE.md

TASK: Implement the functions specified in the specs into:
.claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py

Include the PEP-723 header from the plan. Write ONLY the functions covered by T-S1-01..04. Do NOT run the tests yourself.

After writing the code, update progress:
- T-S1-01..04 → [code-written]

THEN switch to VERIFIER role:
Run: uv run --with pytest pytest .claude/skills/youtube-artifact-collector/tests/ -v

If all pass → update progress to [green] for each.

If any fail → for EACH failure, describe the behavioral gap in plain language.
Example: "does not emit HH:MM:SS format when seconds >= 3600"
Do NOT include assertion text, line numbers, or expected values.
Then fix the code (max 3 iterations) using ONLY the behavioral gap descriptions + specs.
After each fix, re-run tests.
Final state: update progress to [green] when all pass.
```

**Beklenen çıktı:**
- `extract_artifacts.py` dosyasında 4 fonksiyon implement edilmiş
- Progress: T-S1-01..04 → `[green]`

---

### ═══════════════════════════════════════════
### BLOK A2 — Skill 1 Metadata + Transcript + Segments (T-S1-05..07)
### ═══════════════════════════════════════════

**Kapsam:** `build_video_block`, `select_transcript_track`, `build_segments`

#### A2 — SESSION 1: Spec + Test Yazımı

**Prompt:** Yukarıdaki A1-Session 1 prompt'unun aynısı, şu değişikliklerle:
- T-S1-01..04 yerine **T-S1-05, T-S1-06, T-S1-07** referansları
- Spec dosyaları: `docs/specs/A2-T-S1-05-build_video_block.spec.md` vb.
- Plan'dan odaklanılacak bölümler: §Canonical per-video JSON (video{} block), §Functions 3-4, transcript language preference logic
- Fixtures: captured yt-dlp JSON sample, mocked transcript track objects
- Progress hedefi: T-S1-05..07 → `[test-written]`

#### A2 — SESSION 2: Blind Implementation + Verification

**Prompt:** A1-Session 2 prompt'unun aynısı, şu değişikliklerle:
- Okuması gereken spec'ler: `A2-T-S1-05/06/07`
- Mevcut `extract_artifacts.py`'ye yeni fonksiyonları ekle (üstüne yaz değil, ekle)
- Progress hedefi: T-S1-05..07 → `[green]`

---

### ═══════════════════════════════════════════
### BLOK A3 — Skill 1 Markdown + Manifest + Degradation (T-S1-08..11)
### ═══════════════════════════════════════════

**Kapsam:** `render_markdown`, `build_manifest`, `parse_hidden_unavailable`, graceful degradation

#### A3 — SESSION 1: Spec + Test

Aynı kalıp. T-S1-08..11 referansları. Spec dosyaları `docs/specs/A3-*`. Odak: §render_markdown, §_manifest.json shape, §graceful degradation, stderr WARNING parsing.

#### A3 — SESSION 2: Blind Implement + Verify

Aynı kalıp. Mevcut `extract_artifacts.py`'ye ekleme. Progress → `[green]`.

---

### ═══════════════════════════════════════════
### BLOK A4 — Skill 2 Config + Prompt + ID Scheme (T-S2-01, 02, 04, 05)
### ═══════════════════════════════════════════

**Kapsam:** `config resolution`, `fill_prompt`, `validate_req_id`, composite-key uniqueness

#### A4 — SESSION 1: Spec + Test

Aynı kalıp. T-S2-01, 02, 04, 05. Spec dosyaları `docs/specs/A4-*`. Odak: §Skill 2, §Requirement ID scheme, §CLI (OpenAI engine), config precedence (CLI > env > default).

#### A4 — SESSION 2: Blind Implement + Verify

Hedef dosya: `.claude/skills/feature-requirement-extractor/scripts/extract_requirements.py`. PEP-723 header with `openai, python-dotenv` deps. Progress → `[green]`.

---

### ═══════════════════════════════════════════
### BLOK A5 — Skill 2 Response Render + Input Resolution + Env (T-S2-03, 06, 07)
### ═══════════════════════════════════════════

**Kapsam:** `parse_response`/`render`, env key loading, input resolution

#### A5 — SESSION 1: Spec + Test

Aynı kalıp. T-S2-03, 06, 07. Spec dosyaları `docs/specs/A5-*`. Odak: json_schema response → Markdown + JSON rendering, manifest iteration, missing OPENAI_API_KEY handling.

#### A5 — SESSION 2: Blind Implement + Verify

Mevcut `extract_requirements.py`'ye ekleme. Progress → `[green]`.

---

### ═══════════════════════════════════════════
### PHASE C — Authoring (Non-Blind)
### ═══════════════════════════════════════════

> Tüm A blokları green olduktan sonra. Tests denylist'i hâlâ geçerli ama blind değil — bitmiş script'leri okuyabilir.

#### C — TEK SESSION

**Prompt:**

```
You are the AUTHORING AGENT. All A-block units are green.

DENYLIST (still applies): Do NOT read **/tests/**, **/conftest.py**, **/fixtures/**

You MAY read the finished scripts:
- .claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py
- .claude/skills/feature-requirement-extractor/scripts/extract_requirements.py
- docs/IMPLEMENTATION_PLAN_v2.md (§SKILL.md trigger, §Phase C, §Skill 2 prompts/templates)
- CLAUDE.md

TASK — Author these files in order:

C1: .claude/skills/youtube-artifact-collector/SKILL.md
- YAML frontmatter: name + description with de-confliction trigger ("not a quick single-video transcript dump")
- Usage section with CLI flags AS ACTUALLY SHIPPED (read from the finished script's argparse)
- Update progress: SK1-DOC → [drafted]

C2: Skill 2 swappable assets:
- .claude/skills/feature-requirement-extractor/prompts/system_prompt.md
- .claude/skills/feature-requirement-extractor/prompts/extraction_prompt.md
  (with {{placeholders}} matching fill_prompt's contract + module/action code lookup table for <MODULE>-<FEATURE>-<NNN>)
- .claude/skills/feature-requirement-extractor/templates/requirement_doc.md
- .claude/skills/feature-requirement-extractor/.env.example (OPENAI_API_KEY=your_key_here)
- Update progress: SK2-ASSETS → [drafted]

C3: .claude/skills/feature-requirement-extractor/SKILL.md
- Claude-native engine instructions (read artifact JSON + manifest, read prompt/template files, fill, write/print)
- Consumption trigger ("from already-extracted artifacts")
- Optional --engine openai note
- DEPENDS ON C2 (reference the prompt/template files by path)
- Update progress: SK2-DOC → [drafted]
```

**Beklenen çıktı:** 6 dosya yazılmış, progress'te SK1-DOC, SK2-ASSETS, SK2-DOC → `[drafted]`

---

### ═══════════════════════════════════════════
### PHASE B — Integration + Acceptance Gates
### ═══════════════════════════════════════════

> Phase C tamamlandıktan sonra. Gerçek network gerektirir.

#### B1-B3 — SESSION (Skill 1 Integration)

**Prompt:**

```
Run integration tests for Skill 1. Execute these in order:

B1: uv run .claude/skills/youtube-artifact-collector/scripts/extract_artifacts.py fl1DSmwQKKY --print
Expected: 60 Turkish auto segments, selected.type:"auto", available_tracks=[tr], full metadata.
Verify and report.

B2: Run same WITHOUT --print.
Expected: data/_singles/fl1DSmwQKKY.json + .md created. Segments carry index field.
Verify file exists and structure.

B3: Run on playlist URL: https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Expected: data/<slug>-PLk.../ folder with _manifest.json, per-video JSON+MD.
Manifest has hidden_unavailable_count:5, ordered members, failures recorded with status.
Verify and report.

Update progress for I-01, I-02 based on results.
```

#### B4 — SESSION (Trigger Test)

```
Test: provide a watch?v=...&list=... URL. Confirm single video by default, --playlist expands.
Test: ask Claude "collect artifacts for this playlist" — verify youtube-artifact-collector SKILL.md fires, NOT youtube-transcript.
Update: A-01 → [accepted], SK1-DOC → [accepted]
```

#### B5-B6 — SESSION (Skill 2 Integration)

```
B5: Use Claude-native engine — point at data/_singles/fl1DSmwQKKY.json.
Read prompts/extraction_prompt.md and templates/requirement_doc.md.
Produce filled requirement doc with <MODULE>-<FEATURE>-NNN codes + traces.
Verify codes match pattern, traces reference real segment times.
Update: A-02, A-03 → [accepted], SK2-ASSETS → [accepted], SK2-DOC → [accepted]

B6 (optional, needs OpenAI key): Run extract_requirements.py with .env.
Verify same JSON/MD shape as Claude-native output.
Update: I-03 based on result.
```

#### B7 — Deprecation (Kullanıcı Onayı Gerekli)

```
Deprecate youtube-transcript skill:
- Remove or archive .claude/skills/youtube-transcript/
- Update skills-lock.json at repo root
- Commit with: chore: deprecate youtube-transcript skill
ONLY proceed with explicit user confirmation.
```

---

## Progress Tracker Şablonu

Her adımdan sonra `docs/IMPLEMENTATION_PLAN-progress.md` güncellenir. State geçişleri:

```
pending → spec → test-written → code-written → green → accepted
```

Authoring satırları için:
```
pending → drafted → accepted
```

Tüm satırlar ve beklenen final durumları:

```
## Skill 1 — youtube-artifact-collector
- [green] T-S1-01 — extract_video_id
- [green] T-S1-02 — format_timestamp
- [green] T-S1-03 — classify_input
- [green] T-S1-04 — slugify / collection_dir_name
- [green] T-S1-05 — build_video_block
- [green] T-S1-06 — select_transcript_track
- [green] T-S1-07 — build_segments
- [green] T-S1-08 — render_markdown
- [green] T-S1-09 — build_manifest
- [green] T-S1-10 — parse_hidden_unavailable
- [green] T-S1-11 — graceful degradation

## Skill 2 — feature-requirement-extractor
- [green] T-S2-01 — config resolution
- [green] T-S2-02 — fill_prompt
- [green] T-S2-03 — parse_response / render
- [green] T-S2-04 — validate_req_id
- [green] T-S2-05 — composite-key uniqueness
- [green] T-S2-06 — env key loading
- [green] T-S2-07 — input resolution

## Authoring (non-blind)
- [accepted] SK1-DOC — youtube-artifact-collector/SKILL.md
- [accepted] SK2-ASSETS — prompts + templates + .env.example
- [accepted] SK2-DOC — feature-requirement-extractor/SKILL.md

## Integration
- [accepted] I-01 — Skill 1 single video (fl1DSmwQKKY)
- [accepted] I-02 — Skill 1 playlist + graceful degradation
- [accepted] I-03 — Skill 2 OpenAI engine

## Acceptance
- [accepted] A-01 — Skill 1 SKILL.md trigger
- [accepted] A-02 — Skill 2 SKILL.md trigger
- [accepted] A-03 — Claude-native engine output quality
- [accepted] A-04 — Prompt swap without code edit
```

---

## Toplam Session Sayısı

| Faz | Session | Açıklama |
|-----|---------|----------|
| A1 | 2 | Spec+Test → Blind Implement |
| A2 | 2 | Spec+Test → Blind Implement |
| A3 | 2 | Spec+Test → Blind Implement |
| A4 | 2 | Spec+Test → Blind Implement |
| A5 | 2 | Spec+Test → Blind Implement |
| C | 1 | Authoring (SKILL.md + prompts + templates) |
| B1-B3 | 1 | Skill 1 integration |
| B4 | 1 | Trigger test |
| B5-B6 | 1 | Skill 2 integration |
| B7 | 1 | Deprecation (optional) |
| **Toplam** | **~15** | |

---

## Özet Akış

```
H1-H2 (hazırlık)
  │
  ▼
A1 Session 1 → A1 Session 2 → progress [green]
  │
  ▼
A2 Session 1 → A2 Session 2 → progress [green]
  │
  ▼
A3 Session 1 → A3 Session 2 → progress [green]
  │
  ▼
A4 Session 1 → A4 Session 2 → progress [green]
  │
  ▼
A5 Session 1 → A5 Session 2 → progress [green]
  │
  ▼
Phase C (tek session) → progress [drafted]
  │
  ▼
B1-B3 → B4 → B5-B6 → progress [accepted]
  │
  ▼
B7 (deprecation, onay ile)
  │
  ▼
✅ DONE
```
