import logging
from collections.abc import AsyncGenerator

from langchain_openai import ChatOpenAI

from app.config import settings
from app.schemas import SourceItem
from app.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class RagEngine:
    SYSTEM_PROMPT = (
        'Sen empatik ve uzman bir Türk Hukuku asistanısın (bir nevi hukuki yaşam koçu).\n'
        'Kurallar:\n'
        '1) Sadece verilen bağlamı (kanun maddelerini) kullanarak hukuki tavsiye veya kesin cevap ver. Bağlamda olmayan kanun/madde/karar uydurma.\n'
        '2) Eğer bağlam yetersizse veya kullanıcının sorusu çok kısa/belirsizse (örneğin "boşanmak istiyorum", "işten kovuldum"), hemen "veri bulunamadı" demek yerine, önce empatik ve iyimser bir yaklaşım sergile (örneğin "Yaşadığınız bu zor durum için üzgünüm, ancak hukuki haklarınız var..."). Sonra kullanıcıyı yönlendirmek için durumu detaylandırmasını iste ve ona örnek senaryolar sun (örneğin "Anlaşmalı boşanma mı düşünüyorsunuz yoksa çekişmeli mi?", "Ne kadar süredir orada çalışıyordunuz?").\n'
        '3) Eğer kullanıcı hava durumu, yemek tarifi, teknoloji veya genel sohbet gibi HUKUK DIŞI bir konu sorarsa, kibarca hukuki asistan olduğunu belirterek cevap vermeyi reddet.\n'
        '4) Kanun maddelerini katı ve kelimesi kelimesine kopyalamak yerine, tüm fıkraları kapsayacak şekilde açıklayıcı ve anlaşılır bir dille ifade et.\n'
        '5) Kesin hukuki bir cevap verdiğinde, cevabın en sonuna kullandığın bağlamdaki kanun adını ve madde numarasını doğal bir şekilde "Kaynaklar:" başlığı altında ekle.\n'
        '6) Kullanıcıya hukuki bir tavsiye veya çözüm yolu sunduğunda, cevabının sonuna mutlaka adım adım uygulanabilecek bir "Strateji ve Eylem Planı" ekle. Bu planı okuması kolay bir akış diyagramı veya adım adım (Aksiyon 1, Aksiyon 2 vb.) mantıksal bir sırayla sun.'
    )

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError('OPENAI_API_KEY is missing. Set it in your .env file.')

        self.vector_store = get_vector_store()
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )

    def _retrieve(self, query: str) -> tuple[list, list[SourceItem], float]:
        results = self.vector_store.similarity_search_with_relevance_scores(query, k=settings.TOP_K)

        filtered_docs = []
        sources: list[SourceItem] = []
        seen: set[tuple[str, int]] = set()
        best_score = 0.0

        for doc, score in results:
            numeric_score = float(score)
            best_score = max(best_score, numeric_score)
            if numeric_score < settings.SIMILARITY_THRESHOLD:
                continue

            filtered_docs.append(doc)
            filename = str(doc.metadata.get('source') or doc.metadata.get('filename', 'unknown'))
            page = int(doc.metadata.get('page') or doc.metadata.get('page_number', 0))
            key = (filename, page)

            if key in seen:
                continue
            sources.append(SourceItem(filename=filename, page=page))
            seen.add(key)

        return filtered_docs, sources, best_score

    @staticmethod
    def _build_user_prompt(query: str, context: str) -> str:
        return f'Baglam:\n{context}\n\nSoru: {query}'

    def build_final_answer(self, answer_text: str, sources: list[SourceItem]) -> tuple[str, list[SourceItem]]:
        text = (answer_text or '').strip()
        if not text:
            return settings.NO_CONTEXT_MESSAGE, []
        return text, sources

    def prepare_messages(self, query: str) -> tuple[list[tuple[str, str]] | None, list[SourceItem]]:
        prefixed_query = f"query: {query}"
        docs, sources, best_score = self._retrieve(prefixed_query)
        if not docs or best_score < settings.SIMILARITY_THRESHOLD:
            logger.info(
                'Low context confidence for query (best_score=%.4f, threshold=%.2f). Passing empty context to LLM for conversational guidance.',
                best_score,
                settings.SIMILARITY_THRESHOLD,
            )
            context = 'Hukuki bağlam bulunamadı.'
        else:
            context = '\n\n'.join(doc.page_content for doc in docs)
        user_prompt = self._build_user_prompt(query=query, context=context)
        messages: list[tuple[str, str]] = [
            ('system', self.SYSTEM_PROMPT),
            ('human', user_prompt),
        ]
        return messages, sources

    def answer(self, query: str) -> tuple[str, list[SourceItem]]:
        messages, sources = self.prepare_messages(query)
        if messages is None:
            return settings.NO_CONTEXT_MESSAGE, []

        response = self.llm.invoke(messages)
        return self.build_final_answer(response.content or '', sources)

    async def stream_tokens(self, messages: list[tuple[str, str]]) -> AsyncGenerator[str, None]:
        async for chunk in self.llm.astream(messages):
            text = chunk.content or ''
            if text:
                yield text
