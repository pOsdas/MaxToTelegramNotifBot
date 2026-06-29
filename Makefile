.PHONY: setup build up down restart logs status test shell telegram-test chat-id inspect clean

setup:
	cp -n .env.example .env || true
	mkdir -p runtime/data runtime/browser-profile runtime/screenshots runtime/logs

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

restart:
	docker compose restart notifier

logs:
	docker compose logs -f --tail=200 notifier

status:
	docker compose ps
	docker stats --no-stream max-telegram-notifier || true

shell:
	docker compose exec notifier bash

test:
	docker compose run --rm notifier bash -lc "pip install -e '.[dev]' && pytest"

telegram-test:
	docker compose run --rm notifier python scripts/send_test_notification.py

chat-id:
	docker compose run --rm notifier python scripts/get_telegram_chat_id.py

inspect:
	-docker compose stop notifier
	-docker compose run --rm notifier python scripts/inspect_max_page.py
	-docker compose start notifier

clean:
	docker compose down --remove-orphans
	rm -rf runtime/screenshots/* runtime/logs/*
