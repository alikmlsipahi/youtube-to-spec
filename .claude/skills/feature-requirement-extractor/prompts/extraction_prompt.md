Extract the software requirements demonstrated in the following video, organized
as **Module → Feature → Requirement**, and return them as the strict JSON object
described in the system prompt.

## Source video

- **Video ID:** {{video_id}}
- **Title:** {{video_title}}
- **URL:** {{video_url}}
- **Channel:** {{channel}}
- **Collection / module:** {{collection_title}}

### Description

{{description}}

### Transcript (segment-indexed)

Each line is `[<segment_index>] (<start>s) <text>`. Use the `<segment_index>` and
the `<start>` time to populate each requirement's `trace`.

{{transcript}}

## Module / action code lookup table

Use this table to normalize `<MODULE>` and `<FEATURE>` codes. It is a *starting
point* — if the video clearly belongs to a module or action not listed, coin a
code in the same style (MODULE: 3–6 uppercase; ACTION: short uppercase verb) and
note the new code in `assumptions`.

### MODULE codes (from the collection / module title)

| Domain area (TR / EN)              | MODULE |
| ---------------------------------- | ------ |
| Kayıt / Registration               | REG    |
| Sınav / Exam                       | EXAM   |
| Yoklama, Devamsızlık / Attendance  | ATTND  |
| Not, Değerlendirme / Grading       | GRADE  |
| Raporlama / Reporting              | RPT    |
| Kullanıcı / User management        | USER   |
| Yetki, Rol / Authorization, Roles  | AUTH   |
| Ayarlar / Settings                 | CFG    |
| Ödeme, Tahsilat / Payment          | PAY    |
| Bildirim / Notification            | NOTIF  |

### ACTION codes (the verb part of `<FEATURE>`)

| Action (TR)        | Action (EN)   | ACTION   |
| ------------------ | ------------- | -------- |
| ekle               | add           | ADD      |
| sil                | delete        | DEL      |
| toplu sil          | bulk delete   | BULK-DEL |
| güncelle           | update        | UPD      |
| kaydet             | save          | SAVE     |
| listele            | list          | LIST     |
| görüntüle          | view          | VIEW     |
| seç                | select        | SEL      |
| ara, sorgula       | search        | SRCH     |
| onayla             | approve       | APPR     |
| dışa aktar         | export        | EXP      |
| içe aktar          | import        | IMP      |
| filtrele           | filter        | FILT     |

### ENTITY suffixes (optional, for `ACTION-ENTITY` features)

| Entity (TR / EN)        | ENTITY |
| ----------------------- | ------ |
| Öğrenci / Student       | STU    |
| Sınıf / Class           | CLS    |
| Kullanıcı / User        | USR    |
| Ders / Course           | CRS    |
| Kayıt / Record          | REC    |

`<FEATURE>` is either an `ACTION` (e.g. `LIST`, `GRADE`) or `ACTION-ENTITY`
(e.g. `ADD-STU`, `BULK-DEL`). Keep the whole feature code within 3–10 characters.

## Task

1. Identify the **module** the video belongs to (from its collection/module
   title) and assign its `<MODULE>` code.
2. Walk the transcript in order and identify each distinct **feature** and the
   **requirements** it demonstrates.
3. Number requirements video-locally from `001`, building each `id` as
   `<MODULE>-<FEATURE>-<NNN>`.
4. Set every requirement's `source_video_id` to `{{video_id}}` and fill its
   `trace` from the supporting transcript segment.
5. Record anything inferred in `assumptions` and any genuine ambiguity in
   `open_questions`.

Return only the JSON object.
