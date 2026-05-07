import json
import logging
import re
from pathlib import Path
from langchain_core.documents import Document

from app.config import settings

logger = logging.getLogger(__name__)

def list_json_paths(data_dir: str | None = None) -> list[Path]:
    target_dir = Path(data_dir or settings.DATA_DIR)
    if not target_dir.exists():
        logger.warning(f'Data directory not found: {target_dir}')
        return []

    json_paths = sorted(target_dir.rglob('*.json'))
    if not json_paths:
        logger.warning('No JSON files found in %s', target_dir)
        return []

    return json_paths

def extract_entities(text: str) -> list[str]:
    entities = set()
    # Matches "Madde 12", "Madde 12/A", etc.
    madde_matches = re.findall(r'(?i)\bMadde\s+\d+[a-zA-Z]*\b', text)
    entities.update(match.strip() for match in madde_matches)
    
    # Matches "... Kanunu" or "XX sayılı ... Kanunu"
    kanun_matches = re.findall(r'(?i)\b(?:\d+\s+sayılı\s+)?(?:[A-ZÇĞİÖŞÜa-zçğıöşü]+\s+)*Kanun(?:u|una|unda|undan|un)?\b', text)
    # Basic cleanup for kanun matches to avoid generic trailing suffixes
    entities.update(match.strip() for match in kanun_matches if len(match) > 6)
    
    return sorted(list(entities))

def extract_json_documents(json_path: Path) -> list[Document]:
    documents: list[Document] = []
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        isim = data.get('isim', json_path.stem)
        maddeler = data.get('maddeler', [])
        
        for item in maddeler:
            madde_no = item.get('madde_no', 'Bilinmiyor')
            icerik = item.get('icerik', '').strip()
            
            if not icerik:
                continue
                
            entities = extract_entities(icerik)
            
            # Append entity context to the content so LLM sees it directly
            enriched_content = f"[Kanun: {isim}] [Madde: {madde_no}]\n\n{icerik}"
            if entities:
                enriched_content += f"\n\n[İlişkili Referanslar: {', '.join(entities)}]"

            metadata = {
                'source': json_path.name,
                'isim': isim,
                'madde_no': str(madde_no),
                'linked_entities': ", ".join(entities) if entities else ""
            }
            
            documents.append(
                Document(
                    page_content=enriched_content,
                    metadata=metadata,
                )
            )
            
    except Exception as exc:
        logger.exception('Failed to read JSON %s: %s', json_path.name, exc)

    logger.info('Parsed %s: %s madde (chunks) created', json_path.name, len(documents))
    return documents

def load_json_documents(data_dir: str | None = None) -> list[Document]:
    json_paths = list_json_paths(data_dir)
    if not json_paths:
        return []

    documents: list[Document] = []
    for json_path in json_paths:
        documents.extend(extract_json_documents(json_path))

    logger.info('Loaded total %s chunks from %s JSON files', len(documents), len(json_paths))
    return documents
