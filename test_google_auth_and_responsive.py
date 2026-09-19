import unittest
import json
from app import app
from database import init_db, get_db_connection

class TestGoogleAuthAndResponsive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_login_page_renders_firebase_google_auth_button(self):
        """Verify that the login page provides Firebase Google authentication."""
        res = self.app.get('/login')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Continue with Google", html)
        self.assertIn("firebase", html.lower())
        self.assertIn("handleGoogleSignIn", html)

    def test_02_auth_google_endpoint_accessible(self):
        """Verify /auth/google initiates flow or shows Google Account Chooser."""
        res = self.app.get('/auth/google')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Sign in with Google", html)
        self.assertIn("Vamsi Krishna", html)
        self.assertIn("vamsi.google@gmail.com", html)

    def test_03_google_demo_login_creates_new_user_with_wallet_coins(self):
        """Verify that Google OAuth demo sign-in creates a new user and credits 100 coins."""
        self.app.get('/logout')
        test_email = "new.google.customer@gmail.com"
        test_name = "Kavitha Google"
        
        res = self.app.post('/auth/google/demo', data={
            'email': test_email,
            'name': test_name,
            'picture': 'https://example.com/photo.jpg'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Kavitha Google", html)

        # Verify wallet balance
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (test_email,)).fetchone()
        conn.close()
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'customer')
        self.assertEqual(user['auth_provider'], 'google')
        self.assertEqual(user['wallet_balance'], 100.0)

    def test_04_google_login_matches_existing_user_by_email(self):
        """Verify that Google OAuth signs into an existing user if email matches."""
        self.app.get('/logout')
        res = self.app.post('/auth/google/demo', data={
            'email': 'vamsi@example.com',
            'name': 'Vamsi Vegi'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Welcome back", html)
        self.assertIn("Vamsi Vegi", html)

    def test_05_google_callback_rejects_invalid_csrf_state(self):
        """Verify /auth/google/callback rejects requests with missing or mismatched state."""
        self.app.get('/logout')
        res = self.app.get('/auth/google/callback?code=fake_code&state=invalid_csrf_token', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Invalid state parameter", html)

    def test_06_dashboard_shows_google_user_badge(self):
        """Verify navbar shows authenticated user profile when signed in via Google."""
        self.app.post('/auth/google/demo', data={
            'email': 'vamsi.google@gmail.com',
            'name': 'Vamsi Krishna'
        }, follow_redirects=True)
        dash_res = self.app.get('/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        html = dash_res.data.decode('utf-8')
        self.assertIn("Vamsi Krishna", html)
        self.assertIn("Log Out", html)

    def test_07_firebase_login_api_creates_new_customer(self):
        """Verify POST /api/auth/firebase-login provisions new user and credits 100 coins."""
        self.app.get('/logout')
        test_email = "firebase.fresh.buyer@gmail.com"
        test_name = "Ananya Firebase"
        
        res = self.app.post('/api/auth/firebase-login', json={
            'email': test_email,
            'displayName': test_name,
            'photoURL': 'https://example.com/avatar.jpg',
            'idToken': 'mock_firebase_id_token'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_new'])
        self.assertIn("PPM Organic Farms", data['message'])
        self.assertEqual(data['user']['email'], test_email)

        # Check DB
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (test_email,)).fetchone()
        conn.close()
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'customer')
        self.assertEqual(user['wallet_balance'], 100.0)

    def test_08_firebase_login_api_authenticates_existing_user(self):
        """Verify POST /api/auth/firebase-login logs in existing user seamlessly."""
        self.app.get('/logout')
        test_email = "firebase.fresh.buyer@gmail.com"
        
        res = self.app.post('/api/auth/firebase-login', json={
            'email': test_email,
            'displayName': "Ananya Updated",
            'photoURL': 'https://example.com/avatar.jpg'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertFalse(data['is_new'])
        self.assertIn("Welcome back", data['message'])

    def test_09_seo_endpoints_robots_and_sitemap(self):
        """Verify /robots.txt and /sitemap.xml endpoints return valid crawl directives."""
        # robots.txt
        res_robots = self.app.get('/robots.txt')
        self.assertEqual(res_robots.status_code, 200)
        self.assertEqual(res_robots.mimetype, 'text/plain')
        content_robots = res_robots.data.decode('utf-8')
        self.assertIn("User-agent: *", content_robots)
        self.assertIn("Allow: /shop", content_robots)
        self.assertIn("Sitemap: https://vamsi2005.pythonanywhere.com/sitemap.xml", content_robots)

        # sitemap.xml
        res_sitemap = self.app.get('/sitemap.xml')
        self.assertEqual(res_sitemap.status_code, 200)
        self.assertEqual(res_sitemap.mimetype, 'application/xml')
        content_sitemap = res_sitemap.data.decode('utf-8')
        self.assertIn("<urlset", content_sitemap)
        self.assertIn("https://vamsi2005.pythonanywhere.com/shop", content_sitemap)

    def test_10_product_search_api_phonetic_telugu(self):
        """Verify /api/products/search performs vernacular transliteration search."""
        # 'tamata' should match 'Tomato'
        res_tomato = self.app.get('/api/products/search?q=tamata')
        self.assertEqual(res_tomato.status_code, 200)
        data = res_tomato.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['count'], 0)
        matched_names = [p['name'].lower() for p in data['products']]
        self.assertTrue(any('tomato' in n for n in matched_names))

        # 'ullipaya' should match 'Onion'
        res_onion = self.app.get('/api/products/search?q=ullipaya')
        self.assertEqual(res_onion.status_code, 200)
        data_onion = res_onion.get_json()
        self.assertTrue(data_onion['success'])
        self.assertGreater(data_onion['count'], 0)
        matched_onion_names = [p['name'].lower() for p in data_onion['products']]
        self.assertTrue(any('onion' in n for n in matched_onion_names))

if __name__ == '__main__':
    unittest.main()

