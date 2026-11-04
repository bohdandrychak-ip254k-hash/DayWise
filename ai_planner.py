"""Lightweight illustrative ML classifier + transparent scheduling logic."""
import re
from datetime import datetime, timedelta
from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression

# Small illustrative examples: this model is a real trained text classifier, not a GPT API.
TRAINING = {
    'high': [
        'терміново здати звіт', 'дедлайн сьогодні надіслати проєкт', 'важливий іспит',
        'підготуватися до контрольної', 'зустріч з лікарем', 'оплатити рахунок сьогодні',
        'зробити домашнє завдання до завтра', 'важливий дзвінок клієнту',
        'urgent submit report', 'exam tomorrow', 'pay bill today', 'finish deadline task',
        'потрібно негайно виправити помилку', 'захист лабораторної завтра',
        'робоча презентація до вечора', 'запис до стоматолога'
    ],
    'medium': [
        'прибрати кімнату', 'придбати продукти', 'виконати вправи',
        'попрацювати над проєктом', 'відповісти на листи', 'прання речей',
        'приготувати обід', 'потренуватися', 'повторити матеріал',
        'buy groceries', 'clean room', 'work on project', 'reply to emails',
        'зателефонувати другу', 'прочитати конспект', 'зробити покупки'
    ],
    'low': [
        'подивитися серіал', 'пограти у гру', 'послухати музику',
        'прогулянка у парку', 'подивитися відео', 'відпочити',
        'почитати роман', 'соціальні мережі', 'пограти на компютері',
        'watch series', 'play video games', 'listen to music', 'relax',
        'переглянути меми', 'пошукати новий фільм', 'почитати новини'
    ]
}

@lru_cache(maxsize=1)
def model():
    texts = [s for samples in TRAINING.values() for s in samples]
    classes = [label for label, samples in TRAINING.items() for _ in samples]
    # Char ngrams tolerate Ukrainian inflection and short user entries.
    pipeline = make_pipeline(
        TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 5), min_df=1),
        LogisticRegression(max_iter=1000, random_state=42)
    )
    pipeline.fit(texts, classes)
    return pipeline

DUR_RE = re.compile(r'(\d{1,3})\s*(хв(?:илин[иа]?|\.)?|min(?:utes?)?|год(?:ин[аи]?|\.)?|hours?|h)\b', re.I)
CLOCK_RE = re.compile(r'(?:\bо\s*|\bat\s*)([01]?\d|2[0-3]):([0-5]\d)\b', re.I)
PRIORITY_WORDS = {
    'high': ('терміново', 'дедлайн', 'сьогодні до', 'завтра', 'іспит', 'негайно', 'urgent', 'deadline'),
    'low': ('відпочити', 'пограти', 'серіал', 'relax', 'game')
}

def parse_tasks(description):
    lines = re.split(r'[\n;]+', description)
    tasks = []
    for raw in lines:
        raw = re.sub(r'^\s*(?:[-•*]|\d+[.)])\s*', '', raw).strip()
        if not raw:
            continue
        raw = raw[:160]
        duration_match = DUR_RE.search(raw)
        duration = 45
        if duration_match:
            duration = int(duration_match.group(1))
            if duration_match.group(2).lower().startswith(('год', 'hour')) or duration_match.group(2).lower() == 'h':
                duration *= 60
        duration = min(max(duration, 10), 240)
        tm = CLOCK_RE.search(raw)
        fixed = f'{int(tm.group(1)):02d}:{tm.group(2)}' if tm else None
        cls = model().predict([raw])[0]
        lower = raw.lower()
        if any(x in lower for x in PRIORITY_WORDS['high']):
            cls = 'high'
        elif any(x in lower for x in PRIORITY_WORDS['low']):
            cls = 'low'
        tasks.append({'title': raw, 'duration': duration, 'priority': cls, 'fixed': fixed})
    return tasks[:20]

def create_schedule(description, date_str, start='09:00', end='21:00', pause=10):
    day = datetime.strptime(date_str, '%Y-%m-%d')
    begin = datetime.combine(day.date(), datetime.strptime(start, '%H:%M').time())
    finish = datetime.combine(day.date(), datetime.strptime(end, '%H:%M').time())
    if begin >= finish:
        raise ValueError('Початок дня має бути раніше завершення.')
    tasks = parse_tasks(description)
    if not tasks:
        raise ValueError('Додайте хоча б одне завдання.')
    if len(re.split(r'[\n;]+', description)) > 20:
        raise ValueError('Максимум 20 завдань.')

    # Reserve timed appointments first; fill the remaining free gaps by priority.
    busy, scheduled, skipped = [], [], []
    def place(task, at):
        until = at + timedelta(minutes=task['duration'])
        if at < begin or until > finish or any(at < b and until > a for a, b in busy):
            return False
        busy.append((at, until))
        scheduled.append({**task, 'start': at.isoformat(timespec='minutes'), 'end': until.isoformat(timespec='minutes')})
        return True

    fixed = [t for t in tasks if t['fixed']]
    flexible = [t for t in tasks if not t['fixed']]
    for task in sorted(fixed, key=lambda x: x['fixed']):
        at = datetime.combine(day.date(), datetime.strptime(task['fixed'], '%H:%M').time())
        if not place(task, at):
            skipped.append({**task, 'reason': 'Фіксований час зайнятий або поза межами дня'})

    order = {'high': 0, 'medium': 1, 'low': 2}
    flexible.sort(key=lambda t: order[t['priority']])
    cursor = begin
    for task in flexible:
        candidate = cursor
        while candidate + timedelta(minutes=task['duration']) <= finish:
            conflict = next(((a, b) for a, b in sorted(busy) if candidate < b and candidate + timedelta(minutes=task['duration']) > a), None)
            if conflict:
                candidate = conflict[1] + timedelta(minutes=pause)
                continue
            break
        if place(task, candidate):
            cursor = candidate + timedelta(minutes=task['duration'] + pause)
        else:
            skipped.append({**task, 'reason': 'Недостатньо вільного часу'})
    scheduled.sort(key=lambda t: t['start'])
    return {'tasks': scheduled, 'skipped': skipped, 'count': len(tasks), 'scheduled_count': len(scheduled), 'total_minutes': sum(t['duration'] for t in scheduled)}
