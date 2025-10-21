"""
hybrid_search.py
Semantic + Keyword + Component search with proper tokenization
"""

import json
import numpy as np
import re
import warnings
import os
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from pathlib import Path
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from typing import List, Tuple, Optional
import logging
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


def tokenize(text):
    """Proper tokenization - remove punctuation"""
    if not text:
        return []
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    return [t for t in text.split() if t and len(t) > 1]


class HybridSearch:
    """Hybrid search with fixed tokenization"""
    
    COMPONENT_KEYWORDS = {
        'multiplexer': {'match': 'Multiplexer', 'opposite': 'Demultiplexer'},
        'mux': {'match': 'Multiplexer', 'opposite': 'Demultiplexer'},
        'demultiplexer': {'match': 'Demultiplexer', 'opposite': 'Multiplexer'},
        'demux': {'match': 'Demultiplexer', 'opposite': 'Multiplexer'},
        'flip flop': {'match': ['DflipFlop', 'JKflipFlop', 'SRflipFlop', 'TflipFlop']},
        'latch': {'match': ['DflipFlop', 'SRflipFlop']},
        'memory element': {'match': ['DflipFlop', 'JKflipFlop', 'SRflipFlop', 'TflipFlop', 'Ram', 'EEPROM']},
        'adder': {'match': ['FullAdder', 'HalfAdder']},
        'display': {'match': ['SevenSegDisplay', 'HexDisplay', 'DigitalLed']},
        'seven segment': {'match': 'SevenSegDisplay'},
        'counter': {'match': 'Counter'},
        'decoder': {'match': 'Decoder'},
    }
    
    def __init__(self, circuits_file, embeddings_file,
                 model_name='sentence-transformers/all-MiniLM-L12-v2'):

        # Load model
        self.model = SentenceTransformer(model_name)
        
        # Load circuits
        with open(circuits_file, 'r', encoding='utf-8') as f:
            self.circuits = json.load(f)
        
        # Load embeddings
        self.embeddings = np.load(embeddings_file)
        
        print(f"Loaded {len(self.circuits):,} circuits")
        
        # Get enriched texts and filter empty circuits
        self.enriched_texts = []
        self.valid_indices = []
        
        for i, c in enumerate(self.circuits):
            text = c.get('embedding_text', '')
            # Skip truly empty circuits
            if text and text != 'Empty circuit' and len(text) > 10:
                self.enriched_texts.append(text)
                self.valid_indices.append(i)
        
        print(f"Valid circuits for search: {len(self.valid_indices):,}")
        
        # Build BM25 index with proper tokenization
        print("Building BM25 index with proper tokenization...")
        tokenized_corpus = [tokenize(text) for text in self.enriched_texts]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        print("Hybrid search ready\n")
    
    def _detect_component_intent(self, query: str) -> Optional[dict]:
        query_lower = query.lower()
        for keyword, component_info in self.COMPONENT_KEYWORDS.items():
            if keyword in query_lower:
                return component_info
        return None
    
    def _calculate_component_score(self, circuit: dict, component_intent: Optional[dict]) -> float:
        if component_intent is None:
            return 0.5
        
        breakdown = circuit.get('component_breakdown', {})
        
        match_components = component_intent.get('match')
        if isinstance(match_components, str):
            match_components = [match_components]
        
        if match_components:
            for comp in match_components:
                if comp in breakdown:
                    return 1.0
        
        opposite = component_intent.get('opposite')
        if opposite and opposite in breakdown:
            return 0.0
        
        return 0.5
    
    def search(self, query: str, top_k: int = 20) -> List[Tuple[int, dict, dict]]:

        # 1. Semantic search on ALL circuits
        query_embedding = self.model.encode(query, normalize_embeddings=True, show_progress_bar=False)
        semantic_scores_full = np.dot(self.embeddings, query_embedding)
        
        # 2. Keyword search on valid circuits only
        tokenized_query = tokenize(query)
        if tokenized_query:
            keyword_scores_valid = self.bm25.get_scores(tokenized_query)
            # Normalize
            if keyword_scores_valid.max() > 0:
                keyword_scores_valid = keyword_scores_valid / keyword_scores_valid.max()
        else:
            keyword_scores_valid = np.zeros(len(self.valid_indices))
        
        # 3. Map keyword scores back to full circuit list
        keyword_scores_full = np.zeros(len(self.circuits))
        for i, valid_idx in enumerate(self.valid_indices):
            keyword_scores_full[valid_idx] = keyword_scores_valid[i]
        
        # 4. Component scores
        component_intent = self._detect_component_intent(query)
        component_scores = np.array([
            self._calculate_component_score(c, component_intent)
            for c in self.circuits
        ])
        
        # 5. Fusion (weights: 0.45 semantic, 0.45 keyword, 0.1 component)
        final_scores = (
            0.45 * semantic_scores_full +
            0.45 * keyword_scores_full +
            0.1 * component_scores
        )
        
        # 6. Get top-k
        top_indices = np.argsort(final_scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score_breakdown = {
                'final': float(final_scores[idx]),
                'semantic': float(semantic_scores_full[idx]),
                'keyword': float(keyword_scores_full[idx]),
                'component': float(component_scores[idx])
            }
            results.append((int(idx), score_breakdown, self.circuits[idx]))
        
        return results


# Import test queries
from baseline_search import TEST_QUERIES


if __name__ == "__main__":
    CIRCUITS_FILE = "embeddings/circuits_enriched_1000_20251021_220507.json"
    EMBEDDINGS_FILE = "embeddings/embeddings_1000_20251021_220507.npy"
    
    print("="*70)
    print("HYBRID SEARCH - FIXED VERSION")
    print("="*70)
    
    search = HybridSearch(CIRCUITS_FILE, EMBEDDINGS_FILE)
    
    for test in TEST_QUERIES:
        query = test['query']
        category = test['category']
        
        print(f"\n{'='*70}")
        print(f"Query: '{query}' [{category}]")
        print(f"{'='*70}")
        
        results = search.search(query, top_k=5)
        
        if not results:
            print("No results found")
            continue
        
        for i, (idx, scores, circuit) in enumerate(results, 1):
            print(f"\n{i}. [{scores['final']:.3f}] {circuit['name']}")
            print(f"   S={scores['semantic']:.2f} K={scores['keyword']:.2f} C={scores['component']:.1f}")
            comp_count = circuit.get('component_count', 0)
            print(f"   Components: {comp_count}")
    
    print(f"\n{'='*70}\n")