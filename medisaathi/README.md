# MediSaathi (working title)

Scan your prescription once, and know exactly what to take, how much to buy,
where it is cheapest, and when you will run out.

Built for Tech Eximius 2.0 (Tech Circle).

> Reminder and information tool, not medical advice. Price data is sample data
> collected by hand.

## Run locally
```
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # then add your keys
streamlit run app.py
```

## Layout
| File | Owner |
|---|---|
| app.py, schedule.py, reminders.py | Person 3 |
| reader.py, assistant.py, strip.py | Person 1 |
| matcher.py, pricing.py, data/ | Person 2 |

## Credits
(Libraries, APIs and datasets are listed here before submission.)
