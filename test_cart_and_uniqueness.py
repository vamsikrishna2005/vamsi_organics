import unittest
import json
from app import app
from database import init_db, get_db_connection

class TestCartAndUniqueness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_cart_route_requires_login(self):
        """Verify unauthenticated user cannot access /cart and is redirected to /login."""
        self.app.get('/logout')
        res = self.app.get('/cart', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])

    def test_02_authenticated_customer_can_access_cart_page(self):
        """Verify logged-in customer loads dedicated standalone /cart page successfully."""
        # Login as customer Vamsi Vegi
        login_res = self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # Access /cart
        res = self.app.get('/cart')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Your Farm Basket", html)
        self.assertIn("Delivery Address", html)
        self.assertIn("Delivery Schedule", html)
        self.assertIn("Promo Coupon", html)
        self.assertIn("Redeem Farm Wallet Coins", html)
        self.assertIn("Proceed to Express Checkout", html)

    def test_03_registration_duplicate_phone_rejected(self):
        """Verify that registering with an already existing mobile number is rejected."""
        self.app.get('/logout')
        res = self.app.post('/register', data={
            'name': 'Duplicate Phone User',
            'email': 'brandnewemail@example.com',
            'phone': '8888888888' # Already registered to Vamsi Vegi
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertTrue("already registered" in html.lower())

    def test_04_registration_duplicate_email_rejected_case_insensitive(self):
        """Verify that registering with an already existing email (case-insensitive) is rejected."""
        self.app.get('/logout')
        res = self.app.post('/register', data={
            'name': 'Duplicate Email User',
            'email': 'VAMSI@EXAMPLE.COM', # Already registered in lowercase
            'phone': '9876543211'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertTrue("already registered" in html.lower())

    def test_05_registration_with_unique_credentials_succeeds(self):
        """Verify that a brand new customer with unique phone & email registers and receives ₹100 coins."""
        self.app.get('/logout')
        unique_phone = "9812345678"
        unique_email = "freshbuyer.unique@example.com"
        res = self.app.post('/register', data={
            'name': 'Priya Fresh',
            'email': unique_email,
            'phone': unique_phone
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Registration successful", html)

        # Verify customer can log in with new phone
        login_res = self.app.post('/login', data={
            'login_type': 'customer',
            'phone': unique_phone
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # Verify wallet balance initialized to 100.0
        wallet_res = self.app.get('/api/user/wallet')
        self.assertEqual(wallet_res.status_code, 200)
        wdata = wallet_res.get_json()
        self.assertEqual(wdata['balance'], 100.0)

    def test_06_check_user_unique_api(self):
        """Verify the real-time credential uniqueness validation API."""
        # Existing phone check
        p_res = self.app.get('/api/check-user-unique?phone=8888888888')
        self.assertEqual(p_res.status_code, 200)
        p_data = p_res.get_json()
        self.assertFalse(p_data['phone_available'])

        # Available phone check
        p_new_res = self.app.get('/api/check-user-unique?phone=9991112233')
        self.assertEqual(p_new_res.status_code, 200)
        self.assertTrue(p_new_res.get_json()['phone_available'])

        # Existing email check
        e_res = self.app.get('/api/check-user-unique?email=vamsi@example.com')
        self.assertEqual(e_res.status_code, 200)
        self.assertFalse(e_res.get_json()['email_available'])

        # Available email check
        e_new_res = self.app.get('/api/check-user-unique?email=fresh.produce.buyer@example.com')
        self.assertEqual(e_new_res.status_code, 200)
        self.assertTrue(e_new_res.get_json()['email_available'])

    def test_07_order_triggers_admin_real_time_alert(self):
        """Verify placing an order generates real-time notifications for the store admin."""
        # 1. Customer login & checkout
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        order_res = self.app.post('/api/checkout', json={
            "items": [{"product_id": 1, "quantity": 1}],
            "delivery_date": "2026-09-08",
            "delivery_slot": "Morning (8:00 AM - 11:00 AM)",
            "delivery_address": "Villa 14, Palm Meadows, Gachibowli, Hyderabad"
        })
        self.assertEqual(order_res.status_code, 200)
        order_id = order_res.get_json()['order_id']

        # 2. Admin polls live order notification endpoint
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        poll_res = self.app.get('/api/admin/live-order-poll')
        self.assertEqual(poll_res.status_code, 200)
        poll_data = poll_res.get_json()
        self.assertTrue(poll_data['success'])
        self.assertTrue(poll_data['has_new_orders'])
        self.assertGreater(len(poll_data['notifications']), 0)
        self.assertIn(order_id, poll_data['notifications'][0]['message'])

    def test_08_landing_page_serves_storefront(self):
        """Verify visiting the root URL / serves the public farm storefront (200 OK) for SEO."""
        self.app.get('/logout')
        res = self.app.get('/', follow_redirects=False)
        self.assertEqual(res.status_code, 200)
        self.assertIn("PPM Organic Farms", res.data.decode('utf-8'))

    def test_09_customer_login_redirects_to_dashboard(self):
        """Verify successful customer login redirects to unified /dashboard."""
        res = self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dashboard', res.headers['Location'])

    def test_10_store_js_syntax_clean(self):
        """Verify that store.js has no JS syntax errors and parses cleanly."""
        import subprocess
        result = subprocess.run(["node", "-c", "static/js/store.js"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"store.js syntax error: {result.stderr}")

    def test_11_login_page_hides_admin_login_from_users(self):
        """Verify that the public login page does NOT show the Store Admin tab or admin login form."""
        res = self.app.get('/login')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        # Store Admin tab button and form should not exist on public login
        self.assertNotIn("tab-btn-admin", html)
        self.assertNotIn("id=\"admin-login-section\"", html)
        self.assertIn("Customer Login", html)
        self.assertIn("New Customer Register", html)

    def test_12_admin_login_portal_handles_authentication(self):
        """Verify that /admin/login serves dedicated admin portal and logs in admin."""
        self.app.get('/logout')
        res = self.app.get('/admin/login')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertTrue("Store Manager" in html or "Farm Operations" in html)
        self.assertTrue("Manager Username" in html or "Admin Username" in html)

        # Submit valid credentials
        post_res = self.app.post('/admin/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
        self.assertEqual(post_res.status_code, 302)
        self.assertIn('/admin', post_res.headers['Location'])

    def test_13_unauthenticated_admin_redirects_to_admin_login(self):
        """Verify that accessing /admin without admin session redirects to /admin/login."""
        self.app.get('/logout')
        res = self.app.get('/admin', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login', res.headers['Location'])

if __name__ == '__main__':
    unittest.main()

