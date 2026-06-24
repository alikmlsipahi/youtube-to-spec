# Proje Amacı

Amacım, bir yazılım ürününün kamuya açık kullanım rehberi videolarından ürün bilgisini otomatik olarak çıkartabilen bir veri toplama ve bilgi çıkarım aracı geliştirmektir.

İncelenen ürün modüler bir yapıya sahiptir. Her modül için ayrı YouTube playlistleri bulunmaktadır. Her playlist ilgili modülün kullanım rehberlerini içeren videolardan oluşmaktadır. Her video genellikle bir veya birkaç feature'ın nasıl kullanıldığını anlatmaktadır.

Nihai hedefim, bu kullanım rehberi videolarını sistematik şekilde işleyerek ürünün iş kurallarını, davranışlarını, yeteneklerini ve gereksinimlerini çıkartabilecek yüksek kaliteli bir veri seti oluşturmaktır.

# Toplanmak İstenen Veriler

Her video için mümkün olduğunca zengin ve yapılandırılmış veri elde etmek istiyorum.

Her video için:

* Video ID
* Video URL
* Video başlığı
* Playlist bilgisi
* Kanal bilgisi
* Video açıklaması
* Yayın tarihi
* Süre
* Varsa chapter bilgileri
* Varsa etiketler
* Varsa diğer anlamlı metadata alanları
* Transcript / caption içeriği
* Transcript zaman damgaları
* Transcript dili
* Transcript türü (manuel veya otomatik)

toplanmalıdır.

# Transcript Gereksinimleri

Transcript projenin en önemli çıktılarından biridir.

İstediğim transcript:

* Tam metin olmalı
* Zaman damgalarını korumalı
* Mümkün olduğunca yüksek doğrulukta olmalı
* Otomatik oluşturulmuş altyazılar desteklenmeli
* Bir videoda birden fazla dil varsa bunlar ayırt edilebilmeli
* Transcript daha sonra işlenebilir bir veri yapısında tutulmalı

# Playlist Gereksinimleri

Araç yalnızca tek video ile sınırlı olmamalıdır.

Aşağıdaki kullanım senaryoları desteklenmelidir:

* Tek video URL'si işleme
* Birden fazla video URL'si işleme
* Playlist URL'si işleme
* Playlist içindeki tüm videoları işleme
* Playlist içindeki belirli videoları seçerek işleme
* Hatalı, silinmiş veya private videoları atlayarak devam etme

# Veri Kalitesi Gereksinimleri

Amaç yalnızca transcript indirmek değildir.

Amaç daha sonra LLM'ler tarafından analiz edilebilecek yüksek kaliteli bir bilgi tabanı oluşturmaktır.

Bu nedenle:

* Metadata eksiksiz tutulmalı
* Transcript ile metadata ilişkilendirilmeli
* Hangi transcriptin hangi videoya ait olduğu açık olmalı
* Playlist, modül ve video ilişkileri korunmalı
* Veri kaybı minimum olmalı

# Nihai Kullanım Senaryosu

Toplanan video metadata'ları ve transcriptler daha sonra aşağıdaki amaçlar için kullanılacaktır:

* Ürünün feature'larını anlamak
* Ürünün iş kurallarını çıkarmak
* Ürünün davranışlarını çıkarmak
* Requirement extraction
* Functional requirement üretimi
* Software specification oluşturma
* Modül-feature ilişkilerini çıkarmak
* Bir ürün bilgi tabanı oluşturmak
* LLM destekli analizler yapmak

Bu nedenle sistem yalnızca transcript indiren bir araç değil, kullanım rehberi videolarından ürün bilgisini çıkarmaya yönelik bir veri toplama ve hazırlama pipeline'ının ilk aşaması olarak düşünülmelidir.


# Ek İstek: Transcript ile Birlikte Video Görsel Kanıtlarının Toplanması

Transcriptler daha sonra LLM'e verilerek yazılım gereksinimleri, iş kuralları, feature davranışları ve ürün akışları çıkarılacaktır.

Ancak yalnızca transcript kullanmak bazı durumlarda yetersiz kalabilir. Kullanım rehberi videolarında anlatılan birçok bilgi görsel arayüz, ekran akışı, form alanları, seçenekler, uyarılar, tablo yapıları, veri ilişkileri veya işlem sonuçları üzerinden anlaşılmaktadır.

Bu nedenle transcriptlere ek olarak videodan belirli zamanlarda alınmış ekran görüntülerinin de kaydedilmesini istiyorum.

Amaç, LLM'e yalnızca metinsel transcript değil, gerektiğinde transcript ile ilişkili görsel bağlam da sağlayabilmektir.

# Görsel Veri Toplama Amacı

Ekran görüntüleri şu amaçlarla kullanılacaktır:

* Transcriptte geçen işlemin ekrandaki karşılığını görmek
* Form alanlarını, seçenekleri ve veri giriş noktalarını anlamak
* İş akışındaki adımları görsel olarak takip etmek
* Transcriptte yanlış yazılmış veya eksik anlaşılmış ifadeleri görsel bağlamla düzeltmek
* UI detaylarını birebir requirement olarak yazmak için değil, sistem davranışını ve iş kuralını daha doğru anlamak için kullanmak
* Feature'ın hangi veri nesneleriyle ilişkili olduğunu daha iyi anlamak
* Video içinde anlatılan işlem sonucunu veya sistem tepkisini tespit etmek

# Zaman Damgası Problemi

Manuel olarak her video için hangi saniyelerden ekran görüntüsü alınacağını belirleyemem.

Bu nedenle sistemin ekran görüntüsü alınacak zamanları otomatik belirlemesini istiyorum.

Bu otomatik seçim için şu yaklaşımlar değerlendirilebilir:

* Transcript segmentlerinin zaman damgalarını kullanmak
* Konuşma yoğunluğu olan segmentlerden örnek görüntüler almak
* Belirli aralıklarla düzenli screenshot almak
* Ekranda anlamlı değişiklik olduğunda screenshot almak
* Transcriptte işlem, kayıt, silme, ekleme, seçme, kaydetme, güncelleme, listeleme gibi aksiyon bildiren ifadeler geçtiğinde o zaman aralığından screenshot almak
* Video içinde sahne/ekran değişimi tespit edildiğinde screenshot almak
* Çok sık tekrar eden veya aynı ekrana ait görüntüleri elemek
* Her transcript chunk'ı için bir veya birkaç temsilî ekran görüntüsü seçmek

# İstenen Çıktı İlişkisi

Ekran görüntüleri transcriptten kopuk olmamalıdır.

Her screenshot şu bilgilerle ilişkilendirilmelidir:

* Video ID
* Video başlığı
* Playlist/modül bilgisi
* Screenshot timestamp'i
* İlgili transcript segmenti veya transcript chunk'ı
* Screenshot dosya yolu
* Screenshot'ın hangi seçim stratejisiyle alındığı
* Mümkünse ilgili konuşma metni

# Nihai Hedef

Nihai hedef, her video için yalnızca düz transcript değil, transcript + metadata + zaman damgalı görsel bağlam içeren daha zengin bir analiz paketi oluşturmaktır.

Bu paket daha sonra LLM'e verilerek daha doğru functional requirement, iş kuralı, feature davranışı ve ürün spesifikasyonu çıkarımı yapılacaktır.

Bu aşamada kesin teknik çözüm dayatılmamalıdır. Önce bu ihtiyacın doğru şekilde analiz edilmesini, avantaj/dezavantajlarının tartışılmasını ve sonrasında uygulanabilir bir spec tasarlanmasını istiyorum.
