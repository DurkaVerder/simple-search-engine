# Simple Search Engine

Сервис поиска документов по тексту. Полные документы хранятся в PostgreSQL,
а полнотекстовый индекс — в Elasticsearch.


## Быстрый запуск

Склонируйте репозиторий и перейдите в его каталог:

```bash
git clone <repository-url>
cd simple-search-engine
```

Создайте локальный файл конфигурации из примера:

```bash
cp .env.example .env
```


При необходимости измените значения в `.env`.

Запустите постоянные сервисы:

```bash
docker compose up --build -d
```

Запуск поднимает:

- API;
- PostgreSQL;
- Elasticsearch.

Импортёр не запускается автоматически. После готовности сервисов выполните
импорт данных вручную:

```bash
docker compose run --rm importer
```

Импортёр прочитает `posts.csv`, сохранит документы в PostgreSQL и создаст
индекс `posts` в Elasticsearch. Повторный импорт безопасен: идентификаторы
генерируются детерминированно, а существующие записи обновляются.

## Адреса сервисов

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
- Elasticsearch: http://localhost:9200

## API

### Поиск

Возвращает не более 20 документов, найденных по полю `text`. Результаты
упорядочены по `created_date` от новых к старым.

```bash
curl "http://localhost:8000/search?q=конкурс"
```

### Удаление

Удаляет документ из PostgreSQL и Elasticsearch по UUID:

```bash
curl -X DELETE "http://localhost:8000/posts/<uuid>"
```

При временной недоступности Elasticsearch удаление повторяется три раза с
exponential backoff: через 1, 2 и 4 секунды. После четвёртой неудачной
попытки ошибка возвращается вызывающему коду.

### Проверка состояния

```bash
curl http://localhost:8000/health
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

## Локальная разработка

Создайте `.env` из `.env.example`, затем установите зависимости:

```bash
pip install -r requirements.txt
```

Запустите тесты:

```bash
pytest
```

Для запуска API локально PostgreSQL и Elasticsearch должны быть доступны по
адресам из `.env`.



