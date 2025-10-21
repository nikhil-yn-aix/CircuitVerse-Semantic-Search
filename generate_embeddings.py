"""
generate_embeddings.py - Generate semantic embeddings for circuits
Creates enriched text from circuit metadata and generates embeddings
"""

import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import re
from datetime import datetime


class CircuitEmbeddingGenerator:
    """Generate semantic embeddings for CircuitVerse circuits"""
    
    # Components worth explicitly mentioning
    DISTINCTIVE_COMPONENTS = {
        'DflipFlop', 'SRflipFlop', 'JKflipFlop', 'TflipFlop',
        'FullAdder', 'HalfAdder',
        'Multiplexer', 'Demultiplexer',
        'Decoder', 'Encoder',
        'Counter', 'ALU',
        'SevenSegDisplay', 'HexDisplay', 'RGBLed',
        'EEPROM', 'Rom', 'Ram',
        'SubCircuit'
    }
    
    # Sequential circuit indicators
    SEQUENTIAL_COMPONENTS = {'DflipFlop', 'SRflipFlop', 'JKflipFlop', 'TflipFlop', 'Clock'}
    
    # Display components
    DISPLAY_COMPONENTS = {'SevenSegDisplay', 'HexDisplay', 'RGBLed', 'LED', 'DigitalLed'}
    
    # Generic name patterns
    GENERIC_PATTERNS = ['untitled', 'project', 'assignment', 'homework', 'lab',
                       'test', 'demo', 'ex', 'tp', 'experiment']
    
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L12-v2'):
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        dim = self.model.get_sentence_embedding_dimension()
        print(f"Model loaded successfully. Embedding dimension: {dim}")
    
    def _is_generic_name(self, name):
        if not name or len(name) <= 3:
            return True
        name_lower = name.lower()
        return any(pattern in name_lower for pattern in self.GENERIC_PATTERNS)
    
    def _clean_html(self, text):
        if not text:
            return ""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = ' '.join(clean.split())
        return clean
    
    def _is_sequential(self, breakdown):
        return any(comp in breakdown for comp in self.SEQUENTIAL_COMPONENTS)
    
    def _format_component_name(self, comp_type, count):
        if comp_type in ['DflipFlop', 'SRflipFlop', 'JKflipFlop', 'TflipFlop']:
            base = comp_type.replace('flipFlop', ' flip-flop')
            return f"{count} {base}{'s' if count > 1 else ''}"
        elif comp_type == 'SevenSegDisplay':
            return f"{count} 7-segment display{'s' if count > 1 else ''}"
        elif comp_type == 'HexDisplay':
            return f"{count} hex display{'s' if count > 1 else ''}"
        elif comp_type == 'SubCircuit':
            return f"{count} subcircuit module{'s' if count > 1 else ''}"
        elif comp_type in ['FullAdder', 'HalfAdder']:
            return f"{count} {comp_type.lower()}{'s' if count > 1 else ''}"
        else:
            return f"{count} {comp_type.lower()}{'s' if count > 1 else ''}"
    
    def _get_distinctive_components(self, breakdown):
        distinctive = []
        for comp_type in self.DISTINCTIVE_COMPONENTS:
            if comp_type in breakdown:
                count = breakdown[comp_type]
                distinctive.append(self._format_component_name(comp_type, count))
        return distinctive
    
    def create_embedding_text(self, circuit):
        """
        Create enriched semantic text for embedding
        
        Combines: name, description, scope names, circuit type,
        distinctive components, and I/O summary
        """
        parts = []
        
        # 1. Name (only if meaningful)
        name = circuit.get('name', '')
        if name and not self._is_generic_name(name):
            parts.append(name)
        
        # 2. Description (clean and truncate)
        description = circuit.get('description')
        if description:
            clean_desc = self._clean_html(description)
            if clean_desc:
                parts.append(clean_desc[:200])
        
        # 3. Scope names (NEW - the gold data)
        scope_names = circuit.get('scope_names', [])
        if scope_names:
            # Join scope names, limit to avoid overwhelming the embedding
            scope_text = ', '.join(scope_names[:5])
            parts.append(f"Modules: {scope_text}")
        
        # 4. Tags
        tags = circuit.get('tags', [])
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")
        
        # 5. Circuit type classification
        breakdown = circuit.get('component_breakdown', {})
        if breakdown:
            if self._is_sequential(breakdown):
                parts.append("Sequential logic circuit")
                if 'Clock' in breakdown:
                    parts.append("Clocked operation")
            else:
                parts.append("Combinational logic circuit")
        
        # 6. Distinctive components
        distinctive = self._get_distinctive_components(breakdown)
        if distinctive:
            comp_text = ', '.join(distinctive[:5])
            parts.append(f"Components: {comp_text}")
        
        # 7. I/O summary
        input_count = breakdown.get('Input', 0)
        output_count = breakdown.get('Output', 0)
        if input_count > 0 or output_count > 0:
            parts.append(f"{input_count} inputs, {output_count} outputs")
        
        # Join all parts
        embedding_text = ". ".join(parts)
        if embedding_text and not embedding_text.endswith('.'):
            embedding_text += "."
        
        return embedding_text if embedding_text else "Empty circuit"
    
    def generate_embeddings(self, circuits_file, output_dir="embeddings"):
        """
        Generate embeddings for all circuits
        
        Args:
            circuits_file: Path to circuits JSON (with scope names)
            output_dir: Directory to save embeddings
        
        Returns:
            dict with paths to output files
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        print(f"\n{'='*70}")
        print("LOADING CIRCUITS")
        print(f"{'='*70}")
        
        with open(circuits_file, 'r', encoding='utf-8') as f:
            circuits = json.load(f)
        
        print(f"Loaded {len(circuits):,} circuits from: {circuits_file}")

        print(f"\n{'='*70}")
        print("GENERATING EMBEDDING TEXTS")
        print(f"{'='*70}")
        
        embedding_texts = []
        for circuit in tqdm(circuits, desc="Creating texts", unit="circuit"):
            text = self.create_embedding_text(circuit)
            embedding_texts.append(text)

        print(f"\n{'='*70}")
        print("SAMPLE EMBEDDING TEXTS")
        print(f"{'='*70}")
        
        sample_indices = [0, 100, 200, 300, 400]
        for idx in sample_indices:
            if idx < len(circuits):
                circuit = circuits[idx]
                text = embedding_texts[idx]
                
                print(f"\nCircuit {idx}:")
                print(f"  Name: {circuit['name']}")
                print(f"  Components: {circuit.get('component_count', 0)}")
                print(f"  Scope names: {len(circuit.get('scope_names', []))}")
                print(f"  Embedding text: {text[:150]}...")
        
        text_lengths = [len(t) for t in embedding_texts]
        avg_length = sum(text_lengths) / len(text_lengths)
        
        print(f"\n{'='*70}")
        print("TEXT STATISTICS")
        print(f"{'='*70}")
        print(f"Average text length: {avg_length:.1f} characters")
        print(f"Min length: {min(text_lengths)}")
        print(f"Max length: {max(text_lengths)}")
        
        print(f"\n{'='*70}")
        print("GENERATING EMBEDDINGS")
        print(f"{'='*70}")
        print(f"Processing {len(embedding_texts):,} texts...")
        print("This will take approximately 5-10 minutes...\n")
        
        embeddings = self.model.encode(
            embedding_texts,
            batch_size=32,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        print(f"\nEmbeddings generated: {embeddings.shape}")
        print(f"  Circuits: {embeddings.shape[0]:,}")
        print(f"  Dimensions: {embeddings.shape[1]}")
        
        print(f"\n{'='*70}")
        print("SAVING FILES")
        print(f"{'='*70}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Save embeddings as numpy array
        embeddings_file = output_dir / f"embeddings_{len(circuits)}_{timestamp}.npy"
        np.save(embeddings_file, embeddings)
        size_mb = embeddings_file.stat().st_size / (1024 * 1024)
        print(f"Saved embeddings: {embeddings_file}")
        print(f"  Size: {size_mb:.2f} MB")
        
        # 2. Save circuits with enriched texts
        circuits_enriched = []
        for circuit, text in zip(circuits, embedding_texts):
            circuit_copy = circuit.copy()
            circuit_copy['embedding_text'] = text
            circuits_enriched.append(circuit_copy)
        
        circuits_file = output_dir / f"circuits_enriched_{len(circuits)}_{timestamp}.json"
        with open(circuits_file, 'w', encoding='utf-8') as f:
            json.dump(circuits_enriched, f, indent=2, ensure_ascii=False)
        size_mb = circuits_file.stat().st_size / (1024 * 1024)
        print(f"Saved enriched circuits: {circuits_file}")
        print(f"  Size: {size_mb:.2f} MB")
        
        # 3. Save metadata
        with_descriptions = sum(1 for c in circuits if c.get('description'))
        with_scope_names = sum(1 for c in circuits if c.get('scope_names'))
        with_components = sum(1 for c in circuits if c.get('component_count', 0) > 0)
        
        metadata = {
            'timestamp': timestamp,
            'num_circuits': len(circuits),
            'embedding_dimension': int(embeddings.shape[1]),
            'model_name': 'sentence-transformers/all-MiniLM-L12-v2',
            'circuits_with_descriptions': with_descriptions,
            'circuits_with_scope_names': with_scope_names,
            'circuits_with_components': with_components,
            'mean_text_length': avg_length,
            'embeddings_normalized': True,
            'files': {
                'embeddings': str(embeddings_file.name),
                'circuits': str(circuits_file.name)
            }
        }
        
        metadata_file = output_dir / f"metadata_{len(circuits)}_{timestamp}.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"Saved metadata: {metadata_file}")

        print(f"\n{'='*70}")
        print("DATA QUALITY SUMMARY")
        print(f"{'='*70}")
        print(f"Circuits with descriptions: {with_descriptions:,} ({with_descriptions/len(circuits)*100:.1f}%)")
        print(f"Circuits with scope names: {with_scope_names:,} ({with_scope_names/len(circuits)*100:.1f}%)")
        print(f"Circuits with components: {with_components:,} ({with_components/len(circuits)*100:.1f}%)")
        
        print(f"\n{'='*70}")
        print("COMPLETE")
        print(f"{'='*70}")
        
        return {
            'embeddings_file': embeddings_file,
            'circuits_file': circuits_file,
            'metadata_file': metadata_file,
            'metadata': metadata
        }


if __name__ == "__main__":

    INPUT_FILE = "circuit_collection_full/circuits_with_scopes_1000_20251021_220343.json"
    OUTPUT_DIR = "embeddings"
    
    print("="*70)
    print("CircuitVerse Embedding Generator")
    print("="*70)
    print(f"\nInput: {INPUT_FILE}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Model: all-MiniLM-L12-v2 (384 dimensions)\n")
    
    generator = CircuitEmbeddingGenerator()
    output_files = generator.generate_embeddings(INPUT_FILE, OUTPUT_DIR)
    
    print("\nGenerated files:")
    for key, path in output_files.items():
        if key != 'metadata':
            print(f"  {key}: {path}")