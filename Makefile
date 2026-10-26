.PHONY: test eval seed bench lint help

help:
	@echo "Available commands:"
	@echo "  make test   - Run all pytest unit and security tests"
	@echo "  make seed   - Seed evaluation corpus into PostgreSQL"
	@echo "  make eval   - Run full golden set evaluation harness"
	@echo "  make bench  - Run streaming TTFT latency benchmark"

test:
	python -m pytest -v

seed:
	python eval/seed_eval_corpus.py

eval:
	python eval/run_eval.py

bench:
	python eval/bench_ttft.py
