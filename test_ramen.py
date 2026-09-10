"""Flask and real SQLite checks using temporary synthetic reviews only."""
from contextlib import closing
import csv
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.datastructures import MultiDict
import app as application
import functions as db

TOKEN = 'synthetic-admin-token-for-tests-only-0000'
AUTH = {'Authorization': 'Bearer ' + TOKEN}
ROWS = [('1', 'SG', "O'Brien", 'Miso 100%_\\ seaweed', 'Cup', '4'),
        ('2', 'JP', 'Brand B', 'Spicy ramen', 'Pack', '3'),
        ('3', 'SG', 'Brand C', '<script>window.__unsafe=1</script>', 'Cup', '5')]


class RamenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ramen-test-')
        self.addCleanup(self.tmp.cleanup)
        self.database = str(Path(self.tmp.name) / 'synthetic.db')
        self.csv = Path(self.tmp.name) / 'synthetic.csv'
        db.createone(self.database, 'Ratings')
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.executemany('INSERT INTO Ratings VALUES (?, ?, ?, ?, ?, ?)', ROWS)
        self.app = application.create_app({'TESTING': True, 'DATABASE': self.database,
                                          'CSV': str(self.csv), 'ADMIN_TOKEN': TOKEN})
        self.client = self.app.test_client()

    def count(self):
        with closing(sqlite3.connect(self.database)) as conn:
            return conn.execute('SELECT COUNT(*) FROM Ratings').fetchone()[0]

    def test_injection_filters_are_literal(self):
        for field, value in [('country', "XX' OR 1=1 --"), ('keyword', "x' OR 1=1 --"), ('brand', 'x" OR 1=1 --')]:
            with self.subTest(field=field):
                result = self.client.get('/api/searchsome', query_string={field: value})
                self.assertEqual((result.status_code, result.json['items']), (200, []))
        self.assertEqual(self.count(), 3)

    def test_quotes_unicode_case_and_single_field_insert(self):
        row = {'ID': '4', 'Brand': '日本 O\'Brien "Special"', 'Country': 'sG'}
        self.assertEqual(self.client.post('/api/addone', json=row, headers=AUTH).status_code, 201)
        found = self.client.get('/api/searchsome', query_string={'brand': row['Brand'], 'country': 'SG'}).json['items']
        self.assertEqual((len(found), found[0]['Brand'], found[0]['Country']), (1, row['Brand'], 'sG'))
        self.assertEqual(self.client.post('/api/addone', json={'ID': '5'}, headers=AUTH).status_code, 201)

    def test_keyword_metacharacters_are_literal(self):
        for keyword in ['%', '_', '\\']:
            with self.subTest(keyword=keyword):
                found = self.client.get('/api/searchsome', query_string={'keyword': keyword}).json['items']
                # The escaped-script fixture also contains a literal underscore.
                self.assertEqual([row['ID'] for row in found], ['1', '3'] if keyword == '_' else ['1'])

    def test_get_and_head_cannot_mutate(self):
        for endpoint in ['createone', 'addone', 'addmany', 'editsome', 'deletesome', 'deleteall']:
            for method in ['GET', 'HEAD']:
                with self.subTest(endpoint=endpoint, method=method):
                    self.assertEqual(self.client.open('/api/' + endpoint, method=method, headers=AUTH).status_code, 405)
        self.assertEqual(self.count(), 3)

    def test_all_writes_require_bearer_auth(self):
        for method, endpoint in [('POST', 'createone'), ('PUT', 'addone'), ('POST', 'addmany'), ('PUT', 'editsome'), ('DELETE', 'deletesome'), ('DELETE', 'deleteall')]:
            for headers in [{}, {'Authorization': 'Bearer wrong'}, {'Cookie': 'token=' + TOKEN}]:
                with self.subTest(endpoint=endpoint, headers=bool(headers)):
                    self.assertEqual(self.client.open('/api/' + endpoint, method=method, headers=headers, json={'ID': '1'}).status_code, 401)
        self.assertEqual(self.count(), 3)

    def test_unconfigured_writes_fail_closed_and_reads_work(self):
        for token in ['', 'too-short', None]:
            self.app.config['ADMIN_TOKEN'] = token
            self.assertEqual(self.client.delete('/api/deleteall', headers=AUTH).status_code, 503)
            self.assertEqual(self.client.get('/api/selectall').status_code, 200)
        self.assertEqual(self.count(), 3)

    def test_bulk_delete_requires_confirmation(self):
        self.assertEqual(self.client.delete('/api/deleteall', headers=AUTH).status_code, 400)
        self.assertEqual(self.count(), 3)
        result = self.client.delete('/api/deleteall', headers={**AUTH, 'X-Confirm-Delete': 'all-reviews'})
        self.assertEqual((result.status_code, result.json['affected'], self.count()), (200, 3, 0))

    def test_failed_delete_returns_failure_without_private_details(self):
        with patch.object(db, 'deleteall', side_effect=sqlite3.OperationalError('synthetic private error')):
            result = self.client.delete('/api/deleteall', headers={**AUTH, 'X-Confirm-Delete': 'all-reviews'})
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('synthetic private error', result.text)
        self.assertEqual(self.count(), 3)

    def test_invalid_filters_cannot_broaden_deletes(self):
        for payload in [{}, {'wrong': 'x'}, {'ID': '1', 'wrong': 'x'}, {'ID': None}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.delete('/api/deletesome', json=payload, headers=AUTH).status_code, 400)
        self.assertEqual(self.count(), 3)

    def test_delete_injection_is_literal_and_legacy_put_works(self):
        result = self.client.delete('/api/deletesome', json={'country': 'x" OR 1=1 --'}, headers=AUTH)
        self.assertEqual((result.status_code, self.count()), (404, 3))
        result = self.client.put('/api/deletesome', data={'ID': '2'}, headers=AUTH)
        self.assertEqual((result.status_code, result.json['affected'], self.count()), (200, 1, 2))

    def test_update_by_id_stores_literal_text(self):
        value = 'new", Rating="0" --'
        result = self.client.put('/api/editsome', json={'ID': '1', 'updatebrand': value}, headers=AUTH)
        self.assertEqual((result.status_code, result.json['affected']), (200, 1))
        rows = db.selectall(self.database, 'Ratings')
        self.assertEqual((rows[0]['Brand'], rows[0]['Rating'], rows[1]['Brand']), (value, '4', 'Brand B'))

    def test_update_requires_filters_and_assignments(self):
        for payload in [{'ID': '1'}, {'updatebrand': 'new'}, {'ID': '1', 'updateid': '4'}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.put('/api/editsome', json=payload, headers=AUTH).status_code, 400)
        self.assertEqual(self.count(), 3)

    def test_duplicate_form_json_and_case_fields_are_rejected(self):
        for payload in [MultiDict([('ID', '1'), ('ID', '2')]), {'ID': '1', 'id': '2'}]:
            self.assertEqual(self.client.put('/api/deletesome', data=payload, headers=AUTH).status_code, 400)
        result = self.client.delete('/api/deletesome', data='{"ID":"1","ID":"2"}', content_type='application/json', headers=AUTH)
        self.assertEqual((result.status_code, self.count()), (400, 3))

    def test_invalid_sort_and_duplicate_query_fields(self):
        for query in [{'sortby': 'ID; DROP TABLE Ratings'}, MultiDict([('limit', '1'), ('limit', '2')])]:
            self.assertEqual(self.client.get('/api/selectall', query_string=query).status_code, 400)
        self.assertEqual(self.client.get('/api/searchsome?ID=1&sortby=ID&Sortby=Country').status_code, 400)

    def test_pagination_is_bounded_and_stable(self):
        first = self.client.get('/api/selectall?limit=2').json
        second = self.client.get('/api/selectall?limit=2&offset=2').json
        self.assertEqual([r['ID'] for r in first['items'] + second['items']], ['1', '2', '3'])
        self.assertEqual((first['has_more'], first['next_offset'], second['has_more'], second['next_offset']), (True, 2, False, None))
        for query in ['limit=0', 'limit=-1', 'limit=201', 'limit=1.5', 'limit=true', 'offset=100001']:
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/api/selectall?' + query).status_code, 400)

    def test_default_page_is_bounded(self):
        with closing(sqlite3.connect(self.database)) as conn, conn:
            conn.executemany('INSERT INTO Ratings (ID) VALUES (?)', [(str(i),) for i in range(100, 200)])
        result = self.client.get('/api/selectall').json
        self.assertEqual((len(result['items']), result['has_more']), (50, True))

    def test_legacy_search_returns_structured_json(self):
        result = self.client.put('/api/searchsome', data={'country': 'sg', 'Sortby': 'ID'})
        self.assertEqual(result.status_code, 200)
        self.assertIsInstance(result.json, dict)
        self.assertEqual([r['ID'] for r in result.json['items']], ['1', '3'])

    def test_create_preserves_records(self):
        self.assertEqual(self.client.post('/api/createone', headers=AUTH).status_code, 200)
        self.assertEqual(self.count(), 3)

    def write_csv(self, rows):
        with self.csv.open('w', encoding='utf-8', newline='') as target:
            writer = csv.writer(target)
            writer.writerow(db.COLUMNS)
            writer.writerows(rows)

    def test_csv_import_and_partial_failure_rollback(self):
        self.write_csv([('4', 'SG', 'Fresh', 'Soup', 'Cup', '4')])
        result = self.client.post('/api/addmany', headers=AUTH)
        self.assertEqual((result.status_code, result.json['affected'], self.count()), (201, 1, 4))
        self.write_csv([('5', 'SG', 'Fresh', 'Soup', 'Cup', '4'), ('6', 'SG')])
        self.assertEqual(self.client.post('/api/addmany', headers=AUTH).status_code, 400)
        self.assertEqual(self.count(), 4)

    def test_bad_csv_headers_size_and_encoding(self):
        for content in [b'ID,Country,Brand,Type,Package,Package\n', b'\xff\xfe\x00']:
            self.csv.write_bytes(content)
            self.assertEqual(self.client.post('/api/addmany', headers=AUTH).status_code, 400)
        with self.csv.open('wb') as target:
            target.truncate(8 * 1024 * 1024 + 1)
        self.assertEqual(self.client.post('/api/addmany', headers=AUTH).status_code, 400)
        self.assertEqual(self.count(), 3)

    def test_connections_close_after_success_and_errors(self):
        original, connections = sqlite3.connect, []
        def tracked(*args, **kwargs):
            conn = original(*args, **kwargs)
            connections.append(conn)
            return conn
        empty = str(Path(self.tmp.name) / 'empty.db')
        with closing(original(empty)):
            pass
        with patch.object(sqlite3, 'connect', side_effect=tracked):
            db.selectall(self.database, 'Ratings')
            with self.assertRaises(sqlite3.OperationalError):
                db.selectall(empty, 'Ratings')
        for conn in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute('SELECT 1')

    def test_missing_database_read_does_not_create_file(self):
        missing = Path(self.tmp.name) / 'missing.db'
        self.app.config['DATABASE'] = str(missing)
        self.assertEqual(self.client.get('/api/selectall').status_code, 503)
        self.assertFalse(missing.exists())

    def test_locked_database_returns_failure_without_deleting(self):
        with closing(sqlite3.connect(self.database)) as conn:
            conn.execute('BEGIN EXCLUSIVE')
            result = self.client.delete('/api/deleteall', headers={**AUTH, 'X-Confirm-Delete': 'all-reviews'})
            self.assertEqual(result.status_code, 503)
            conn.rollback()
        self.assertEqual(self.count(), 3)

    def test_bad_payloads_and_request_limits(self):
        for data in ['[]', 'null', '{', '{"ID":null}', '{"ID":{}}']:
            self.assertEqual(self.client.post('/api/addone', data=data, content_type='application/json', headers=AUTH).status_code, 400)
        self.assertEqual(self.client.post('/api/addone', json={'Type': 'x' * 4097}, headers=AUTH).status_code, 400)
        self.assertEqual(self.client.post('/api/addone', data='x' * 33000, content_type='application/json', headers=AUTH).status_code, 413)

    def test_sql_identifiers_are_allowlisted(self):
        with self.assertRaises(db.ValidationError):
            db.selectall(self.database, 'Ratings; DROP TABLE Ratings')
        with self.assertRaises(db.ValidationError):
            db.insertone(self.database, 'Ratings', {'ID) VALUES(1); --': 'x'})
        self.assertEqual(self.count(), 3)

    def test_pages_and_html_escaping(self):
        for route in ['/', '/help', '/documentation', '/display']:
            with self.subTest(route=route):
                result = self.client.get(route)
                self.assertEqual(result.status_code, 200)
                self.assertIn('The Prawn Projects', result.text)
        result = self.client.get('/display')
        self.assertNotIn('<script>window.__unsafe', result.text)
        self.assertIn('&lt;script&gt;window.__unsafe', result.text)
        self.assertIn('No reviews match.', self.client.get('/display?brand=Absent').text)

    def test_page_links_preserve_filters(self):
        result = self.client.get('/display?country=SG&limit=1')
        self.assertIn('country=SG&amp;limit=1&amp;offset=1', result.text)
        self.assertIn('Next page', result.text)

    def test_entry_points_share_app_without_opening_storage(self):
        with patch.object(sqlite3, 'connect', side_effect=AssertionError('Import must not access data')):
            import main
            self.assertIs(main.app, application.app)
            application.create_app({'DATABASE': 'missing.db'})
        self.assertFalse(application.app.debug)

    def test_response_headers(self):
        result = self.client.get('/api/selectall')
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertEqual(result.headers['X-Content-Type-Options'], 'nosniff')
        self.assertIn("script-src 'none'", result.headers['Content-Security-Policy'])
        self.assertNotIn('Access-Control-Allow-Origin', result.headers)
        with self.client.get('/static/css/prawn.css') as asset:
            self.assertIn('max-age=3600', asset.headers['Cache-Control'])

    def test_identifier_filters_do_not_merge_case_distinct_ids(self):
        for identifier in ['a', 'A']:
            db.insertone(self.database, 'Ratings', {'ID': identifier, 'Brand': 'Case fixture'})
        result = self.client.get('/api/searchsome', query_string={'ID': 'a'}).json['items']
        self.assertEqual([row['ID'] for row in result], ['a'])
        changed = self.client.put('/api/editsome', json={'ID': 'a', 'updaterating': '1'}, headers=AUTH)
        self.assertEqual(changed.json['affected'], 1)
        result = self.client.delete('/api/deletesome', json={'ID': 'a'}, headers=AUTH)
        self.assertEqual(result.json['affected'], 1)
        self.assertEqual([row['ID'] for row in self.client.get('/api/searchsome?ID=A').json['items']], ['A'])

    def test_unicode_text_filters_preserve_legacy_case_matching(self):
        # The old helpers capitalized these values before storage and filtering.
        db.insertone(self.database, 'Ratings', {'ID': 'u', 'Brand': 'Äbc', 'Country': 'CÔTE', 'Type': 'Äpfel noodles'})
        result = self.client.get('/api/searchsome', query_string={'brand': 'äbc', 'country': 'côte', 'keyword': 'äpfel'}).json['items']
        self.assertEqual([row['ID'] for row in result], ['u'])
        result = self.client.put('/api/editsome', json={'brand': 'äbc', 'updaterating': 'Unrated'}, headers=AUTH)
        self.assertEqual(result.json['affected'], 1)
        # Ratings, like IDs, retain exact text matching.
        self.assertEqual(self.client.get('/api/searchsome?rating=unrated').json['items'], [])


if __name__ == '__main__':
    unittest.main()
