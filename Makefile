.PHONY: setup up down reset psql check-idempotent check-memory check-money

setup:
	pip install -r requirements.txt
	python scripts/prepare_data.py
	docker compose up -d
	@echo "Готово"

up:
	docker compose up -d

down:
	docker compose down

reset:            
	docker compose down -v && docker compose up -d
	@sleep 5

psql:
	docker compose exec db psql -U postgres -d taxi

check-idempotent:
	python etl.py --month 2024-01
	@docker compose exec -T db psql -U postgres -d taxi -tAc \
	  "select count(*), sum(total) from trips" > /tmp/a.txt
	python etl.py --month 2024-01
	@docker compose exec -T db psql -U postgres -d taxi -tAc \
	  "select count(*), sum(total) from trips" > /tmp/b.txt
	@diff /tmp/a.txt /tmp/b.txt && echo "IDEMPOTENT OK" || (echo "BROKEN"; exit 1)

check-memory:
	/usr/bin/time -v python etl.py --backfill 2024-01:2024-12 2>&1 \
	  | grep "Maximum resident set size"

check-money:
	@docker compose exec -T db psql -U postgres -d taxi -tAc \
	  "select sum(total) from trips where pickup >= '2024-02-01' and pickup < '2024-03-01'"
	@grep '^2024-02' expected/reference.csv | cut -d, -f3
	@echo "^ ці два числа мають збігтись. До копійки."
