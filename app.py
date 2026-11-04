import os
from datetime import date, datetime
from flask import Flask, jsonify, render_template, request
from ai_planner import create_schedule

app = Flask(__name__)
app.json.ensure_ascii = False

@app.get('/')
def home():
    return render_template('index.html')

@app.get('/health')
def health():
    return jsonify(status='ok')

@app.post('/api/plan')
def plan():
    data = request.get_json(silent=True) or {}
    description = str(data.get('description', ''))
    if len(description) > 4000:
        return jsonify(error='Максимум 4000 символів.'), 400
    try:
        day = str(data.get('date', date.today().isoformat()))
        datetime.strptime(day, '%Y-%m-%d')
        result = create_schedule(description, day, str(data.get('start', '09:00')), str(data.get('end', '21:00')))
        return jsonify(result)
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
