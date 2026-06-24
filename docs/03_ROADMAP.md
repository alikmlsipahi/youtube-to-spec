# Amaç

Bu doküman, projenin **uzun vadeli vizyonunu** ve ilk development phase (Phase 1) kapsamı dışında bırakılan artifact türlerini ve kullanım senaryolarını tutar.

Buradaki özellikler değerlidir ve mimari onları engellemeyecek şekilde tasarlanmalıdır; ancak **ilk iterasyonun teslim hedefi değildir**. Phase 1 kapsamı ve temel tasarım ilkeleri için bağlam dokümanına bakınız: [`02_PRODUCT_BRIEF.md`](02_PRODUCT_BRIEF.md).

Temel ilke ([`02_PRODUCT_BRIEF.md`](02_PRODUCT_BRIEF.md) ile aynı) korunur: sistem, video kaynaklarından yüksek kaliteli, yapılandırılmış, LLM dostu artifact'ler üretir; bu artifact'ler üzerinde çalışan analizler ise ayrı bir tüketim katmanıdır. Aşağıdaki maddeler, **üretim katmanına eklenebilecek yeni artifact türlerini** ve bunların açtığı tüketim olanaklarını tanımlar.

# Görsel (Screenshot) Artifact'i

Yalnızca metinsel transcript bazı durumlarda yetersiz kalır. Birçok video içeriğinde bilgi görsel arayüz, ekran akışı, form alanları, seçenekler, uyarılar, tablo yapıları, veri ilişkileri veya işlem sonuçları üzerinden aktarılır.

Bu nedenle transcript'e ek olarak, videodan belirli zamanlarda alınmış ekran görüntüleri de artifact olarak üretilebilir. Amaç, tüketim katmanına yalnızca metinsel değil, gerektiğinde **zaman damgasıyla ilişkilendirilmiş görsel bağlam** da sağlayabilmektir.

## Görsel Artifact'lerin Sağladığı Değer

Görsel artifact'ler, downstream LLM görevlerinde şu tür ihtiyaçları karşılamak için kullanılabilir:

* Transcript'te geçen bir işlemin ekrandaki karşılığını görmek
* Form alanlarını, seçenekleri ve veri giriş noktalarını anlamak
* Bir akıştaki adımları görsel olarak takip etmek
* Transcript'te yanlış yazılmış veya eksik anlaşılmış ifadeleri görsel bağlamla doğrulamak
* Bir öğenin hangi veri nesneleriyle ilişkili olduğunu daha iyi anlamak
* Video içinde anlatılan işlemin sonucunu veya sistem tepkisini tespit etmek

Bu, görsel artifact'lerin nasıl kullanılabileceğine dair örneklerdir; üretim katmanı bu kullanımı dayatmaz, yalnızca mümkün kılar.

## Zaman Seçimi Problemi

Ekran görüntüsünün hangi saniyelerden alınacağı manuel olarak belirlenemez. Bu nedenle sistem, screenshot alınacak zamanları otomatik belirleyebilmelidir.

Otomatik zaman seçimi için değerlendirilebilecek stratejiler (tek bir çözüm dayatılmaz, birden fazlası kombine edilebilir):

* Transcript segmentlerinin zaman damgalarını kullanmak
* Konuşma yoğunluğu yüksek segmentlerden örnek görüntü almak
* Belirli aralıklarla düzenli screenshot almak
* Ekranda anlamlı görsel değişiklik olduğunda screenshot almak
* Transcript'te aksiyon bildiren ifadeler (kayıt, silme, ekleme, seçme, kaydetme, güncelleme, listeleme vb.) geçtiğinde ilgili zaman aralığından screenshot almak
* Video içinde sahne / ekran değişimi tespit edildiğinde screenshot almak
* Çok sık tekrar eden veya aynı ekrana ait görüntüleri elemek
* Her transcript chunk'ı için bir veya birkaç temsilî görüntü seçmek

Seçim stratejisi, üretilen her görsel artifact ile birlikte kayıt altına alınmalıdır; böylece downstream tarafında görüntünün hangi mantıkla seçildiği bilinir.

## Görsel Artifact İlişkilendirme

Görsel artifact'ler transcript ve metadata'dan kopuk olmamalıdır. Her screenshot en az şu bilgilerle ilişkilendirilmelidir:

* Video ID
* Video başlığı
* Playlist / koleksiyon (gruplama) bilgisi
* Screenshot timestamp'i
* İlgili transcript segmenti veya chunk'ı
* Screenshot dosya yolu
* Görüntünün hangi seçim stratejisiyle alındığı
* Mümkünse ilgili konuşma metni

Bu ilişkilendirme gereksinimleri, [`02_PRODUCT_BRIEF.md`](02_PRODUCT_BRIEF.md) içindeki genel İlişkisel Bütünlük gereksinimlerinin görsel artifact'lere uzantısıdır.

# Diğer Gelecek Artifact Türleri

Üretim katmanına ileride eklenebilecek diğer türetilmiş artifact türleri:

* Segment / chunk bazlı yapılandırılmış birimler
* Çıkarılmış anahtar kelimeler veya varlıklar (entity extraction)
* Görüntülerden çıkarılmış metin (OCR)
* Konuşmacı / konu bölütlemeleri (speaker / topic segmentation)
* Görsel analiz ve video frame intelligence ile elde edilen üst düzey sinyaller
* Henüz düşünülmemiş diğer türetilmiş veriler

Mimari, bu türlerin ortak bir artifact modeli ve ilişkilendirme şeması altında eklenebilmesine olanak tanımalıdır.

# Uzun Vadeli Kullanım Senaryosu Genişlemesi

Görsel ve diğer multimodal artifact'ler eklendiğinde nihai hedef genişler:

Her video için yalnızca **transcript + metadata** değil; **transcript + metadata + zaman damgalı görsel bağlam** ve gelecekte eklenebilecek diğer türetilmiş verileri içeren, ilişkileri korunmuş zengin bir artifact paketi üretmek.

Bu paket, herhangi bir tekil analize bağımlı olmadan, çok çeşitli LLM görevleri için ortak ve yeniden kullanılabilir bir girdi tabanı oluşturur. Multimodal bağlam sayesinde, yalnızca metne dayalı analizlere göre daha doğru functional requirement, iş kuralı, feature davranışı ve ürün spesifikasyonu çıkarımı gibi tüketim senaryoları mümkün hale gelir. Belirli bir analiz (örneğin functional requirement veya iş kuralı çıkarımı) bu paketin yalnızca olası bir tüketicisidir.
