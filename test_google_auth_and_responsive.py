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

    def test_01_login_page_renders_google_auth_button(self):
        """Verify that the login page has removed Google Login and focuses on unique phone login."""
        res = self.app.get('/login')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertNotIn("Continue with Google", html)
        self.assertNotIn("google-btn", html)

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
        # vamsi@example.com is a pre-seeded user
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

if __name__ == '__main__':
    unittest.main()
