web: gunicorn hotspot.wsgi:application --bind 0.0.0.0:$PORT --workers 2
worker: celery -A hotspot worker -l info
beat: celery -A hotspot beat -l info
