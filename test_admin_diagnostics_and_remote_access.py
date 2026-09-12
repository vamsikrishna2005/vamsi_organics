import unittest
import os
import json
from app import app, SYSTEM_ERROR_LOGS

class TestAdminDiagnosticsAndRemoteAccess(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_diagnostics_auth_protection(self):
        """Ensure guest and customer users cannot access diagnostics"""
        res_guest = self.client.get('/admin/diagnostics')
        self.assertEqual(res_guest.status_code, 302)
        self.assertIn('/admin/login', res_guest.headers.get('Location'))

        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['role'] = 'customer'
        res_cust = self.client.get('/admin/diagnostics')
        self.assertEqual(res_cust.status_code, 302)

    def test_02_diagnostics_admin_access(self):
        """Ensure admin can access diagnostics dashboard and inspect metrics"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 5
            sess['role'] = 'admin'
            sess['name'] = 'Store Manager (Admin)'

        res = self.client.get('/admin/diagnostics')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("System Health & Error Diagnostics", html)
        self.assertIn("Database Size", html)
        self.assertIn("Backup Database", html)

    def test_03_self_test_api(self):
        """Verify automated health check endpoint"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 5
            sess['role'] = 'admin'

        res = self.client.post('/admin/api/self-test')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        checks = data.get('checks', [])
        self.assertGreaterEqual(len(checks), 4)
        for check in checks:
            self.assertTrue(check.get('passed'), f"Check {check.get('name')} failed: {check.get('details')}")

    def test_04_database_backup_download(self):
        """Verify 1-click SQLite database download endpoint"""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 5
            sess['role'] = 'admin'

        res = self.client.get('/admin/backup-db')
        self.assertEqual(res.status_code, 200)
        self.assertIn('attachment', res.headers.get('Content-Disposition', ''))
        self.assertIn('.db', res.headers.get('Content-Disposition', ''))

    def test_05_error_logging_and_clear(self):
        """Verify error logging and clear logs endpoint"""
        SYSTEM_ERROR_LOGS.clear()
        SYSTEM_ERROR_LOGS.append({
            'id': 'TEST01',
            'timestamp': '2026-09-12 12:00:00',
            'path': '/api/test',
            'method': 'POST',
            'user': 'Test User',
            'error': 'Synthetic test exception',
            'trace': 'Traceback (most recent call last)...'
        })
        self.assertEqual(len(SYSTEM_ERROR_LOGS), 1)

        with self.client.session_transaction() as sess:
            sess['user_id'] = 5
            sess['role'] = 'admin'

        res_clear = self.client.post('/admin/api/clear-errors')
        self.assertEqual(res_clear.status_code, 200)
        self.assertEqual(len(SYSTEM_ERROR_LOGS), 0)

if __name__ == '__main__':
    unittest.main()
