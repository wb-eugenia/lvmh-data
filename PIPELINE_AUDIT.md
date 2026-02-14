# Pipeline Audit Report

## Overview

The LVMH Voice-to-Tag pipeline has **3 runtime profiles** and a **multi-tier processing architecture**.

---

## Current Pipeline Modes

### 1. Runtime Profiles

| Profile | Use Case | Timeout | RAG | Cache | Quality Gate |
|---------|----------|---------|-----|-------|--------------|
| `single_note` | Real-time API | 25s | k=2, thr=0.42 | Yes | Strict |
| `batch_csv` | Batch processing | 90s | k=5, thr=0.30 | Yes | Moderate |
| `fast_batch` | Speed priority | 20s | k=1, thr=1.0 | No | None |

### 2. Processing Tiers

```
Note → [Smart Router] → Tier Selection
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
        Tier 1          Tier 2          Tier 3
     (Regex Rules)    (Mistral)       (GPT-4)
        ~50ms           ~3s            ~5s
        €0.0000         €0.0001        €0.005
```

- **Tier 1**: Simple regex rules for straightforward notes
- **Tier 2**: Mistral AI for medium complexity
- **Tier 3**: GPT-4 for complex, high-value notes

---

## Issues Found

### High Priority

| Issue | Location | Impact |
|-------|----------|--------|
| No profile-specific routing | Smart Router | Wrong tier selection |
| Hardcoded RGPD markers | `pipeline_async.py:61-74` | Inflexible |
| Synchronous cache I/O | `cache_manager.py` | Blocks event loop |
| No retry on Tier 2 timeout | `tier2_mistral.py` | Lost notes |
| No circuit breaker | Pipeline | Cascade failures |

### Medium Priority

| Issue | Location | Impact |
|-------|----------|--------|
| Memory accumulation | Profile stats | Memory leak over time |
| No input validation | `process_note` | Garbage in = garbage out |
| Duplicate RGPD logic | `_build_heuristic_rgpd` | Code duplication |
| Verbose logging in prod | Multiple files | Log bloat |

### Low Priority

| Issue | Location | Impact |
|-------|----------|--------|
| No metrics export | Pipeline | No observability |
| Missing type hints | Several files | Poor IDE support |
| Magic numbers | Config | Hard to tune |

---

## Recommendations

### Phase 1: Quick Wins (1-2 days)

```python
# 1. Add circuit breaker for external APIs
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = "closed"
    
    async def call(self, func):
        if self.state == "open":
            raise CircuitOpenError()
        try:
            return await func()
        except Exception as e:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                asyncio.create_task(self._reset_after_timeout())

# 2. Add input validation
def validate_note(note: Dict) -> bool:
    if not note.get('Transcription'):
        return False
    if len(note['Transcription']) < 10:
        return False
    return True

# 3. Add profile-aware routing
def get_profile_for_note(text: str, profile: str) -> str:
    if profile == "fast_batch":
        return "tier1_only"  # Skip AI entirely
```

### Phase 2: Performance (1 week)

1. **Async cache I/O**
   - Replace `CacheManager` with async Redis-based cache
   - Add `cache_hit_rate` metrics per profile

2. **Profile-specific optimization**
   - `fast_batch`: Skip RGPD LLM, use heuristics only
   - `batch_csv`: Add parallel note processing
   - `single_note`: Pre-warm cache on startup

3. **Observability**
   - Add OpenTelemetry tracing
   - Export metrics to Prometheus
   - Structured logging with request IDs

### Phase 3: Architecture (2-4 weeks)

1. **Smart Tier Selection**
   - Train ML model to predict optimal tier
   - Features: text length, keywords, client history

2. **Tier 2 Improvements**
   - Add retry with exponential backoff
   - Implement fallback to cached results

3. **Dynamic Configuration**
   - Hot-reload profiles without restart
   - A/B testing for new profiles

---

## Feature Suggestions

| Feature | Priority | Benefit |
|---------|----------|---------|
| **Profile auto-selector** | High | Route notes to optimal profile |
| **Cost estimator** | High | Predict processing cost per note |
| **Graceful degradation** | Medium | Continue on partial failure |
| **Note similarity search** | Medium | Find similar past notes |
| **Real-time quality alerts** | Low | Monitor extraction quality |

---

## Performance Targets

| Metric | Current | Target |
|--------|---------|--------|
| Tier 1 latency | ~50ms | <30ms |
| Tier 2 latency | ~3000ms | <1500ms |
| Cache hit rate | ~20% | >50% |
| Fast batch throughput | ~100/hr | >500/hr |
| Cold start | ~10s | <3s |

---

## Action Items

- [ ] Add circuit breaker for Tier 2/3 calls
- [ ] Implement profile-aware RGPD processing
- [ ] Add async Redis cache
- [ ] Add OpenTelemetry tracing
- [ ] Create profile auto-selector ML model
- [ ] Add cost estimation endpoint
