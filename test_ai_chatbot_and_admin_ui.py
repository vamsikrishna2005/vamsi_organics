import unittest
import json
from app import app
from database import init_db, get_db_connection

class TestAIChatbotAndAdminUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    # =========================================================
    # 1. AI ASSISTANT CHATBOT BACKEND TESTS
    # =========================================================

    def test_01_ai_chat_greeting_empty_and_hello(self):
        """Verify greeting response when empty or hello is sent."""
        res_empty = self.app.post('/api/ai-assistant/chat', json={'message': ''})
        self.assertEqual(res_empty.status_code, 200)
        data = res_empty.get_json()
        self.assertTrue(data['success'])
        self.assertIn("Kisan AI", data['reply'])
        self.assertGreaterEqual(len(data['suggestions']), 3)

        res_hi = self.app.post('/api/ai-assistant/chat', json={'message': 'Namaste, who are you?'})
        self.assertEqual(res_hi.status_code, 200)
        data_hi = res_hi.get_json()
        self.assertEqual(data_hi['intent'], 'greeting')
        self.assertIn("Kisan AI", data_hi['reply'])

    def test_02_ai_chat_track_specific_order_id(self):
        """Verify tracking a specific order ID returns timeline, status, and items."""
        res = self.app.post('/api/ai-assistant/chat', json={'message': 'Where is my order VOF-20260829-1003?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'track_order')
        self.assertIn("VOF-20260829-1003", data['reply'])
        self.assertIn("Out for Delivery", data['reply'])
        self.assertIn("Door No. 12-4, Gandhi Road, Puttur", data['reply'])

    def test_03_ai_chat_track_logged_in_user_orders(self):
        """Verify general order tracking retrieves the logged-in user's latest delivery."""
        # Login as customer Vamsi Vegi
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

        res = self.app.post('/api/ai-assistant/chat', json={'message': 'Can you track my order status?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'track_order')
        self.assertIn("VOF-", data['reply'])
        self.assertIn("Scheduled Delivery", data['reply'])

    def test_04_ai_chat_vegetable_inquiry_english(self):
        """Verify produce inquiry returns in-stock vegetables with pricing and Telugu names."""
        res = self.app.post('/api/ai-assistant/chat', json={'message': 'Do you have fresh tomatoes and palak in stock?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'product_inquiry')
        self.assertIn("Tomato", data['reply'])
        self.assertIn("In Stock", data['reply'])
        self.assertTrue(len(data.get('products', [])) >= 1)

    def test_05_ai_chat_vegetable_inquiry_telugu(self):
        """Verify Telugu vegetable name queries resolve accurately."""
        res = self.app.post('/api/ai-assistant/chat', json={'message': 'వంకాయ ఉందా?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'product_inquiry')
        self.assertTrue("Brinjal" in data['reply'] or "వంకాయ" in data['reply'])

    def test_06_ai_chat_recipes(self):
        """Verify recipe recommendations for home cooking."""
        res = self.app.post('/api/ai-assistant/chat', json={'message': 'Suggest a recipe for spinach and dal'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'recipe_ideas')
        self.assertIn("Palakura Pappu", data['reply'])
        self.assertIn("Tadka", data['reply'])

    def test_07_ai_chat_health_nutrition(self):
        """Verify health advice for diabetes and nutrition."""
        res = self.app.post('/api/ai-assistant/chat', json={'message': 'What vegetables are best for diabetes?'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'health_advice')
        self.assertIn("Bitter Gourd", data['reply'])
        self.assertIn("కాకరకాయ", data['reply'])

    def test_08_ai_chat_wallet_and_coupons(self):
        """Verify wallet and coupon explanations."""
        res_wallet = self.app.post('/api/ai-assistant/chat', json={'message': 'How do I redeem my wallet coins?'})
        self.assertEqual(res_wallet.status_code, 200)
        self.assertIn("Farm Wallet", res_wallet.get_json()['reply'])
        self.assertIn("5% Automatic Cashback", res_wallet.get_json()['reply'])

        res_coupon = self.app.post('/api/ai-assistant/chat', json={'message': 'Are there any promo coupons?'})
        self.assertEqual(res_coupon.status_code, 200)
        self.assertIn("FARM50", res_coupon.get_json()['reply'])

    def test_09_ai_chat_problem_and_complaint(self):
        """Verify customer issue diagnosis and support guarantee."""
        res = self.app.post('/api/ai-assistant/chat', json={'message': 'My vegetable arrived damaged, I want a refund or replacement'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['intent'], 'problem_support')
        self.assertIn("100% Farm Fresh Guarantee", data['reply'])
        self.assertIn("+91 9876543210", data['reply'])

    # =========================================================
    # 2. ADMIN PORTAL CLUMSINESS RESOLUTION & ISOLATION TESTS
    # =========================================================

    def test_10_admin_portal_has_no_customer_bottom_bar_or_whatsapp(self):
        """Verify admin portal does NOT render shopping bottom bar or WhatsApp button."""
        # Admin login
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        res = self.app.get('/admin')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # 1. No shopping cart badge in mobile bottom bar
        self.assertNotIn('id="mobile-cart-badge"', html)

        # 2. No floating WhatsApp support bubble
        self.assertNotIn('api.whatsapp.com/send', html)

        # 3. Has dedicated admin console header
        self.assertIn('Admin Console', html)
        self.assertIn('#orders-section', html)
        self.assertIn('#inventory-section', html)
        self.assertIn('#crm-section', html)
        self.assertIn('#coupons-section', html)

    def test_11_admin_order_drawer_hidden_by_default(self):
        """Verify slide-over drawer has hidden and style=display: none; by default."""
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        res = self.app.get('/admin')
        html = res.data.decode('utf-8')

        # Check drawer is hidden
        self.assertIn('id="admin-order-drawer"', html)
        self.assertIn('display: none;', html)
        self.assertIn('id="admin-order-drawer-backdrop"', html)

    def test_12_admin_inventory_table_displays_readable_names(self):
        """Verify vegetable names and Telugu titles are rendered as visible text, not just empty inputs."""
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        res = self.app.get('/admin')
        html = res.data.decode('utf-8')

        # Visible text checks
        self.assertIn('Hybrid Tomatoes', html)
        self.assertIn('టమోటా', html)
        self.assertIn('Desi Red Onions', html)
        self.assertIn('ఉల్లిపాయలు', html)

    # =========================================================
    # 3. CUSTOMER DASHBOARD KISAN AI WIDGET RENDERING
    # =========================================================

    def test_13_customer_dashboard_renders_kisan_ai_launcher(self):
        """Verify customer dashboard includes the Kisan AI floating launcher and chat window."""
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

        res = self.app.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        self.assertIn('id="farm-ai-chat-launcher"', html)
        self.assertIn('id="farm-ai-toggle-btn"', html)
        self.assertIn('id="farm-ai-chat-window"', html)
        self.assertIn('Kisan AI', html)

if __name__ == '__main__':
    unittest.main()
