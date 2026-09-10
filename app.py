"""Ramen Reviews app factory; no database work occurs during import/startup."""
from functools import wraps
import csv
import hmac
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlencode

from flask import Flask, current_app, jsonify, render_template, request, url_for
from werkzeug.exceptions import BadRequest, HTTPException
import functions as db


def _unique(values) -> dict:
    if any(len(items) != 1 for _, items in values.lists()):
        raise db.ValidationError('Supply each parameter only once.')
    return values.to_dict()


def _payload() -> dict:
    if request.is_json:
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise db.ValidationError('Supply each JSON field only once.')
                result[key] = value
            return result
        try:
            result = json.loads(request.get_data(), object_pairs_hook=unique_object)
        except (ValueError, UnicodeError) as error:
            if isinstance(error, db.ValidationError):
                raise
            raise BadRequest('Supply valid JSON.') from error
        if not isinstance(result, dict):
            raise db.ValidationError('Supply a JSON object.')
        return result
    return _unique(request.form)


def _admin(function):
    @wraps(function)
    def authorized(*args, **kwargs):
        token = current_app.config['ADMIN_TOKEN']
        if not isinstance(token, str) or len(token) < 32:
            return jsonify(error='Administrative writes are not configured.'), 503
        provided = request.headers.get('Authorization', '')
        if not hmac.compare_digest(provided.encode('utf-8'), ('Bearer ' + token).encode('utf-8')):
            return jsonify(error='A valid administrative bearer token is required.'), 401, {'WWW-Authenticate': 'Bearer'}
        return function(*args, **kwargs)
    return authorized


def create_app(config=None) -> Flask:
    app = Flask(__name__)
    root = Path(__file__).resolve().parent
    app.config.from_mapping(
        DATABASE=os.environ.get('RAMEN_DATABASE', str(root / 'ratings.db')),
        CSV=os.environ.get('RAMEN_CSV', str(root / 'ratings.csv')),
        ADMIN_TOKEN=os.environ.get('RAMEN_ADMIN_TOKEN', ''),
        MAX_CONTENT_LENGTH=32 * 1024,
        MAX_FORM_MEMORY_SIZE=32 * 1024,
        MAX_FORM_PARTS=20,
        SEND_FILE_MAX_AGE_DEFAULT=3600,
    )
    if config:
        app.config.update(config)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'none'; style-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(db.ValidationError)
    def validation(error):
        if request.path.startswith('/api/'):
            return jsonify(error=str(error)), 400
        return render_template('help.html', error=str(error)), 400

    @app.errorhandler(csv.Error)
    @app.errorhandler(UnicodeError)
    def invalid_csv(error):
        return jsonify(error='The configured CSV is not valid UTF-8 CSV data.'), 400

    @app.errorhandler(sqlite3.Error)
    @app.errorhandler(OSError)
    def unavailable(error):
        # Avoid logging request values, local paths or records from DB exceptions.
        app.logger.warning('Review storage unavailable: %s', type(error).__name__)
        message = 'Reviews are temporarily unavailable. Please try again later.'
        if request.path.startswith('/api/'):
            return jsonify(error=message), 503
        return render_template('help.html', error=message), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = error.get_response()
        if request.path.startswith('/api/'):
            response.data = app.json.dumps({'error': error.description})
            response.content_type = 'application/json'
        return response

    def page_data(values):
        values = dict(values)
        if 'sortby' in values and 'Sortby' in values:
            raise db.ValidationError('Supply the sort column only once.')
        limit = values.pop('limit', db.DEFAULT_LIMIT)
        offset = values.pop('offset', 0)
        sortby = values.pop('sortby', values.pop('Sortby', 'ID'))
        return db.read_page(app.config['DATABASE'], 'Ratings', values, sortby=sortby, limit=limit, offset=offset)

    @app.get('/api/selectall')
    def select_all():
        values = _unique(request.args)
        if set(values) - {'limit', 'offset', 'sortby'}:
            raise db.ValidationError('Use /api/searchsome to filter reviews.')
        return jsonify(page_data(values))

    @app.route('/api/searchsome', methods=['GET', 'PUT'])
    def search_some():
        values = _unique(request.args)
        if request.method == 'PUT':
            payload = _payload()
            if set(values) & set(payload):
                raise db.ValidationError('Supply each parameter only once.')
            values.update(payload)
        filters = {key: value for key, value in values.items() if key not in {'sortby', 'Sortby', 'limit', 'offset'}}
        if not filters:
            raise db.ValidationError('Supply at least one search filter.')
        return jsonify(page_data(values))

    @app.post('/api/createone')
    @_admin
    def create_one():
        db.createone(app.config['DATABASE'], 'Ratings')
        return jsonify(message='Review storage is ready.')

    @app.route('/api/addone', methods=['POST', 'PUT'])
    @_admin
    def add_one():
        count = db.insertone(app.config['DATABASE'], 'Ratings', _payload())
        return jsonify(message='Review added.', affected=count), 201

    @app.post('/api/addmany')
    @_admin
    def add_many():
        count = db.insertall(app.config['DATABASE'], app.config['CSV'])
        return jsonify(message='CSV import completed.', affected=count), 201

    @app.put('/api/editsome')
    @_admin
    def edit_some():
        count = db.updatesome(app.config['DATABASE'], 'Ratings', _payload())
        return jsonify(message='Reviews updated.' if count else 'No reviews matched.', affected=count), 200 if count else 404

    @app.route('/api/deletesome', methods=['DELETE', 'PUT'])
    @_admin
    def delete_some():
        count = db.deletesome(app.config['DATABASE'], 'Ratings', _payload())
        return jsonify(message='Reviews deleted.' if count else 'No reviews matched.', affected=count), 200 if count else 404

    @app.delete('/api/deleteall')
    @_admin
    def delete_all():
        if request.headers.get('X-Confirm-Delete') != 'all-reviews':
            raise db.ValidationError('Bulk deletion requires X-Confirm-Delete: all-reviews.')
        count = db.deleteall(app.config['DATABASE'], 'Ratings')
        return jsonify(message='Reviews deleted.', affected=count)

    @app.get('/')
    def home():
        return render_template('home.html')

    @app.get('/documentation')
    def docs():
        return render_template('documentation.html')

    @app.get('/help')
    def help_page():
        return render_template('help.html', error=None)

    @app.get('/display')
    def display():
        submitted = _unique(request.args)
        values = {key: value for key, value in submitted.items() if value != ''}
        result = page_data(values)
        def link(offset):
            return url_for('display') + '?' + urlencode({**values, 'offset': offset})
        return render_template('display.html', page=result, filters=values,
                               previous=link(max(0, result['offset'] - result['limit'])) if result['offset'] else None,
                               following=link(result['next_offset']) if result['next_offset'] is not None else None)

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=False)
