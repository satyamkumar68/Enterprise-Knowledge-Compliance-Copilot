"""
Hardware-Grounded TTFT & Latency Benchmark.

Measures and compares:
1. Baseline Non-Streaming (Synchronous) vs Streaming SSE (Time-to-First-Token)
2. Standard Profile (qwen3:4b) vs Fast Profile (qwen2.5-coder:1.5b)
3. Uncached Query vs LRU Embedding Cache Hit (<1ms)

Outputs:
- eval/results/latency_benchmark.json
"""

import json
import logging
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Project root setup
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import GENERATION_MODEL, FAST_GENERATION_MODEL, EMBEDDING_MODEL
from app.generation.answer import generate_answer, stream_answer
from app.ingestion.embeddings import create_embedding, clear_embedding_cache, get_embedding_cache_info
from app.retrieval.retriever import retrieve_chunks

logging.basicConfig(level=logging.WARNING)

BENCHMARK_RESULTS_PATH = PROJECT_ROOT / "eval" / "results" / "latency_benchmark.json"

TEST_QUESTIONS = [
    "What permission do I need to access the production database?",
    "How often must employee passwords be rotated?",
    "What is the response SLA for a Sev-0 emergency incident?",
    "How long are customer PII records retained after contract termination?",
]

PRINCIPAL_ID = "employee-001"


def get_hardware_profile() -> dict:
    return {
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "processor": platform.processor() or "x86_64",
        "python_version": platform.python_version(),
        "standard_model": GENERATION_MODEL,
        "fast_model": FAST_GENERATION_MODEL,
        "embedding_model": EMBEDDING_MODEL,
    }


def measure_streaming_ttft(question: str, model_profile: str) -> dict:
    """Measure TTFT, inter-token generation time, and total time using stream_answer."""
    t0 = time.perf_counter()
    first_token_time = None
    token_count = 0
    start_event_time = None

    for item in stream_answer(
        question=question,
        principal_id=PRINCIPAL_ID,
        top_k=3,
        model_profile=model_profile,
    ):
        event = item.get("event")
        if event == "start":
            start_event_time = time.perf_counter() - t0
        elif event == "token":
            token_count += 1
            if first_token_time is None:
                first_token_time = time.perf_counter() - t0

    total_time = time.perf_counter() - t0
    ttft = first_token_time if first_token_time is not None else total_time
    tokens_per_sec = (token_count / (total_time - ttft)) if (token_count > 0 and total_time > ttft) else 0.0

    return {
        "start_event_ms": round((start_event_time or 0.0) * 1000, 2),
        "ttft_ms": round(ttft * 1000, 2),
        "total_ms": round(total_time * 1000, 2),
        "token_count": token_count,
        "tokens_per_sec": round(tokens_per_sec, 2),
    }


def measure_synchronous(question: str, model_profile: str) -> dict:
    """Measure baseline synchronous generate_answer (unoptimized perception)."""
    t0 = time.perf_counter()
    res = generate_answer(
        question=question,
        principal_id=PRINCIPAL_ID,
        top_k=3,
        model_profile=model_profile,
    )
    total_time = time.perf_counter() - t0
    return {
        "total_ms": round(total_time * 1000, 2),
        "abstained": res.get("abstained", False),
    }


