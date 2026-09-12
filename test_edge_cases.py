import unittest
from app import app
from database import init_db

class TestEdgeCasesAndBugFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_negative_and_zero_checkout_quantity_rejected(self):
        """Ensure invalid quantities (<= 0) are blocked by API."""
        # Log in as customer
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        
        # Zero quantity
        res_zero = self.app.post('/api/checkout', json={
            "items": [{"product_id": 1, "quantity": 0}]
        })
        self.assertEqual(res_zero.status_code, 400)
        self.assertFalse(res_zero.get_json()['success'])

        # Negative quantity
        res_neg = self.app.post('/api/checkout', json={
            "items": [{"product_id": 1, "quantity": -5}]
        })
        self.assertEqual(res_neg.status_code, 400)
        self.assertFalse(res_neg.get_json()['success'])

    def test_02_unauthorized_admin_restock_blocked(self):
        """Ensure non-admin users cannot trigger admin restock endpoint."""
        self.app.get('/logout')
        res = self.app.post('/api/admin/restock', json={"product_id": 1, "quantity": 10})
        self.assertEqual(res.status_code, 403)

    def test_03_duplicate_email_registration_handled_cleanly(self):
        """Ensure duplicate email registration is rejected with friendly flash message."""
        res = self.app.post('/register', data={
            'name': 'Duplicate Tester',
            'email': 'vamsi@example.com', # Existing email
            'phone': '9123456780'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"already registered", res.data)

    def test_04_cross_user_notification_dismissal_blocked(self):
        """Ensure unauthenticated user cannot dismiss notifications."""
        self.app.get('/logout')
        res = self.app.post('/api/notifications/dismiss/1')
        self.assertEqual(res.status_code, 401)

if __name__ == '__main__':
    unittest.main()
