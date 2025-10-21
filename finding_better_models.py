"""
finding_better_models.py - Test technical/QA-focused models
"""

from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cosine
import numpy as np

def quick_test(model_name):
    """test on circuit terminology"""
    print(f"\n{'='*70}")
    print(f"Testing: {model_name}")
    print(f"{'='*70}")
    
    try:
        model = SentenceTransformer(model_name)
        print(f"Loaded. Dimension: {model.get_sentence_embedding_dimension()}")
        
        tests = [
            ('adder circuit', 'full adder implementation', 'flip flop memory'),
            ('flip flop', 'D flip-flop', 'adder circuit'),
            ('multiplexer', '4:1 mux', 'demultiplexer'),
            ('counter', '4-bit counter', 'adder'),
            ('sequential logic', 'circuit with flip-flops and clock', 'combinational logic gates'),
        ]
        
        scores = []
        for query, should_match, should_not_match in tests:
            q_emb = model.encode(query)
            match_emb = model.encode(should_match)
            nomatch_emb = model.encode(should_not_match)
            
            match_sim = 1 - cosine(q_emb, match_emb)
            nomatch_sim = 1 - cosine(q_emb, nomatch_emb)
            separation = match_sim - nomatch_sim
            
            scores.append(separation)
            
            print(f"\nQuery: '{query}'")
            print(f"  ✓ '{should_match}': {match_sim:.3f}")
            print(f"  ✗ '{should_not_match}': {nomatch_sim:.3f}")
            print(f"  Separation: {separation:.3f}")
        
        avg_separation = np.mean(scores)
        print(f"\nAverage separation: {avg_separation:.3f}")
        
        return avg_separation
        
    except Exception as e:
        print(f"Error: {e}")
        return 0


if __name__ == "__main__":
    models = [
        'sentence-transformers/all-mpnet-base-v2',
        'sentence-transformers/multi-qa-mpnet-base-dot-v1',
        'sentence-transformers/gtr-t5-base',
        'sentence-transformers/all-MiniLM-L12-v2',
    ]
    
    results = {}
    
    for model_name in models:
        avg_sep = quick_test(model_name)
        results[model_name] = avg_sep
    
    print(f"\n{'='*70}")
    print("FINAL RANKING")
    print(f"{'='*70}")
    
    sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    for i, (model, score) in enumerate(sorted_results, 1):
        print(f"{i}. {model.split('/')[-1]}: {score:.3f}")