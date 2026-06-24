# Plan: `02_INITIAL.md`'yi Phase 1'e Odakla + Vizyonu Roadmap'e Ayır

## Context

`docs/02_INITIAL.md` şu anda hem ilk development phase kapsamını hem de uzun vadeli ürün
vizyonunu (screenshot extraction, görsel analiz, multimodal pipeline, OCR, video frame
intelligence) tek dokümanda barındırıyor. Bu dosya ileride üretilecek tüm deliverable'ların
(PRD, spec, task list, implementation plan) temel bağlam dokümanı olacak. Vizyon ve Phase 1
kapsamı aynı dokümanda karışık durdukça, downstream tüketicilerin ilk iterasyonun teslim
hedefini gelecekteki fikirlerle karıştırması (scope creep) riski var.

**Hedeflenen sonuç:** `02_INITIAL.md` Phase 1'e odaklı, dar ve net bir bağlam dokümanına
dönüşür; ertelenmiş vizyon hiç içerik kaybı olmadan ayrı bir `docs/03_ROADMAP.md`'ye taşınır.
Ayrıca Phase 1 kapsamına ait ama mevcut dokümanda eksik olan **LLM Entegrasyonu** ve **çıktı
saklama** gereksinimleri eklenir. Repo git ile initialize edilir ve değişiklikler commit'lenir.

**Karar (Adım 1): Seçenek B.** Ertelenen özellikler ayrı `docs/03_ROADMAP.md`'ye taşınır.
Genel/genişletilebilir mimari çerçeve (üretim/tüketim katmanı ayrımı, artifact soyutlaması) bir
"gelecek özelliği" değil temel tasarım ilkesi olduğu için `02`'de KALIR; yalnızca somut
ertelenmiş özellikler roadmap'e gider.

Diller: Dokümanlar Türkçe kalır (mevcut stil korunur).

---

## Adım 2 — Doküman Düzenlemesi

### 2a. `docs/02_INITIAL.md` — yeniden yapılandırılmış hedef yapı

KALAN bölümler (mevcut içerikten, gerekirse küçük düzenlemelerle):
- `# Proje Amacı` — aynen
- `# Temel Tasarım İlkesi: Üretim / Tüketim Ayrımı` — aynen (çekirdek ilke)
- `# Hedeflenen Kullanım Senaryoları (Örnekler)` — aynen; prompt seviyesinde
  değiştirilebilir olduğu vurgusu eklenir (LLM bölümüyle bağ)
- `# Girdi Modeli` — aynen (tek/çoklu URL, playlist, graceful degradation)
- `# Üretilecek Artifact Türleri (Phase 1)`:
  - `## Metadata Artifact'i` — aynen
  - `## Transcript Artifact'i` — aynen
  - `## Genişletilebilir Artifact Türleri` — SLİM hale getirilir: genişletilebilirlik
    *ilkesi* kalır, somut örnek liste (OCR, speaker segmentation vb.) → `03_ROADMAP.md`'ye
    referansla kısaltılır
- `# İlişkisel Bütünlük Gereksinimleri` — KALIR, ancak `## Görsel Artifact İlişkilendirme`
  alt bölümü çıkarılıp roadmap'e taşınır
- `# Bu Aşamada Beklenen Yaklaşım` — KALIR, Phase 1 odağına göre uyarlanır

YENİ eklenecek bölümler (komuttaki `<context>` Phase 1 kapsamından):
- `# Phase 1 Kapsamı` — bu iterasyonun teslim hedefinin kısa özeti; Phase 1 ötesi için
  `03_ROADMAP.md`'ye işaret eder
- `# LLM Entegrasyonu (Phase 1)` — ilk tüketici **OpenAI API**:
  - OpenAI API ile çağrı
  - Konfigüre edilebilir parametreler: model adı, temperature, max output/completion token,
    response format, timeout, retry, batch/concurrency limiti, ileride gerekebilecek diğerleri
  - Secret yönetimi: API key koda gömülmez; env variable / `.env` ile dışarıdan yönetilir
  - Promptlar harici dosyalardan okunur; farklı analiz görevleri için prompt seviyesinde
    değiştirilebilir (requirement extraction, product analysis vb. — sistem tek analiz türüne
    bağlı değil)
  - Transcript + metadata promptla birlikte modele gönderilir; tek/çoklu video
  - Uzun transcriptler için chunking / batching / video bazlı işleme ihtiyacı değerlendirilir
  - Model cevapları yapılandırılmış biçimde saklanır; parse edilebilirlik / structured output
    şeması spec'te tartışılacak açık nokta olarak işaretlenir
