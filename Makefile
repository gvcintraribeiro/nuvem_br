.PHONY: format format-check

format:
	uv run black .

format-check:
	uv run black --check .
