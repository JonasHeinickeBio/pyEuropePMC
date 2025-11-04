# Advanced Examples

**Level**: ⭐⭐⭐ Advanced
**Examples**: 3 scripts
**Time**: 30-45 minutes

## Overview

Power user techniques and advanced patterns for sophisticated use cases. Master complex workflows, performance optimization, and production-ready patterns.

## 🐍 Examples

### 01-parser-advanced.ipynb
**Advanced parsing techniques**

Master complex parsing:
- Multi-document processing
- Custom extraction pipelines
- Error recovery strategies
- Performance optimization
- Memory-efficient streaming

**What you'll build**: Production parser pipeline

**Key topics**:
- Batch processing
- Custom extractors
- Error handling
- Performance tuning

### 02-progress-callbacks.py
**Long-running operation monitoring**

Track progress:
- Custom progress callbacks
- Real-time status updates
- Time estimation
- Error aggregation
- Logging integration

**What you'll build**: Monitored bulk processor

**Key topics**:
- Callback functions
- Progress tracking
- Status reporting
- Error handling

### 03-schema-coverage.py
**XML schema analysis**

Analyze corpus schemas:
- Schema detection across corpus
- Coverage statistics
- Element frequency analysis
- Schema variation detection
- Compatibility checking

**What you'll build**: Schema analyzer tool

**Key topics**:
- Schema analysis
- Statistical analysis
- Corpus profiling
- Compatibility testing

## 🚀 Quick Examples

### Progress Tracking
```python
def progress_callback(current, total, article_id, status):
    percent = (current / total) * 100
    print(f"[{percent:.1f}%] {article_id}: {status}")

# Process with progress
for i, article_id in enumerate(article_ids):
    progress_callback(i+1, len(article_ids), article_id, "Processing")
    # ... process article ...
```

### Batch Processing Pipeline
```python
from pyeuropepmc.fulltext_parser import FullTextXMLParser
import os

def process_xml_batch(xml_dir, output_dir):
    """Process all XML files in directory."""
    xml_files = [f for f in os.listdir(xml_dir) if f.endswith('.xml')]

    for xml_file in xml_files:
        with open(os.path.join(xml_dir, xml_file)) as f:
            parser = FullTextXMLParser(f.read())

        # Extract and save
        metadata = parser.extract_metadata()
        tables = parser.extract_tables()

        # Save results
        save_results(metadata, tables, output_dir)
```

### Schema Coverage Analysis
```python
from collections import defaultdict

def analyze_corpus_schemas(xml_files):
    """Analyze schema coverage across corpus."""
    schemas = defaultdict(int)
    elements = defaultdict(int)

    for xml_file in xml_files:
        parser = FullTextXMLParser(open(xml_file).read())
        schema = parser.detect_schema()

        # Count schema types
        schemas[schema.table_structure] += 1

        # Count element types
        for elem_type in schema.citation_types:
            elements[elem_type] += 1

    return schemas, elements
```

## 🎯 Advanced Techniques

### 1. Streaming Processing
Handle large files efficiently:
```python
import xml.etree.ElementTree as ET

def stream_process_large_xml(xml_file):
    """Process large XML without loading into memory."""
    context = ET.iterparse(xml_file, events=('start', 'end'))

    for event, elem in context:
        if event == 'end' and elem.tag == 'article':
            # Process article element
            process_article(elem)
            # Clear to free memory
            elem.clear()
```

### 2. Parallel Processing
Process multiple articles concurrently:
```python
from concurrent.futures import ProcessPoolExecutor
from functools import partial

def process_article(xml_path):
    parser = FullTextXMLParser(open(xml_path).read())
    return parser.extract_metadata()

# Process in parallel
xml_files = get_xml_files()

with ProcessPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_article, xml_files))
```

### 3. Error Recovery
Robust error handling:
```python
class ProcessingError:
    def __init__(self, file, error, context):
        self.file = file
        self.error = error
        self.context = context

def robust_process(xml_files):
    """Process with comprehensive error handling."""
    successful = []
    failed = []

    for xml_file in xml_files:
        try:
            result = process_with_retries(xml_file)
            successful.append(result)
        except Exception as e:
            failed.append(ProcessingError(xml_file, e, get_context()))

    return successful, failed
```

### 4. Custom Extractors
Build specialized extractors:
```python
class CustomTableExtractor:
    """Extract tables with custom logic."""

    def __init__(self, parser):
        self.parser = parser

    def extract_numeric_tables(self):
        """Extract only tables with numeric data."""
        tables = self.parser.extract_tables()

        numeric_tables = []
        for table in tables:
            if self.is_numeric_table(table):
                numeric_tables.append(table)

        return numeric_tables

    def is_numeric_table(self, table):
        """Check if table contains mostly numbers."""
        # Custom logic here
        pass
```

