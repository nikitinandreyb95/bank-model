# Bank Model · MX & CO

Streamlit финансовая модель: Mexico + Colombia, кредитный продукт, 2025–2029.

## Запуск локально
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Деплой на Streamlit Community Cloud (бесплатно)

1. Залить этот репозиторий на GitHub
2. Зайти на https://share.streamlit.io
3. New app → выбрать репо → указать `app.py`
4. Deploy → получить ссылку вида `yourapp.streamlit.app`

## Структура файлов
```
app.py                  — Streamlit UI (сайдбар, вкладки, графики)
model/
  assumptions.py        — все вводные (BASE + сценарные множители)
  engine.py             — расчётный движок (портфель, NII, P&L)
requirements.txt
```

## Как добавить продукт
1. В `assumptions.py` — добавить блок с параметрами нового продукта
2. В `engine.py` — расширить `run_model()` чтобы суммировал несколько продуктов
3. В `app.py` — добавить вкладку или раздел в сайдбаре
