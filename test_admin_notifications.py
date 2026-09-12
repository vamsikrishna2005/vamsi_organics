import unittest
from app import app
from database import init_db, get_db_connection

class TestAdminOrderNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_landing_page_redirect_to_login(self):
        """Verify that visitors landing on / or /shop without session are redirected to /login."""
        response = self.app.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

        response_shop = self.app.get('/shop', follow_redirects=False)
        self.assertEqual(response_shop.status_code, 302)
        self.assertIn('/login', response_shop.headers['Location'])

    def test_02_customer_order_triggers_admin_notification(self):
        """Verify that placing an order generates a real-time notification for admins."""
        # 1. Login as customer Vamsi Vegi (Phone 8888888888)
        login_res = self.app.post('/login', data={
            'login_type': 'customer',
            'phone': '8888888888'
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # 2. Customer places an order
        order_payload = {
            "items": [
                {"product_id": 1, "quantity": 2}, # Hybrid Tomatoes
                {"product_id": 2, "quantity": 1}  # Desi Red Onions
            ],
            "delivery_date": "2026-09-05",
            "delivery_slot": "Morning (8:00 AM - 11:00 AM)",
            "delivery_address": "Flat 301, Sri Sai Residency, Madhapur, Hyderabad"
        }
        checkout_res = self.app.post('/api/checkout', json=order_payload)
        self.assertEqual(checkout_res.status_code, 200)
        checkout_data = checkout_res.get_json()
        self.assertTrue(checkout_data['success'])
        order_id = checkout_data['order_id']
        self.assertTrue(order_id.startswith('VOF-'))

        # 3. Log out customer & Log in as Admin (admin / admin123)
        self.app.get('/logout')
        admin_login = self.app.post('/login', data={
            'login_type': 'admin',
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertEqual(admin_login.status_code, 200)

        # 4. Poll live orders endpoint as admin
        poll_res = self.app.get('/api/admin/live-order-poll')
        self.assertEqual(poll_res.status_code, 200)
        poll_data = poll_res.get_json()
        self.assertTrue(poll_data['success'])
        self.assertTrue(poll_data['has_new_orders'])
        self.assertGreater(len(poll_data['notifications']), 0)
        
        # Verify notification details
        notif = poll_data['notifications'][0]
        self.assertIn(order_id, notif['message'])
        self.assertEqual(poll_data['latest_order']['order_id'], order_id)
        self.assertEqual(poll_data['latest_order']['customer_name'], 'Vamsi Vegi')

        # 5. Dismiss notification
        dismiss_res = self.app.post('/api/admin/dismiss-order-alert', json={
            'notification_id': notif['id']
        })
        self.assertEqual(dismiss_res.status_code, 200)
        self.assertTrue(dismiss_res.get_json()['success'])

        # 6. Re-poll should show no unread alerts
        re_poll = self.app.get('/api/admin/live-order-poll')
        self.assertFalse(re_poll.get_json()['has_new_orders'])

if __name__ == '__main__':
    unittest.main()
