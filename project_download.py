"""
CircuitVerse Metadata Collection Script
Phase 1: Collect project metadata from public API
"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime
from tqdm import tqdm


class CircuitVerseCollector:
    """Collects project metadata from CircuitVerse API"""

    BASE_URL = "https://circuitverse.org/api/v1"
    DEFAULT_PAGE_SIZE = 100
    DELAY_BETWEEN_REQUESTS = 0.15  # 150ms delay
    MAX_RETRIES = 3
    
    def __init__(self, target_count=10000, output_dir="data"):
        self.target_count = target_count
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.collected = []
        self.errors = []
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_requests': 0,
            'failed_requests': 0,
            'projects_collected': 0
        }
    
    def _make_request(self, url, params=None):
        for attempt in range(self.MAX_RETRIES):
            try:
                self.stats['total_requests'] += 1
                response = requests.get(
                    url, 
                    params=params,
                    timeout=10,
                    headers={'Accept': 'application/json'}
                )
                
                if response.status_code == 429:
                    wait_time = 60
                    print(f"\nRate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                self.stats['failed_requests'] += 1
                if attempt == self.MAX_RETRIES - 1:
                    self.errors.append({
                        'url': url,
                        'params': params,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat()
                    })
                    return None
                time.sleep(2 ** attempt)
        
        return None
    
    def _extract_project_data(self, project_raw):
        try:
            attrs = project_raw['attributes']

            tags = []
            if attrs.get('tags'):
                tags = [tag.get('name', '') for tag in attrs['tags'] if tag.get('name')]
            
            return {
                'id': project_raw['id'],
                'name': attrs.get('name', 'Untitled'),
                'description': attrs.get('description', ''),
                'tags': tags,
                'view': attrs.get('view', 0),
                'created_at': attrs.get('created_at', ''),
                'project_access_type': attrs.get('project_access_type', '')
            }
        except (KeyError, TypeError) as e:
            self.errors.append({
                'project_id': project_raw.get('id', 'unknown'),
                'error': f"Data extraction error: {str(e)}",
                'timestamp': datetime.now().isoformat()
            })
            return None
    
    def collect_metadata(self):
        print(f"Starting CircuitVerse metadata collection")
        print(f"Target: {self.target_count:,} projects\n")
        
        self.stats['start_time'] = datetime.now().isoformat()
        
        page_number = 1
        has_more = True
        
        with tqdm(total=self.target_count, desc="Collecting projects", unit="project") as pbar:
            while has_more and len(self.collected) < self.target_count:
                params = {
                    'page[number]': page_number,
                    'page[size]': self.DEFAULT_PAGE_SIZE
                }
                
                data = self._make_request(f"{self.BASE_URL}/projects", params)
                
                if not data:
                    print(f"\n❌ Failed to fetch page {page_number}. Stopping.")
                    break

                projects = data.get('data', [])
                
                if not projects:
                    has_more = False
                    break

                for project_raw in projects:
                    if len(self.collected) >= self.target_count:
                        break

                    if project_raw.get('attributes', {}).get('project_access_type') == 'Public':
                        project_data = self._extract_project_data(project_raw)
                        
                        if project_data:
                            self.collected.append(project_data)
                            pbar.update(1)
                
                links = data.get('links', {})
                has_more = 'next' in links and links['next'] is not None
                
                page_number += 1

                time.sleep(self.DELAY_BETWEEN_REQUESTS)
        
        self.stats['end_time'] = datetime.now().isoformat()
        self.stats['projects_collected'] = len(self.collected)
        
        self._print_summary()
        self._save_data()
    
    def _print_summary(self):

        print(f"\n{'='*60}")
        print(f"Collection Complete!")
        print(f"{'='*60}")
        print(f"Projects collected: {self.stats['projects_collected']:,}")
        print(f"Total API requests: {self.stats['total_requests']:,}")
        print(f"Failed requests: {self.stats['failed_requests']:,}")
        print(f"Errors logged: {len(self.errors):,}")
        
        if self.collected:
            with_description = sum(1 for p in self.collected if p['description'])
            with_tags = sum(1 for p in self.collected if p['tags'])
            
            print(f"\nData Quality:")
            print(f"   Projects with descriptions: {with_description:,} ({with_description/len(self.collected)*100:.1f}%)")
            print(f"   Projects with tags: {with_tags:,} ({with_tags/len(self.collected)*100:.1f}%)")

            all_tags = {}
            for p in self.collected:
                for tag in p['tags']:
                    all_tags[tag] = all_tags.get(tag, 0) + 1
            
            if all_tags:
                top_tags = sorted(all_tags.items(), key=lambda x: x[1], reverse=True)[:10]
                print(f"\nTop 10 Tags:")
                for tag, count in top_tags:
                    print(f"   {tag}: {count}")
    
    def _save_data(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        projects_file = self.output_dir / f"projects_metadata_{timestamp}.json"
        with open(projects_file, 'w', encoding='utf-8') as f:
            json.dump(self.collected, f, indent=2, ensure_ascii=False)
        print(f"\nSaved projects: {projects_file}")
        
        stats_file = self.output_dir / f"collection_stats_{timestamp}.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)
        print(f"Saved stats: {stats_file}")
        
        if self.errors:
            errors_file = self.output_dir / f"collection_errors_{timestamp}.json"
            with open(errors_file, 'w', encoding='utf-8') as f:
                json.dump(self.errors, f, indent=2)
            print(f"Saved errors: {errors_file}")


if __name__ == "__main__":
    collector = CircuitVerseCollector(target_count=10000, output_dir="data")
    collector.collect_metadata()