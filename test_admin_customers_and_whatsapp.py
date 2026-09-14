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
        
        # Verify real customer entries exist
        self.assertIn("Vamsi Vegi", html)
        self.assertIn("8888888888", html)

        # Verify mock/demo customers are strictly removed
        self.assertNotIn("Pranav Ghee", html)
        self.assertNotIn("7777777777", html)
        self.assertNotIn("Sita Sweet", html)
        self.assertNotIn("6666666666", html)
        self.assertNotIn("General Shopper", html)
        self.assertNotIn("5555555555", html)

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

    def test_09_customer_history_visible_after_proceeding_with_order(self):
        """Verify customer and admin can immediately see customer order history after proceeding with order."""
        self.app.get('/logout')
        phone = "9123456780"
        name = "Radha Farm Buyer"
        email = "radha@farmtest.com"

        # 1. Register customer
        res_reg = self.app.post('/register', data={
            'name': name,
            'email': email,
            'phone': phone
        }, follow_redirects=True)
        self.assertEqual(res_reg.status_code, 200)

        # Log in as the newly registered customer
        res_login = self.app.post('/login', data={'login_type': 'customer', 'phone': phone}, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)

        # 2. Proceed with order (Checkout)
        res_order = self.app.post('/api/checkout', json={
            'items': [
                {'product_id': 1, 'quantity': 2}, # 2 Tomatoes
                {'product_id': 9, 'quantity': 1}  # 1 Spinach
            ],
            'delivery_address': 'Flat 402, Lotus Greens, Gachibowli, Hyderabad - 500032',
            'delivery_date': '2026-09-17',
            'delivery_slot': 'Morning (8:00 AM - 11:00 AM)'
        })
        self.assertEqual(res_order.status_code, 200)
        order_data = res_order.get_json()
        self.assertTrue(order_data['success'])
        order_id = order_data['order_id']

        # 3. Customer immediately sees order in customer order history on /dashboard?tab=orders
        res_dashboard = self.app.get('/dashboard?tab=orders')
        self.assertEqual(res_dashboard.status_code, 200)
        dash_html = res_dashboard.data.decode('utf-8')
        self.assertIn(order_id, dash_html)
        self.assertIn('Lotus Greens, Gachibowli', dash_html)

        # 4. Admin logs in and checks /admin/customers
        self.app.get('/logout')
        self.login_admin()

        res_admin_cust = self.app.get('/admin/customers')
        self.assertEqual(res_admin_cust.status_code, 200)
        admin_cust_html = res_admin_cust.data.decode('utf-8')
        self.assertIn(name, admin_cust_html)
        self.assertIn(phone, admin_cust_html)
        self.assertIn('Lotus Greens, Gachibowli', admin_cust_html)

        # Verify demo customers are NOT present
        self.assertNotIn('General Shopper', admin_cust_html)
        self.assertNotIn('Pranav Ghee', admin_cust_html)
        self.assertNotIn('Sita Sweet', admin_cust_html)

        # 5. Query customer orders API for Radha
        from database import get_db_connection
        conn = get_db_connection()
        user_row = conn.execute("SELECT id FROM users WHERE phone = ?", (phone,)).fetchone()
        conn.close()
        self.assertIsNotNone(user_row)
        radha_id = user_row['id']

        res_api = self.app.get(f'/api/admin/customers/{radha_id}/orders')
        self.assertEqual(res_api.status_code, 200)
        api_data = res_api.get_json()
        self.assertTrue(api_data['success'])
        self.assertEqual(api_data['customer']['name'], name)
        self.assertEqual(api_data['customer']['phone'], phone)
        self.assertEqual(api_data['customer']['total_orders'], 1)
        self.assertEqual(len(api_data['orders']), 1)
        self.assertEqual(api_data['orders'][0]['order_id'], order_id)
        self.assertIn('Lotus Greens, Gachibowli', api_data['orders'][0]['delivery_address'])
        self.assertEqual(len(api_data['orders'][0]['items']), 2)

if __name__ == '__main__':
    unittest.main()
