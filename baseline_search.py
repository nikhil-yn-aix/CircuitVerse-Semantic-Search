"""
baseline_search.py
pure keyword search with proper tokenization
"""

import json
import numpy as np
import re
import warnings
warnings.filterwarnings('ignore')

from pathlib import Path
from rank_bm25 import BM25Okapi
from typing import List, Tuple


def tokenize(text):
    """tokenization to remove punctuation"""
    if not text:
        return []
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    
    # split and filter empty tokens
    return [t for t in text.split() if t and len(t) > 1]  # filter 1-char tokens too


class BaselineSearch:
    """pure keyword search using BM25"""
    def __init__(self, circuits_file):
        with open(circuits_file, 'r', encoding='utf-8') as f:
            self.circuits = json.load(f)
        
        print(f"Loaded {len(self.circuits):,} circuits")
    
        self.corpus = self._build_corpus()
        
        # build BM25 index with proper tokenization
        print("Building BM25 index with proper tokenization...")
        tokenized_corpus = [tokenize(doc) for doc in self.corpus]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        print("Baseline search ready\n")
    
    def _clean_html(self, text):
        """remove HTML tags"""
        if not text:
            return ""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = ' '.join(clean.split())
        return clean
    
    def _build_corpus(self):
        """build search corpus: name + description + tags"""
        corpus = []
        
        for circuit in self.circuits:
            parts = []
            
            # name
            if circuit.get('name'):
                parts.append(circuit['name'])
            
            # description
            if circuit.get('description'):
                clean_desc = self._clean_html(circuit['description'])
                if clean_desc:
                    parts.append(clean_desc)
            
            # tags
            if circuit.get('tags'):
                parts.extend(circuit['tags'])
            
            corpus.append(' '.join(parts) if parts else 'untitled')
        
        return corpus
    
    def search(self, query: str, top_k: int = 20) -> List[Tuple[int, float, dict]]:
        """search using BM25"""

        tokenized_query = tokenize(query)
        
        if not tokenized_query:
            return []
        
        # get scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # get top-k
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0:
                results.append((int(idx), score, self.circuits[idx]))
        
        return results


TEST_QUERIES = [
    # exact terms
    {'query': 'flip flop', 'category': 'exact'},
    {'query': 'multiplexer', 'category': 'exact'},
    {'query': 'counter', 'category': 'exact'},
    
    # synonyms
    {'query': 'mux', 'category': 'synonym'},
    {'query': 'latch', 'category': 'synonym'},
    {'query': 'demux', 'category': 'synonym'},
    
    # semantic
    {'query': 'memory element', 'category': 'semantic'},
    {'query': 'data selector', 'category': 'semantic'},
    
    # descriptive
    {'query': 'seven segment display', 'category': 'exact'},
    {'query': 'arithmetic circuit', 'category': 'semantic'},
]


if __name__ == "__main__":
    CIRCUITS_FILE = "circuit_collection_full/circuits_with_scopes_1000_20251021_220343.json"
    
    print("="*70)
    print("BASELINE SEARCH - FIXED VERSION")
    print("="*70)
    
    search = BaselineSearch(CIRCUITS_FILE)
    
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
        
        for i, (idx, score, circuit) in enumerate(results, 1):
            print(f"\n{i}. [{score:.3f}] {circuit['name']}")
            if circuit.get('description'):
                desc = circuit['description'][:60].replace('\n', ' ')
                print(f"   Desc: {desc}...")
            comp_count = circuit.get('component_count', 0)
            print(f"   Components: {comp_count}")
    
    print(f"\n{'='*70}\n")