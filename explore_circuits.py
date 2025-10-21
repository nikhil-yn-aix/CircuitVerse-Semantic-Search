"""
CircuitVerse Circuit Data Collector
Collects circuit metadata + component
"""

import requests
import json
import time
import random
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
from collections import Counter


class CircuitVerseDataCollector:
    BASE_URL = "https://circuitverse.org/api/v1"
    DELAY_BETWEEN_REQUESTS = 0.2
    MAX_RETRIES = 3
    
    # list of CircuitVerse component types
    COMPONENT_TYPES = [
        'Input', 'Output', 'Button', 'Power', 'Ground',
        'AndGate', 'OrGate', 'NotGate', 'NandGate', 'NorGate', 
        'XorGate', 'XnorGate',
        'DflipFlop', 'SRflipFlop', 'JKflipFlop', 'TflipFlop',
        'FullAdder', 'HalfAdder', 'Multiplexer', 'Demultiplexer',
        'Decoder', 'Encoder', 'Splitter', 'ConstantVal',
        'TriState', 'ControlledInverter', 'Clock',
        'LED', 'SevenSegDisplay', 'HexDisplay', 'RGBLed',
        'Stepper', 'TTY', 'Random',
        'Counter', 'ALU', 'MSB', 'LSB',
        'BitSelector', 'DigitalLed', 'VariableLed',
        'EEPROM', 'Rom', 'Ram', 'Tunnel',
        'Rectangle', 'Text', 'Arrow',
        'SubCircuit'
    ]
    
    def __init__(self, metadata_file, num_circuits=200, sampling_mode='random', 
                 min_views=0, output_dir="circuit_collection"):
        """
        Args:
            metadata_file: Path to projects_metadata JSON file
            num_circuits: Number of circuits to collect
            sampling_mode: 'random', 'top_viewed', 'recent', or 'all'
            min_views: Minimum view count filter
            output_dir: Directory to save results
        """
        self.metadata_file = Path(metadata_file)
        self.num_circuits = num_circuits
        self.sampling_mode = sampling_mode
        self.min_views = min_views
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        with open(self.metadata_file, 'r', encoding='utf-8') as f:
            all_projects = json.load(f)
        
        self.all_projects = [p for p in all_projects if p['view'] >= min_views]
        print(f"Loaded {len(all_projects):,} projects")
        print(f"After filtering (views >= {min_views}): {len(self.all_projects):,} projects")
        
        self.collected_circuits = []
        self.errors = []
        
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_requests': 0,
            'successful_fetches': 0,
            'failed_fetches': 0,
            'empty_circuits': 0,
            'component_statistics': {}
        }
    
    def _select_circuits(self):
        """Select circuits based on sampling mode"""
        available = len(self.all_projects)
        target = min(self.num_circuits, available)
        
        if self.sampling_mode == 'random':
            indices = random.sample(range(available), target)
            return [self.all_projects[i] for i in indices]
        
        elif self.sampling_mode == 'top_viewed':
            sorted_projects = sorted(self.all_projects, key=lambda x: x['view'], reverse=True)
            return sorted_projects[:target]
        
        elif self.sampling_mode == 'recent':
            sorted_projects = sorted(self.all_projects, key=lambda x: x['created_at'], reverse=True)
            return sorted_projects[:target]
        
        elif self.sampling_mode == 'all':
            return self.all_projects[:target]
        
        else:
            raise ValueError(f"Unknown sampling_mode: {self.sampling_mode}")
    
    def _make_request(self, url):
        """Make API request"""
        for attempt in range(self.MAX_RETRIES):
            try:
                self.stats['total_requests'] += 1
                response = requests.get(
                    url,
                    timeout=15,
                    headers={'Accept': 'application/json'}
                )
                
                if response.status_code == 429:
                    wait_time = 60
                    print(f"\nRate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                if response.status_code in [404, 403]:
                    return None
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == self.MAX_RETRIES - 1:
                    self.errors.append({
                        'url': url,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
                    return None
                time.sleep(2 ** attempt)
        
        return None
    
    def _extract_components(self, circuit_data):
        """
        Extract components from circuit data
        Only uses component-type keys in scope object
        """
        component_list = []
        
        try:
            if not circuit_data:
                return component_list
            
            scopes = circuit_data.get('scopes', [])
            
            for scope in scopes:
                if not isinstance(scope, dict):
                    continue
            
                for comp_type in self.COMPONENT_TYPES:
                    if comp_type in scope:
                        comp_instances = scope[comp_type]
                        if isinstance(comp_instances, list):
                            component_list.extend([comp_type] * len(comp_instances))
            
        except Exception as e:
            self.errors.append({
                'error_type': 'component_extraction',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        
        return component_list
    
    def collect(self):
        print(f"\nStarting circuit collection")
        print(f"Mode: {self.sampling_mode}")
        print(f"Target: {self.num_circuits:,} circuits")
        print(f"Min views filter: {self.min_views}\n")
        
        self.stats['start_time'] = datetime.now().isoformat()
        
        # Select circuits
        selected_projects = self._select_circuits()
        
        print(f"Selected {len(selected_projects):,} circuits to fetch\n")
        
        # Collect circuit data
        with tqdm(total=len(selected_projects), desc="Collecting circuits", unit="circuit") as pbar:
            for project in selected_projects:
                project_id = project['id']
                
                # Fetch circuit data
                url = f"{self.BASE_URL}/projects/{project_id}/circuit_data"
                circuit_data = self._make_request(url)
                
                if circuit_data is None:
                    self.stats['failed_fetches'] += 1
                    pbar.update(1)
                    time.sleep(self.DELAY_BETWEEN_REQUESTS)
                    continue
                
                # Extract components
                components = self._extract_components(circuit_data)
                component_count = len(components)
                unique_types = list(set(components))
                
                # Track empty circuits
                if component_count == 0:
                    self.stats['empty_circuits'] += 1
                
                # Build complete circuit record
                circuit_record = {
                    # Metadata
                    'id': project['id'],
                    'name': project['name'],
                    'description': project['description'],
                    'tags': project['tags'],
                    'view': project['view'],
                    'created_at': project['created_at'],
                    'project_access_type': project['project_access_type'],
                    
                    # Component data
                    'components': components,
                    'component_count': component_count,
                    'unique_component_types': len(unique_types),
                    'component_breakdown': dict(Counter(components))
                }
                
                self.collected_circuits.append(circuit_record)
                self.stats['successful_fetches'] += 1
                
                pbar.update(1)
                time.sleep(self.DELAY_BETWEEN_REQUESTS)
        
        self.stats['end_time'] = datetime.now().isoformat()
        
        self._compute_statistics()
        self._print_summary()
        self._save_data()
    
    def _compute_statistics(self):
        if not self.collected_circuits:
            return
        
        counts = [c['component_count'] for c in self.collected_circuits]
        all_components = []
        for c in self.collected_circuits:
            all_components.extend(c['components'])
        
        self.stats['component_statistics'] = {
            'total_circuits': len(self.collected_circuits),
            'circuits_with_components': sum(1 for c in counts if c > 0),
            'empty_circuits': self.stats['empty_circuits'],
            'mean_components': sum(counts) / len(counts) if counts else 0,
            'median_components': sorted(counts)[len(counts) // 2] if counts else 0,
            'min_components': min(counts) if counts else 0,
            'max_components': max(counts) if counts else 0,
            'total_components': sum(counts),
            'unique_component_types_used': len(set(all_components)),
            'component_type_distribution': dict(Counter(all_components).most_common(20))
        }
    
    def _print_summary(self):
        print(f"\n{'='*70}")
        print(f"COLLECTION COMPLETE")
        print(f"{'='*70}")
        
        print(f"\nCOLLECTION STATS:")
        print(f"  Circuits collected: {self.stats['successful_fetches']:,}")
        print(f"  Failed fetches: {self.stats['failed_fetches']:,}")
        print(f"  Total API requests: {self.stats['total_requests']:,}")
        
        cs = self.stats['component_statistics']
        if cs:
            print(f"\nCOMPONENT STATS:")
            print(f"  Circuits with components: {cs['circuits_with_components']:,} ({cs['circuits_with_components']/cs['total_circuits']*100:.1f}%)")
            print(f"  Empty circuits: {cs['empty_circuits']:,} ({cs['empty_circuits']/cs['total_circuits']*100:.1f}%)")
            print(f"  Mean components/circuit: {cs['mean_components']:.1f}")
            print(f"  Median components: {cs['median_components']}")
            print(f"  Range: {cs['min_components']} - {cs['max_components']}")
            print(f"  Total components collected: {cs['total_components']:,}")
            
            print(f"\nTOP 15 COMPONENT TYPES:")
            for comp_type, count in list(cs['component_type_distribution'].items())[:15]:
                print(f"  {comp_type:<30} {count:>6,}")
        
        print(f"\n{'='*70}")
    
    def _save_data(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save circuits
        circuits_file = self.output_dir / f"circuits_{self.num_circuits}_{timestamp}.json"
        with open(circuits_file, 'w', encoding='utf-8') as f:
            json.dump(self.collected_circuits, f, indent=2, ensure_ascii=False)
        print(f"\nSaved circuits: {circuits_file}")
        
        # Save statistics
        stats_file = self.output_dir / f"statistics_{self.num_circuits}_{timestamp}.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Saved statistics: {stats_file}")
        
        # Save errors if any
        if self.errors:
            errors_file = self.output_dir / f"errors_{self.num_circuits}_{timestamp}.json"
            with open(errors_file, 'w', encoding='utf-8') as f:
                json.dump(self.errors, f, indent=2)
            print(f"Saved errors: {errors_file}")


if __name__ == "__main__":
    CONFIG = {
        'metadata_file': 'data/projects_metadata_20251021_155524.json',
        'num_circuits': 10000,
        'sampling_mode': 'random',    # Options: 'random', 'top_viewed', 'recent', 'all'
        'min_views': 0,
        'output_dir': 'circuit_collection_full'
    }
    
    print("="*70)
    print("CircuitVerse Circuit Data Collector")
    print("="*70)
    print(f"\nConfiguration:")
    for key, value in CONFIG.items():
        print(f"  {key}: {value}")
    
    collector = CircuitVerseDataCollector(**CONFIG)
    collector.collect()