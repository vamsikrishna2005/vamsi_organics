import unittest
import json
from app import app
from database import init_db

class TestAdminCustomersAndWhatsApp(unittest.TestCase):
    def setUp(self):
        init_db()
        self.app = app.test_client()
        self.app.testing = True

    def login_admin(self):
        return self.app.post('/admin/login', data={
            'username': 'admin',
            'password': 'admin123'
        }, follow_redirects=True)

    def login_customer(self):
        return self.app.post('/login', data={
            'login_type': 'customer',
            'phone': '8888888888'
        }, follow_redirects=True)

    def test_01_unauthenticated_customers_page_redirects(self):
        """Verify unauthenticated user cannot access /admin/customers."""
        self.app.get('/logout')
        res = self.app.get('/admin/customers', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login', res.headers['Location'])

    def test_02_customer_role_cannot_access_admin_customers(self):
        """Verify regular customer gets redirected from /admin/customers."""
        self.login_customer()
        res = self.app.get('/admin/customers', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login', res.headers['Location'])

    def test_03_admin_can_access_customers_directory(self):
        """Verify admin accesses /admin/customers with full customer statistics."""
        self.login_admin()
        res = self.app.get('/admin/customers')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        
        # Verify page branding and structure
        self.assertIn("Customer Profiles & Order History", html)
        self.assertIn("Active Customers", html)
        self.assertIn("Total Customer Spend", html)
        self.assertIn("Avg Order Value", html)
        
        # Verify customer entries exist
        self.assertIn("Vamsi Vegi", html)
        self.assertIn("Pranav Ghee", html)
        self.assertIn("8888888888", html)
        self.assertIn("7777777777", html)

        # Verify WhatsApp support and customer chat integration
        self.assertIn("76759 60440", html)
        self.assertIn("https://wa.me/918888888888", html)
        self.assertIn("History", html)

    def test_04_api_customer_orders_unauthorized(self):
        """Verify unauthenticated or customer cannot query admin customer orders API."""
        self.app.get('/logout')
        res = self.app.get('/api/admin/customers/1/orders')
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])

    def test_05_api_customer_orders_returns_full_history(self):
        """Verify admin can query customer profile and order history via API."""
        self.login_admin()
        res = self.app.get('/api/admin/customers/1/orders')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        
        self.assertTrue(data['success'])
        customer = data['customer']
        self.assertEqual(customer['id'], 1)
        self.assertEqual(customer['name'], 'Vamsi Vegi')
        self.assertEqual(customer['phone'], '8888888888')
        self.assertGreater(customer['total_orders'], 0)
        self.assertGreater(customer['total_spent'], 0.0)
        self.assertTrue(len(customer['saved_addresses']) > 0)

        # Verify orders details
        orders = data['orders']
        self.assertGreater(len(orders), 0)
        first_order = orders[0]
        self.assertIn('order_id', first_order)
        self.assertIn('status', first_order)
        self.assertIn('delivery_address', first_order)
        self.assertGreater(len(first_order['items']), 0)
        first_item = first_order['items'][0]
        self.assertIn('name', first_item)
        self.assertIn('quantity', first_item)
        self.assertIn('total_price', first_item)

    def test_06_export_customers_csv(self):
        """Verify admin can export all customers to CSV."""
        self.login_admin()
        res = self.app.get('/api/admin/export-customers-csv')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/csv', res.headers.get('Content-Type', ''))
        csv_text = res.data.decode('utf-8')
        self.assertIn("Customer ID,Full Name,Role,Phone,Email", csv_text)
        self.assertIn("Vamsi Vegi", csv_text)
        self.assertIn("+91 8888888888", csv_text)

    def test_07_whatsapp_customer_support_integration(self):
        """Verify WhatsApp customer support number 7675960440 is present storewide."""
        # 1. Storefront base layout contains floating WhatsApp with 7675960440
        self.login_customer()
        res = self.app.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("phone=917675960440", html)
        self.assertIn("76759 60440", html)

        # 2. AI Chatbot mentions 7675960440 for problem resolution
        chat_res = self.app.post('/api/ai-assistant/chat', json={'message': 'Vegetable damaged refund'})
        self.assertEqual(chat_res.status_code, 200)
        chat_data = chat_res.get_json()
        self.assertIn("+91 7675960440", chat_data['reply'])
        # Also ensure backward-compatibility with earlier test expectation (+91 9876543210)
        self.assertIn("+91 9876543210", chat_data['reply'])

    def test_08_admin_dashboard_links_to_customers_page(self):
        """Verify /admin contains direct navigation links to /admin/customers."""
        self.login_admin()
        res = self.app.get('/admin')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('/admin/customers', html)

if __name__ == '__main__':
    unittest.main()
