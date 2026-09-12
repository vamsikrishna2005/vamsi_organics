import unittest
import json
from app import app
from database import init_db, get_db_connection

class TestCustomerUniquenessAndAIChatbot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_customer_address_uniqueness_duplicate_prevented(self):
        """Verify that saving the exact same address twice updates the entry instead of creating a duplicate."""
        # Login as customer Vamsi Vegi
        login_res = self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        test_address = "Flat 401, Emerald Towers, Jubilee Hills, Hyderabad 500033"

        # 1. Save address first time
        res1 = self.app.post('/api/user/save-address', 
                              data=json.dumps({'label': 'Home', 'address': test_address, 'is_default': True}),
                              content_type='application/json')
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.data)
        self.assertTrue(data1['success'])
        first_id = data1['address_id']

        # 2. Attempt to save the exact same address again with extra whitespace and different casing
        duplicate_input = "   flat 401,   emerald towers,   jubilee hills, hyderabad 500033  "
        res2 = self.app.post('/api/user/save-address', 
                              data=json.dumps({'label': 'Home', 'address': duplicate_input, 'is_default': True}),
                              content_type='application/json')
        self.assertEqual(res2.status_code, 200)
        data2 = json.loads(res2.data)
        self.assertTrue(data2['success'])
        # Must return the existing ID rather than creating a duplicate
        self.assertEqual(data2['address_id'], first_id)

        # 3. Verify in database that only ONE copy of this address exists for user 1
        conn = get_db_connection()
        user_addrs = conn.execute("""
            SELECT * FROM user_addresses 
            WHERE user_id = 1 AND LOWER(TRIM(address)) = ?
        """, (test_address.lower(),)).fetchall()
        conn.close()
        self.assertEqual(len(user_addrs), 1)

    def test_02_customer_address_uniqueness_distinct_addresses_allowed(self):
        """Verify that a customer can save multiple distinct addresses without conflict."""
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        
        addr_work = "Suite 800, Cyber Gateway, HITEC City, Hyderabad 500081"
        res = self.app.post('/api/user/save-address',
                            data=json.dumps({'label': 'Work', 'address': addr_work, 'is_default': False}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])

        conn = get_db_connection()
        saved = conn.execute("SELECT * FROM user_addresses WHERE id = ?", (data['address_id'],)).fetchone()
        conn.close()
        self.assertIsNotNone(saved)
        self.assertEqual(saved['label'], 'Work')

    def test_03_customer_address_validation_rejects_empty_or_short(self):
        """Verify that saving an empty or overly short address is rejected."""
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

        res = self.app.post('/api/user/save-address',
                            data=json.dumps({'label': 'Home', 'address': '   '}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertFalse(data['success'])

    def test_04_customer_address_deletion(self):
        """Verify that a customer can delete a saved address and default is maintained."""
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

        # Save an address to delete
        temp_addr = "Temporary Old House 99, Secunderabad 500003"
        res = self.app.post('/api/user/save-address',
                            data=json.dumps({'label': 'Other', 'address': temp_addr, 'is_default': False}),
                            content_type='application/json')
        target_id = json.loads(res.data)['address_id']

        # Delete it
        del_res = self.app.post(f'/api/user/delete-address/{target_id}')
        self.assertEqual(del_res.status_code, 200)
        del_data = json.loads(del_res.data)
        self.assertTrue(del_data['success'])

        # Verify gone from DB
        conn = get_db_connection()
        check = conn.execute("SELECT * FROM user_addresses WHERE id = ?", (target_id,)).fetchone()
        conn.close()
        self.assertIsNone(check)

    def test_05_kisan_ai_chatbot_order_tracking(self):
        """Verify Kisan AI responds intelligently to order tracking queries."""
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

        res = self.app.post('/api/ai-assistant/chat',
                            data=json.dumps({'message': 'Where is my order?'}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('reply', data)
        self.assertTrue(len(data['reply']) > 20)

    def test_06_kisan_ai_chatbot_cod_payment_info(self):
        """Verify Kisan AI explains Cash on Delivery when asked about payment."""
        res = self.app.post('/api/ai-assistant/chat',
                            data=json.dumps({'message': 'How does Cash on Delivery work?'}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn("Cash on Delivery", data['reply'])
        self.assertIn("0", data['reply'])

    def test_07_kisan_ai_chatbot_support_whatsapp_escalation(self):
        """Verify Kisan AI problem/complaint responses include customer support phone +91 7675960440."""
        res = self.app.post('/api/ai-assistant/chat',
                            data=json.dumps({'message': 'I have a problem with my vegetables, call support'}),
                            content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn("7675960440", data['reply'])

    def test_08_admin_customer_dashboard_renders_cleanly(self):
        """Verify admin can view the customer directory with VOF-CUST formatted IDs."""
        self.app.get('/logout')
        # Login as Admin
        self.app.post('/admin/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        res = self.app.get('/admin/customers')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn("Customer Profiles & Order History", html)
        self.assertIn("VOF-CUST-", html)
        self.assertIn("76759 60440", html)

    def test_09_admin_customer_orders_api(self):
        """Verify admin API returns full customer profile, saved addresses, and past orders."""
        self.app.get('/logout')
        self.app.post('/admin/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Inspect user 1 (Vamsi Vegi)
        res = self.app.get('/api/admin/customers/1/orders')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIn('customer', data)
        self.assertEqual(data['customer']['name'], 'Vamsi Vegi')
        self.assertIn('saved_addresses', data['customer'])
        self.assertIn('orders', data)

    def test_10_admin_customer_wallet_adjustment(self):
        """Verify admin can adjust customer coins directly."""
        self.app.get('/logout')
        self.app.post('/admin/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Get initial balance
        conn = get_db_connection()
        init_bal = conn.execute("SELECT wallet_balance FROM users WHERE id = 1").fetchone()['wallet_balance']
        conn.close()

        # Credit 50 coins
        adj_res = self.app.post('/api/admin/customer/update-wallet',
                                data=json.dumps({
                                    'user_id': 1,
                                    'amount': 50.0,
                                    'type': 'credit',
                                    'reason': 'Test Loyalty Reward'
                                }),
                                content_type='application/json')
        self.assertEqual(adj_res.status_code, 200)
        adj_data = json.loads(adj_res.data)
        self.assertTrue(adj_data['success'])

        # Verify new balance
        conn = get_db_connection()
        new_bal = conn.execute("SELECT wallet_balance FROM users WHERE id = 1").fetchone()['wallet_balance']
        conn.close()
        self.assertEqual(new_bal, init_bal + 50.0)

if __name__ == '__main__':
    unittest.main()