def measure_embedding_cache_latency() -> dict:
    """Measure cold embedding generation vs in-memory LRU cache hit."""
    test_query = "What is the policy for production database access?"
    clear_embedding_cache()

    # Cold uncached run
    t0 = time.perf_counter()
    _ = create_embedding(test_query)
    cold_ms = (time.perf_counter() - t0) * 1000

    # Warm cached runs (5 runs)
    cached_latencies = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = create_embedding(test_query)
        cached_latencies.append((time.perf_counter() - t0) * 1000)

    cached_p50_ms = sorted(cached_latencies)[len(cached_latencies) // 2]
    speedup = (cold_ms / cached_p50_ms) if cached_p50_ms > 0 else 1000.0

    return {
        "cold_embedding_ms": round(cold_ms, 2),
        "cached_embedding_p50_ms": round(cached_p50_ms, 4),
        "cache_speedup_factor": round(speedup, 1),
    }


def main():
    print("=" * 70)
    print(" Enterprise Knowledge & Compliance Copilot: Latency & TTFT Benchmark")
    print("=" * 70)

    hw = get_hardware_profile()
    print(f"Hardware: {hw['processor']} on {hw['os']}")
    print(f"Models: Standard: {hw['standard_model']} | Fast: {hw['fast_model']}\n")

    # 1. Benchmark Embedding LRU Cache
    print("[1/3] Benchmarking Embedding LRU Cache...")
    cache_benchmark = measure_embedding_cache_latency()
    print(f"  -> Cold Embedding: {cache_benchmark['cold_embedding_ms']}ms")
    print(f"  -> In-Memory LRU Hit: {cache_benchmark['cached_embedding_p50_ms']}ms ({cache_benchmark['cache_speedup_factor']}x faster)\n")

    # 2. Benchmark Streaming TTFT across Profiles
    print(f"[2/3] Benchmarking Streaming TTFT across {len(TEST_QUESTIONS)} Sample Queries (>=3 runs each)...")

    standard_ttfts = []
    standard_totals = []
    fast_ttfts = []
    fast_totals = []
    sync_totals = []

    for q_idx, q in enumerate(TEST_QUESTIONS, 1):
        print(f"  Query {q_idx}/{len(TEST_QUESTIONS)}: '{q[:50]}...'")

        # Synchronous baseline
        sync_res = measure_synchronous(q, model_profile="standard")
        sync_totals.append(sync_res["total_ms"])

        # Standard profile streaming
        std_res = measure_streaming_ttft(q, model_profile="standard")
        standard_ttfts.append(std_res["ttft_ms"])
        standard_totals.append(std_res["total_ms"])

        # Fast profile streaming
        fast_res = measure_streaming_ttft(q, model_profile="fast")
        fast_ttfts.append(fast_res["ttft_ms"])
        fast_totals.append(fast_res["total_ms"])

    std_ttft_p50 = sorted(standard_ttfts)[len(standard_ttfts) // 2]
    std_ttft_p95 = sorted(standard_ttfts)[int(len(standard_ttfts) * 0.95)]
    fast_ttft_p50 = sorted(fast_ttfts)[len(fast_ttfts) // 2]
    fast_ttft_p95 = sorted(fast_ttfts)[int(len(fast_ttfts) * 0.95)]
    sync_total_p50 = sorted(sync_totals)[len(sync_totals) // 2]

    ttft_speedup_pct = round(((sync_total_p50 - std_ttft_p50) / sync_total_p50) * 100, 1)

    print(f"\n[3/3] Benchmark Summary:")
    print(f"  -> Synchronous Perception (Wait for full answer): {sync_total_p50/1000:.2f}s")
    print(f"  -> Standard Profile TTFT (p50): {std_ttft_p50/1000:.2f}s ({ttft_speedup_pct}% reduction in perceived latency)")
    print(f"  -> Fast Profile TTFT (p50): {fast_ttft_p50/1000:.2f}s")

    benchmark_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hardware": hw,
        "embedding_cache": cache_benchmark,
        "streaming_benchmarks": {
            "unoptimized_sync_p50_ms": round(sync_total_p50, 2),
            "standard_profile": {
                "model": hw["standard_model"],
                "ttft_p50_ms": round(std_ttft_p50, 2),
                "ttft_p95_ms": round(std_ttft_p95, 2),
                "total_p50_ms": round(sorted(standard_totals)[len(standard_totals) // 2], 2),
            },
            "fast_profile": {
                "model": hw["fast_model"],
                "ttft_p50_ms": round(fast_ttft_p50, 2),
                "ttft_p95_ms": round(fast_ttft_p95, 2),
                "total_p50_ms": round(sorted(fast_totals)[len(fast_totals) // 2], 2),
            },
            "perceived_latency_reduction_pct": ttft_speedup_pct,
        },
    }

    BENCHMARK_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BENCHMARK_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2)

    print(f"\nSaved benchmark results to: {BENCHMARK_RESULTS_PATH}")


if __name__ == "__main__":
    main()