- `# Çıktı Formatı ve Saklama (Phase 1)` — format henüz kesinleşmedi (JSON, Markdown, tek/çoklu
  dosya); mimari bu kararın sonradan değişmesine izin verecek şekilde tasarlanmalı
- `# Phase 1 Dışındakiler` — non-goals listesi + `docs/03_ROADMAP.md`'ye çapraz referans:
  screenshot extraction, zaman damgalı görsel artifact, OCR, görsel analiz, multimodal
  pipeline, video frame intelligence, diğer gelişmiş artifact türleri

### 2b. `docs/03_ROADMAP.md` — yeni doküman (taşınan vizyon, içerik kaybı YOK)

- `# Amaç` — uzun vadeli vizyon dokümanı; Phase 1 bağlamı için `02_INITIAL.md`'ye çapraz
  referans; bu özelliklerin ilk iterasyon teslim hedefi olmadığı notu
- `# Görsel (Screenshot) Artifact'i` — `02`'den taşınan tam içerik:
  - giriş + sağladığı değer listesi
  - `## Zaman Seçimi Problemi` + tüm otomatik seçim stratejileri
  - `## Görsel Artifact İlişkilendirme` (screenshot↔transcript/metadata alanları)
- `# Diğer Gelecek Artifact Türleri` — `02`'den taşınan örnekler: segment/chunk birimleri,
  entity extraction, OCR, speaker/topic segmentation, multimodal, video frame intelligence
- `# Uzun Vadeli Kullanım Senaryosu Genişlemesi` — multimodal analiz ile zenginleşen nihai
  hedef (mevcut "Nihai Hedef" bölümünün görsel-bağlamlı kısmı buraya taşınır)

### 2c. Çapraz referans tutarlılığı
- `02` → `03`: "Phase 1 Dışındakiler" ve slim genişletilebilirlik bölümünden roadmap'e link
- `03` → `02`: roadmap girişinden Phase 1 bağlam dokümanına link
- `01_INITIAL.md` dokunulmadan bırakılır (orijinal/tarihsel kayıt)

---

## Adım 3 — Doğrulama
- `docs/02_INITIAL.md` ve `docs/03_ROADMAP.md` son hallerini göster
- `tree` / `ls -R` ile repo dosya yapısını listele
- Git init sonrası `git diff --staged` (veya ilk commit öncesi `git status` + diff) ile özet
- İçerik kaybı kontrolü: mevcut `02`'deki her bölümün ya yeni `02`'de ya `03`'te karşılığı
  olduğunu doğrula (özellikle screenshot stratejileri ve ilişkilendirme alanları)

---

## Adım 4 — Git Repository ve Commit
- `git init -b main` (repo henüz yok; root: `/Users/alikemal/DevLab/youtube-intelligence-pipeline`)
- `.gitignore` oluştur — Python projesi odaklı:
  - Python: `__pycache__/`, `*.pyc`, `.venv/`, `venv/`, `*.egg-info/`, `build/`, `dist/`,
    `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
  - Secrets: `.env`, `.env.*` (`!.env.example` istisnası)
  - IDE/OS: `.vscode/`, `.idea/`, `.DS_Store`
  - Çıktı/veri (ileride): `output/`, `data/`, `*.log`
- Commit: `~/.claude/skills/commit` (custom `/commit` skill) bulundu → bu skill'i çağırarak
  commit yap; skill'in beklediği workflow'u (güvenlik taraması, staging, Conventional Commits
  mesajı, tek y/n onayı) takip et. Önerilen kapsam: `docs:` tipi (doküman yeniden yapılandırma)
  + `.gitignore`. Skill mesaj formatını kendi üretecek.

---

## Notlar
- Hiçbir Phase 1 gereksinimi atlanmaz; mevcut `02`'nin özü korunur, yalnızca doğru dokümana
  yerleştirilir ve eksik Phase 1 kapsamı (LLM entegrasyonu, çıktı saklama) eklenir.
- `01_INITIAL.md` referans olarak korunur, değiştirilmez.
