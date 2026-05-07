# Hukuk Chatbot

Hukuk Chatbot, Retrieval-Augmented Generation (RAG) mimarisi kullanılarak Türk Hukuku (örneğin İş Kanunu vb.) hakkında soruları yanıtlamak üzere tasarlanmış, hafif ve bağımsız bir yapay zeka asistanıdır.

Proje, hızlı yanıtlar verebilmek için FastAPI tabanlı bir backend ve kullanıcı dostu bir Next.js frontend içermektedir.

---

## 🏗️ Mimari Özeti

Sistem iki ana bileşenden oluşmaktadır:
1. **Backend** (`/backend`): Vektör veri tabanında (ChromaDB) saklanan hukuki metinleri arayan ve OpenAI modelleri ile anlamlı cevaplar üreterek sonuçları frontend'e anlık olarak (streaming) gönderen Python/FastAPI sunucusu.
2. **Frontend** (`/frontend`): React tabanlı Next.js 14 (App Router) uygulaması. Kullanıcı arayüzünü (UI) sunar, Tailwind CSS ile şekillendirilmiştir ve gerçek zamanlı cevap akışı (SSE - Server-Sent Events) kullanır.

---

## ⚙️ Kurulum ve Ayarlar (Backend)

Backend'in çalışması için Python 3.10+ gereklidir ve soruları yanıtlamak için OpenAI modeli kullanılır.

### 1. Gereksinimlerin Yüklenmesi
Terminalden `backend` dizinine gidin ve gerekli paketleri yükleyin:
```bash
cd backend
python -m venv venv
# Windows için:
venv\Scripts\activate
# Mac/Linux için:
# source venv/bin/activate
pip install -r requirements.txt
```
  
### 2. Çevresel Değişkenler (.env)
`backend/` dizini içinde bir `.env` dosyası oluşturun. Şablon olarak `.env.example` dosyasını kullanabilirsiniz:
```env
OPENAI_API_KEY=sizin_openai_api_anahtariniz
OPENAI_MODEL=gpt-4o-mini
SIMILARITY_THRESHOLD=0.75
```

### 3. Sunucuyu Başlatma
FastAPI uygulamasını `uvicorn` ile başlatın:
```bash
python -m uvicorn app.main:app --reload --port 8000
```
API, `http://localhost:8000` adresinde çalışmaya başlayacaktır.

---

## 💻 Kurulum ve Ayarlar (Frontend)

Frontend, kullanıcıların chatbot ile yazıştığı modern bir arayüz sağlar.

### 1. Gereksinimlerin Yüklenmesi
Terminalden `frontend` dizinine gidin:
```bash
cd frontend
npm install
```

### 2. Ortam Değişkenleri (API Proxy)
Next.js ayarları (`next.config.mjs`) gelen `/api/` isteklerini otomatik olarak `http://localhost:8000/` adresine yönlendirecek şekilde ayarlanmıştır.

### 3. Uygulamayı Başlatma
Geliştirme sunucusunu başlatın:
```bash
npm run dev
```
Web tarayıcınızda `http://localhost:3000` adresini açarak uygulamayı kullanmaya başlayabilirsiniz.