### 5. Pipeline Architecture
Build processing pipelines:
```python
class ProcessingPipeline:
    """Modular processing pipeline."""

    def __init__(self):
        self.stages = []

    def add_stage(self, stage_func):
        """Add processing stage."""
        self.stages.append(stage_func)

    def process(self, data):
        """Run all stages."""
        result = data
        for stage in self.stages:
            result = stage(result)
        return result

# Usage
pipeline = ProcessingPipeline()
pipeline.add_stage(parse_xml)
pipeline.add_stage(extract_metadata)
pipeline.add_stage(validate_data)
pipeline.add_stage(save_results)

pipeline.process(xml_file)
```

## 💡 Production Patterns

### Batch Processing with Checkpoints
```python
import json
import os

class CheckpointedProcessor:
    """Process with checkpoint recovery."""

    def __init__(self, checkpoint_file='checkpoint.json'):
        self.checkpoint_file = checkpoint_file
        self.processed = self.load_checkpoint()

    def load_checkpoint(self):
        if os.path.exists(self.checkpoint_file):
            with open(self.checkpoint_file) as f:
                return set(json.load(f))
        return set()

    def save_checkpoint(self):
        with open(self.checkpoint_file, 'w') as f:
            json.dump(list(self.processed), f)

    def process_batch(self, items):
        for item in items:
            if item in self.processed:
                continue  # Skip already processed

            try:
                self.process_item(item)
                self.processed.add(item)
                self.save_checkpoint()
            except Exception as e:
                print(f"Error processing {item}: {e}")
```

### Memory-Efficient Processing
```python
def process_large_corpus(xml_dir, batch_size=100):
    """Process large corpus in batches."""
    xml_files = os.listdir(xml_dir)

    for i in range(0, len(xml_files), batch_size):
        batch = xml_files[i:i+batch_size]

        # Process batch
        results = process_batch(batch)

        # Save intermediate results
        save_batch_results(results, i // batch_size)

        # Clear memory
        del results
        gc.collect()
```

### Monitoring and Alerting
```python
import logging
from datetime import datetime

class ProcessingMonitor:
    """Monitor processing with alerts."""

    def __init__(self):
        self.start_time = datetime.now()
        self.processed = 0
        self.errors = 0
        self.logger = logging.getLogger(__name__)

    def record_success(self):
        self.processed += 1

    def record_error(self, error):
        self.errors += 1
        self.logger.error(f"Processing error: {error}")

        # Alert if error rate too high
        if self.errors / max(self.processed, 1) > 0.1:
            self.send_alert("High error rate detected!")

    def get_stats(self):
        elapsed = (datetime.now() - self.start_time).seconds
        rate = self.processed / max(elapsed, 1)

        return {
            'processed': self.processed,
            'errors': self.errors,
            'rate': rate,
            'elapsed': elapsed
        }
```

## 📊 Performance Optimization

### Profiling
```python
import cProfile
import pstats

def profile_processing(func, *args):
    """Profile function execution."""
    profiler = cProfile.Profile()
    profiler.enable()

    result = func(*args)

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)

    return result
```

### Memory Profiling
```python
from memory_profiler import profile

@profile
def process_article(xml_path):
    """Process with memory profiling."""
    parser = FullTextXMLParser(open(xml_path).read())
    metadata = parser.extract_metadata()
    return metadata
```

### Benchmarking
```python
import time
from statistics import mean, stdev

def benchmark_operation(func, args_list, iterations=3):
    """Benchmark operation across multiple runs."""
    times = []

    for _ in range(iterations):
        start = time.time()
        for args in args_list:
            func(*args)
        elapsed = time.time() - start
        times.append(elapsed)

    return {
        'mean': mean(times),
        'stdev': stdev(times),
        'min': min(times),
        'max': max(times)
    }
```

## 🆘 Production Checklist

- [ ] Error handling and recovery
- [ ] Progress tracking and logging
- [ ] Resource management (memory, disk)
- [ ] Checkpoint and resume capability
- [ ] Monitoring and alerting
- [ ] Performance profiling
- [ ] Test with edge cases
- [ ] Documentation and runbooks

## 🔗 Resources

- [Performance Guide](../../docs/advanced/performance.md)
- [Best Practices](../../docs/advanced/best-practices.md)
- [API Reference](../../docs/api/)

## 🎓 Learning Path

1. **Understand basics**: Master core features first
2. **Study patterns**: Review advanced examples
3. **Profile code**: Identify bottlenecks
4. **Optimize**: Apply advanced techniques
5. **Monitor**: Track production performance

## 🚀 Next Steps

- **Build pipelines**: Create end-to-end workflows
- **Optimize performance**: Profile and tune
- **Add monitoring**: Track production systems
- **Scale up**: Handle larger datasets
- **Contribute**: Share your patterns!
