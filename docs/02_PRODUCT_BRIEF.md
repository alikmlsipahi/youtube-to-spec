# Proje Amacı

Amacım, video kaynaklarından mümkün olduğunca yüksek kaliteli, yapılandırılmış ve LLM dostu **artifact**'ler üretebilen bir veri toplama ve hazırlama sistemi geliştirmektir.

Sistemin temel görevi belirli bir analiz türünü gerçekleştirmek değildir. Temel görev, video kaynaklarındaki bilgiyi (konuşma, metin, zaman ve yapı) kayıpsız ve ilişkilerini koruyarak makine tarafından işlenebilir artifact'lere dönüştürmektir.

Bu artifact'ler daha sonra farklı LLM görevlerinde girdi olarak kullanılabilir. Hangi analiz görevinin yapılacağı sistemin sorumluluğu değildir; sistem yalnızca o analizlerin dayanacağı temeli üretir.

Bu nedenle proje, belirli bir domain'e, belirli bir çıktı türüne veya tek bir kullanım senaryosuna bağlı değildir. Proje, video → artifact dönüşümünü gerçekleştiren genel amaçlı bir pipeline olarak tasarlanmalıdır.

> Bu doküman, ilk development phase'in (**Phase 1**) bağlam dokümanıdır ve sonraki tüm deliverable'ların (PRD, spec, task list, implementation plan) temelini oluşturur. Phase 1 kapsamı dışındaki uzun vadeli vizyon (görsel/screenshot artifact'leri, multimodal pipeline, OCR vb.) ayrı bir dokümanda tutulur: bkz. [`03_ROADMAP.md`](03_ROADMAP.md).

# Temel Tasarım İlkesi: Üretim / Tüketim Ayrımı

Sistemin mimari vizyonu iki katmanın net biçimde ayrılmasına dayanır:

* **Üretim katmanı (bu projenin kapsamı):** Video kaynaklarından metadata, transcript ve gelecekte eklenebilecek diğer veri türlerini içeren yüksek kaliteli artifact'ler üretir.
* **Tüketim katmanı (bu projenin kapsamı dışında, ancak hedef kitlesi):** Üretilen artifact'leri kullanarak LLM destekli görevler yürütür.

Bu projenin başarısı, ürettiği artifact'lerin kalitesi, zenginliği ve ilişkisel bütünlüğü ile ölçülür; herhangi bir tekil tüketim senaryosunun başarısı ile değil.

Phase 1'de tüketim katmanının ilk somut örneği de bu repoda geliştirilir (bkz. [LLM Entegrasyonu](#llm-entegrasyonu-phase-1)). Ancak bu, sistemi tek bir analiz türüne bağlamaz: tüketim katmanı, prompt seviyesinde değiştirilebilir tutularak üretim katmanından bağımsız kalır.

# Hedeflenen Kullanım Senaryoları (Örnekler)

Üretilen artifact'ler aşağıdaki gibi çeşitli görevlerde kullanılabilir. Bu liste sistemin tasarımını kısıtlamaz; yalnızca artifact kalitesinin neden önemli olduğunu örneklemek içindir:

* Requirement extraction ve functional requirement üretimi
* Product discovery ve feature analizi
* Business rule / iş kuralı çıkarımı
* Software specification ve documentation generation
* Knowledge extraction ve bilgi tabanı oluşturma
* Workflow / süreç analizi
* Dataset generation (eğitim veya değerlendirme verisi)
* Modül–feature gibi yapısal ilişkilerin çıkarımı
* Henüz öngörülmemiş diğer LLM destekli analizler

Bu senaryolardan herhangi biri (örneğin bir yazılım ürününün kullanım rehberi videolarından ürün bilgisi çıkarmak) sistemin **bir** uygulamasıdır, sistemin kendisi değildir. Bu senaryolar arasındaki geçiş, sistemin yeniden yazılmasıyla değil, kullanılan prompt'un değiştirilmesiyle sağlanabilmelidir.

# Phase 1 Kapsamı

İlk iterasyonun teslim hedefi üç yetenekle sınırlıdır:

1. **Video metadata toplama** — tek video, çoklu video ve playlist girdileri için.
2. **Transcript toplama** — zaman damgalı, yapılandırılmış transcript artifact'leri.
3. **LLM entegrasyonu** — üretilen artifact'leri konfigüre edilebilir bir şekilde bir LLM'e (ilk olarak OpenAI API) gönderip cevapları yapılandırılmış biçimde saklama.

Bu iterasyonun teslim hedefi **olmayan** özellikler için bkz. [Phase 1 Dışındakiler](#phase-1-dışındakiler) ve [`03_ROADMAP.md`](03_ROADMAP.md).

# Girdi Modeli

Sistem, çeşitli granülerlikte video kaynaklarını girdi olarak kabul edebilmelidir. Girdi modeli tek videodan koleksiyonlara kadar ölçeklenmelidir:

* Tek video URL'si işleme
* Birden fazla video URL'sini birlikte işleme
* Playlist URL'si işleme
* Playlist içindeki tüm videoları işleme
* Playlist içindeki belirli videoları seçerek işleme
* Hatalı, silinmiş veya private videoları atlayarak işleme devam etme (graceful degradation)

Playlist ve koleksiyon yapısı yalnızca bir indirme kolaylığı değil, korunması gereken bir **bağlamsal ilişki** olarak ele alınmalıdır (bkz. [İlişkisel Bütünlük](#i̇lişkisel-bütünlük-gereksinimleri)). Playlist'in temsil ettiği gruplama (örneğin bir modül, bir konu, bir seri) artifact'lerde kayıt altına alınmalıdır.

# Üretilecek Artifact Türleri (Phase 1)

Sistem her video için mümkün olduğunca zengin ve yapılandırılmış veri üretmelidir. Artifact türleri genişletilebilir olmalıdır; aşağıdakiler Phase 1'in başlangıç kümesidir, nihai liste değildir.

## Metadata Artifact'i

Her video için en az şu alanlar toplanmalıdır:

* Video ID
* Video URL
* Video başlığı
* Playlist / koleksiyon bilgisi
* Kanal bilgisi
* Video açıklaması
* Yayın tarihi
* Süre
* Varsa chapter bilgileri
* Varsa etiketler
* Varsa diğer anlamlı metadata alanları

Metadata mümkün olduğunca eksiksiz tutulmalı; ileride yeni alanlar eklendiğinde şema bunu destekleyebilmelidir.

## Transcript Artifact'i

Transcript, sistemin en kritik çıktılarından biridir ve şu gereksinimleri karşılamalıdır:

* Tam metin içermeli
* Zaman damgalarını korumalı
* Mümkün olduğunca yüksek doğrulukta olmalı
* Otomatik oluşturulmuş altyazıları desteklemeli
* Bir videoda birden fazla dil varsa bunlar ayırt edilebilmeli
* Transcript dili kayıt altına alınmalı
* Transcript türü (manuel veya otomatik) kayıt altına alınmalı
* Daha sonra işlenebilir, segment bazlı (zaman damgalı) bir veri yapısında tutulmalı

Transcript yalnızca düz metin olarak değil, downstream görevlerin kullanabileceği segment/zaman yapısı korunarak saklanmalıdır.

## Genişletilebilir Artifact Türleri

Sistem, ileride yeni artifact türlerinin eklenmesine açık olmalıdır. Mimari, bu türlerin ortak bir artifact modeli ve ilişkilendirme şeması altında eklenebilmesine olanak tanımalıdır.

Phase 1'de metadata ve transcript dışındaki artifact türleri (görsel/screenshot artifact'leri, OCR, konuşmacı/konu bölütlemeleri, çıkarılmış varlıklar vb.) **uygulanmaz**; bunlar [`03_ROADMAP.md`](03_ROADMAP.md) içinde tanımlanır. Buradaki gereksinim, bu türler eklendiğinde mevcut artifact modelinin onları barındırabilecek şekilde tasarlanmış olmasıdır.

# LLM Entegrasyonu (Phase 1)

Üretilen artifact'lerin ilk tüketicisi **OpenAI API** olacaktır. Bu entegrasyon, sistemi tek bir analiz türüne bağlamadan, artifact'leri konfigüre edilebilir bir şekilde bir LLM'e gönderip cevapları saklayabilmelidir.

Desteklenmesi gereken yetenekler:

* OpenAI API ile LLM çağrısı yapabilmek.
* Aşağıdaki API/runtime parametrelerini konfigüre edilebilir tutmak: model adı, temperature, max output / max completion token, response format, timeout, retry davranışı, batch / concurrency limiti ve ileride gerekebilecek diğer parametreler.
* API key gibi gizli bilgileri **koda gömmemek**; bunları güvenli ve dışarıdan yönetilebilir şekilde (env variable, `.env` dosyası vb.) ele almak.
* Promptları harici dosyalardan okuyabilmek.
* Prompt dosyalarını farklı analiz görevleri için değiştirilebilir hale getirmek (requirement extraction, product analysis vb. prompt seviyesinde değişebilmeli; sistem belirli bir analiz türüne bağlı olmamalı).
* Transcript ve metadata'yı bu promptlarla birlikte modele gönderebilmek.
* Tek video veya çoklu video işleyebilmek.
* Uzun transcriptlerde chunking, batching veya video bazlı işleme ihtiyacını değerlendirmek.
* Model cevaplarını alıp yapılandırılmış biçimde saklayabilmek.
* Cevapların parse edilebilirliğini önemsemek; gerekirse çıktı şeması / structured output yaklaşımını spec içinde tartışmak.

# Çıktı Formatı ve Saklama (Phase 1)

Üretilen artifact'ler ve LLM cevapları, daha sonra LLM'lere gönderilebilecek şekilde yapılandırılmış olarak saklanmalıdır.

Çıktı formatı henüz kesinleşmemiştir (JSON, Markdown, tek dosya / çoklu dosya vb.). Bu nedenle:

* Mimari, çıktı formatı kararının sonradan değişebilmesine izin verecek şekilde tasarlanmalıdır.
* Saklama biçimi, hangi artifact'in hangi videoya ve hangi koleksiyona ait olduğunu kaybetmemelidir (bkz. [İlişkisel Bütünlük](#i̇lişkisel-bütünlük-gereksinimleri)).

# İlişkisel Bütünlük Gereksinimleri

Amaç yalnızca veri indirmek değildir; amaç, downstream LLM görevleri tarafından güvenilir biçimde kullanılabilecek, ilişkileri korunmuş yüksek kaliteli bir artifact kümesi üretmektir.

Bu nedenle:

* Metadata eksiksiz tutulmalı
* Her artifact, ait olduğu video ile açıkça ilişkilendirilmeli
* Transcript ile metadata ilişkilendirilmeli
* Hangi transcript'in hangi videoya ait olduğu net olmalı
* Playlist / koleksiyon, gruplama ve video arasındaki ilişkiler korunmalı
* Veri kaybı minimumda tutulmalı

İleride eklenecek artifact türleri (örneğin görsel artifact'ler) için ek ilişkilendirme gereksinimleri [`03_ROADMAP.md`](03_ROADMAP.md) içinde tanımlanır.

# Phase 1 Dışındakiler

Aşağıdaki özellikler ileride geliştirilebilir ancak ilk iterasyonun teslim hedefi **değildir**. Tanımları ve gerekçeleri [`03_ROADMAP.md`](03_ROADMAP.md) içinde tutulur:

* Screenshot extraction
* Zaman damgalı görsel artifact üretimi
* OCR
* Görsel analiz
* Multimodal pipeline
* Video frame intelligence
* Diğer gelişmiş / türetilmiş artifact türleri

# Bu Aşamada Beklenen Yaklaşım

Bu aşamada kesin bir teknik çözüm dayatılmamalıdır. Önce:

* Phase 1 ihtiyacının (metadata + transcript toplama + LLM entegrasyonu) doğru biçimde analiz edilmesini,
* Üretim ile tüketim katmanı ayrımının netleştirilmesini,
* Olası yaklaşımların avantaj ve dezavantajlarının tartışılmasını,
* Ardından genişletilebilir ve uygulanabilir bir spec tasarlanmasını

istiyorum. Tasarım, Phase 1 ihtiyaçlarını (metadata, transcript, zaman ilişkileri, playlist desteği, veri kalitesi, artifact ilişkileri, LLM entegrasyonu, çıktı saklama) eksiksiz karşılarken, [`03_ROADMAP.md`](03_ROADMAP.md) içinde tanımlanan gelecekteki artifact türlerine ve kullanım senaryolarına da kapı açık bırakmalıdır.
