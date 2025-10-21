"""
extract_scope_names.py - Extract scope names from CircuitVerse API
Fetches circuit_data for selected circuits to get scope names
"""

import json
import time
import requests
from pathlib import Path
from tqdm import tqdm
from datetime import datetime


class ScopeNameExtractor:
    """Extract scope names from CircuitVerse circuit data"""
    BASE_URL = "https://circuitverse.org/api/v1"
    DELAY_BETWEEN_REQUESTS = 0.2
    MAX_RETRIES = 3
    
    def __init__(self, circuits_file, output_dir="circuit_collection_full"):
        self.circuits_file = Path(circuits_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
        with open(self.circuits_file, 'r', encoding='utf-8') as f:
            self.all_circuits = json.load(f)
        
        self.selected_circuits = []
        self.errors = []
        
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_requests': 0,
            'successful_fetches': 0,
            'failed_fetches': 0,
            'circuits_with_scope_names': 0,
            'total_scope_names_found': 0
        }
    
    def select_circuits(self, target_count=1000):
        """
        Select circuits with stratified sampling to match real-world distribution:
        - 20% Tier 1: Good metadata (description OR meaningful name + high views)
        - 50% Tier 2: Generic name + decent components + NO description (our target!)
        - 30% Tier 3: Poor circuits (generic + few components OR empty)
        """
        
        print(f"Selecting {target_count} circuits with stratified sampling...")
        print("Target distribution: 20% Tier 1, 50% Tier 2, 30% Tier 3\n")
        
        # Classify circuits
        tier1 = []  # Good metadata
        tier2 = []  # Generic name + components (our value prop!)
        tier3 = []  # Poor/empty
        
        generic_patterns = ['untitled', 'project', 'assignment', 'homework', 
                        'lab', 'test', 'demo', 'ex', 'tp', 'experiment']
        
        for circuit in self.all_circuits:
            has_desc = bool(circuit.get('description'))
            name = circuit.get('name', '').lower()
            is_generic = any(p in name for p in generic_patterns)
            comp_count = circuit.get('component_count', 0)
            views = circuit.get('view', 0)
            
            # Tier 1: Has description OR (meaningful name AND good views)
            if has_desc or (not is_generic and views > 50):
                tier1.append(circuit)
            
            # Tier 2: Generic name + decent components + NO description
            elif is_generic and comp_count >= 10 and not has_desc:
                tier2.append(circuit)
            
            # Tier 3: Everything else (poor/empty)
            else:
                tier3.append(circuit)
        
        print(f"Available circuits:")
        print(f"  Tier 1 (Good metadata): {len(tier1)}")
        print(f"  Tier 2 (Our target - generic + components): {len(tier2)}")
        print(f"  Tier 3 (Poor/empty): {len(tier3)}")

        import random
        random.seed(42)
        
        n_tier1 = min(int(target_count * 0.2), len(tier1))
        n_tier2 = min(int(target_count * 0.5), len(tier2))
        n_tier3 = min(target_count - n_tier1 - n_tier2, len(tier3))
        
        selected = []
        selected.extend(random.sample(tier1, n_tier1))
        selected.extend(random.sample(tier2, n_tier2))
        selected.extend(random.sample(tier3, n_tier3))

        random.shuffle(selected)
        
        self.selected_circuits = selected
        
        print(f"\nSelected {len(selected)} circuits:")
        print(f"  Tier 1 (Good): {n_tier1} ({n_tier1/len(selected)*100:.1f}%)")
        print(f"  Tier 2 (Target): {n_tier2} ({n_tier2/len(selected)*100:.1f}%)")
        print(f"  Tier 3 (Poor): {n_tier3} ({n_tier3/len(selected)*100:.1f}%)")
        print()
    
    def _make_request(self, url):
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
    
    def _extract_scope_names(self, circuit_data):
        scope_names = []
        
        try:
            if not circuit_data:
                return scope_names
            
            scopes = circuit_data.get('scopes', [])
            
            for scope in scopes:
                if not isinstance(scope, dict):
                    continue
                
                name = scope.get('name', '')
            
                if name and name not in ['Main', 'Untitled', '', 'main', 'untitled']:
                    name = name.strip()
                    if len(name) > 2:
                        scope_names.append(name)
        
        except Exception as e:
            self.errors.append({
                'error_type': 'scope_extraction',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        
        return scope_names
    
    def extract_scopes(self):
        print("Starting scope name extraction")
        print(f"Target: {len(self.selected_circuits)} circuits\n")
        
        self.stats['start_time'] = datetime.now().isoformat()
        
        results = []
        
        with tqdm(total=len(self.selected_circuits), desc="Extracting scopes", unit="circuit") as pbar:
            for circuit in self.selected_circuits:
                project_id = circuit['id']

                url = f"{self.BASE_URL}/projects/{project_id}/circuit_data"
                circuit_data = self._make_request(url)
                
                if circuit_data is None:
                    self.stats['failed_fetches'] += 1
                    circuit_copy = circuit.copy()
                    circuit_copy['scope_names'] = []
                    results.append(circuit_copy)
                    
                    pbar.update(1)
                    time.sleep(self.DELAY_BETWEEN_REQUESTS)
                    continue
                
                scope_names = self._extract_scope_names(circuit_data)

                self.stats['successful_fetches'] += 1
                if scope_names:
                    self.stats['circuits_with_scope_names'] += 1
                    self.stats['total_scope_names_found'] += len(scope_names)

                circuit_copy = circuit.copy()
                circuit_copy['scope_names'] = scope_names
                results.append(circuit_copy)
                
                pbar.update(1)
                time.sleep(self.DELAY_BETWEEN_REQUESTS)
        
        self.stats['end_time'] = datetime.now().isoformat()
        
        self._print_summary()
        self._save_data(results)
        
        return results
    
    def _print_summary(self):
        print(f"\n{'='*70}")
        print("EXTRACTION COMPLETE")
        print(f"{'='*70}")
        
        print(f"\nAPI STATS:")
        print(f"  Total requests: {self.stats['total_requests']}")
        print(f"  Successful: {self.stats['successful_fetches']}")
        print(f"  Failed: {self.stats['failed_fetches']}")
        
        if self.stats['successful_fetches'] > 0:
            print(f"\nSCOPE NAME STATS:")
            print(f"  Circuits with scope names: {self.stats['circuits_with_scope_names']} "
                  f"({self.stats['circuits_with_scope_names']/self.stats['successful_fetches']*100:.1f}%)")
            print(f"  Total scope names found: {self.stats['total_scope_names_found']}")
            
            if self.stats['circuits_with_scope_names'] > 0:
                avg_scopes = self.stats['total_scope_names_found'] / self.stats['circuits_with_scope_names']
                print(f"  Average scopes per circuit (when present): {avg_scopes:.1f}")
        
        if self.errors:
            print(f"\nErrors: {len(self.errors)}")
    
    def _save_data(self, results):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        output_file = self.output_dir / f"circuits_with_scopes_{len(results)}_{timestamp}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nSaved circuits with scopes: {output_file}")

        stats_file = self.output_dir / f"scope_extraction_stats_{timestamp}.json"
        with open(stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Saved statistics: {stats_file}")

        if self.errors:
            errors_file = self.output_dir / f"scope_extraction_errors_{timestamp}.json"
            with open(errors_file, 'w') as f:
                json.dump(self.errors, f, indent=2)
            print(f"Saved errors: {errors_file}")

        circuits_with_scopes = [c for c in results if c.get('scope_names')]
        if circuits_with_scopes:
            print(f"\n{'='*70}")
            print("SAMPLE CIRCUITS WITH SCOPE NAMES")
            print(f"{'='*70}")
            
            for i, circuit in enumerate(circuits_with_scopes[:5], 1):
                print(f"\n{i}. {circuit['name']}")
                print(f"   Scope names: {circuit['scope_names']}")
                print(f"   Components: {circuit.get('component_count', 0)}")


if __name__ == "__main__":
    CIRCUITS_FILE = "circuit_collection_full/circuits_10000_20251021_205125.json"
    TARGET_COUNT = 1000
    
    print("="*70)
    print("CircuitVerse Scope Name Extractor")
    print("="*70)
    print(f"\nInput: {CIRCUITS_FILE}")
    print(f"Target: {TARGET_COUNT} circuits")
    print(f"Sampling: 40% high quality, 40% medium, 20% low quality\n")
    
    extractor = ScopeNameExtractor(CIRCUITS_FILE)
    extractor.select_circuits(TARGET_COUNT)
    extractor.extract_scopes()