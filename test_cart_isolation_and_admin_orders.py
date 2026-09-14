import unittest
import json
from app import app
from database import init_db, get_db_connection

class TestCartIsolationAndAdminOrders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    # =========================================================
    # 1. USER CART ISOLATION TESTS
    # =========================================================

    def test_01_user_cart_api_isolation_between_customers(self):
        """Verify User 1 and User 2 have strictly isolated, private shopping carts."""
        # 1. Login as User 1 (Vamsi Vegi, 8888888888)
        self.app.get('/logout')
        res_login1 = self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        self.assertEqual(res_login1.status_code, 200)

        # Clear cart first
        self.app.post('/api/cart/clear')

        # Sync items for User 1: 2 Tomatoes (id: 1) and 3 Onions (id: 2)
        res_sync1 = self.app.post('/api/cart/sync', json={
            'items': [
                {'id': 1, 'quantity': 2},
                {'id': 2, 'quantity': 3}
            ]
        })
        self.assertEqual(res_sync1.status_code, 200)

        # Fetch cart for User 1
        res_cart1 = self.app.get('/api/cart')
        self.assertEqual(res_cart1.status_code, 200)
        cdata1 = res_cart1.get_json()
        self.assertTrue(cdata1['success'])
        self.assertEqual(cdata1['total_count'], 5)
        self.assertEqual(len(cdata1['items']), 2)

        # 2. Create User 2 (Buyer Two, 9876543211) and test cart isolation
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO users (name, email, phone, role) VALUES ('Buyer Two', 'buyer2@example.com', '9876543211', 'customer')")
        conn.commit()
        conn.close()

        self.app.get('/logout')
        res_login2 = self.app.post('/login', data={'login_type': 'customer', 'phone': '9876543211'}, follow_redirects=True)
        self.assertEqual(res_login2.status_code, 200)

        # Clear cart first for User 2
        self.app.post('/api/cart/clear')

        # Verify User 2 does NOT see User 1's items
        res_cart2 = self.app.get('/api/cart')
        cdata2 = res_cart2.get_json()
        self.assertEqual(cdata2['total_count'], 0)
        self.assertEqual(len(cdata2['items']), 0)

        # Sync different item for User 2: 1 Spinach (id: 9)
        self.app.post('/api/cart/sync', json={
            'items': [{'id': 9, 'quantity': 1}]
        })
        res_cart2_after = self.app.get('/api/cart')
        cdata2_after = res_cart2_after.get_json()
        self.assertEqual(cdata2_after['total_count'], 1)
        self.assertEqual(cdata2_after['items'][0]['name'], "Fresh Spinach (Palak) [పాలకూర]")

        # 3. Logout User 2 and Login back as User 1
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

        # Verify User 1's cart remains intact and untouched by User 2
        res_cart1_recheck = self.app.get('/api/cart')
        cdata1_recheck = res_cart1_recheck.get_json()
        self.assertEqual(cdata1_recheck['total_count'], 5)
        self.assertEqual(len(cdata1_recheck['items']), 2)
        pids = [item['id'] for item in cdata1_recheck['items']]
        self.assertIn(1, pids)
        self.assertIn(2, pids)
        self.assertNotIn(9, pids)

    def test_02_guest_cart_returns_empty_and_guest_flag(self):
        """Verify unauthenticated user receives is_guest: True and empty items list from /api/cart."""
        self.app.get('/logout')
        res = self.app.get('/api/cart')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_guest'])
        self.assertEqual(data['items'], [])

    def test_03_cart_wiped_from_db_on_successful_checkout(self):
        """Verify that completing an order clears the customer's server cart."""
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

        # Put 1 item in cart
        self.app.post('/api/cart/sync', json={'items': [{'id': 1, 'quantity': 1}]})
        pre_check = self.app.get('/api/cart').get_json()
        self.assertEqual(pre_check['total_count'], 1)

        # Execute checkout
        res_order = self.app.post('/api/checkout', json={
            'items': [{'product_id': 1, 'quantity': 1}],
            'delivery_address': 'Flat 101, Test Residency, Madhapur, Hyderabad',
            'delivery_date': '2026-09-15',
            'delivery_slot': 'Morning (8:00 AM - 11:00 AM)'
        })
        self.assertEqual(res_order.status_code, 200)
        odata = res_order.get_json()
        self.assertTrue(odata['success'])

        # Verify cart in DB is now empty
        post_check = self.app.get('/api/cart').get_json()
        self.assertEqual(post_check['total_count'], 0)
        self.assertEqual(len(post_check['items']), 0)

    # =========================================================
    # 2. GUARANTEED ADMIN ORDER VISIBILITY TESTS
    # =========================================================

    def test_04_admin_orders_api_unauthorized_for_customers(self):
        """Verify customers cannot access the admin orders endpoint."""
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

        res = self.app.get('/api/admin/orders')
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])

    def test_05_admin_orders_api_returns_complete_order_list(self):
        """Verify store administrator receives all customer orders via /api/admin/orders."""
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        res = self.app.get('/api/admin/orders')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['total_count'], 1)
        self.assertEqual(len(data['orders']), data['total_count'])

        # Check fields in orders
        first_order = data['orders'][0]
        self.assertIn('order_id', first_order)
        self.assertIn('customer_name', first_order)
        self.assertIn('customer_phone', first_order)
        self.assertIn('delivery_address', first_order)
        self.assertIn('items_summary', first_order)
        self.assertIn('order_total', first_order)
        self.assertIn('status', first_order)
        self.assertIn('purchase_date', first_order)

    def test_06_admin_orders_api_status_filtering_and_search(self):
        """Verify filtering by status and searching by query parameter works accurately."""
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Test Placed status filter
        res_placed = self.app.get('/api/admin/orders?status=Placed')
        self.assertEqual(res_placed.status_code, 200)
        data_placed = res_placed.get_json()
        for o in data_placed['orders']:
            self.assertEqual(o['status'], 'Placed')

        # Test Delivered status filter
        res_del = self.app.get('/api/admin/orders?status=Delivered')
        self.assertEqual(res_del.status_code, 200)
        data_del = res_del.get_json()
        for o in data_del['orders']:
            self.assertEqual(o['status'], 'Delivered')

        # Test Search filter for 'VOF-'
        res_search = self.app.get('/api/admin/orders?search=VOF-')
        self.assertEqual(res_search.status_code, 200)
        data_search = res_search.get_json()
        self.assertGreaterEqual(data_search['total_count'], 1)

    def test_07_new_customer_registration_and_immediate_admin_order_visibility(self):
        """Verify that when a brand new customer registers and places an order, the admin sees it immediately at top."""
        self.app.get('/logout')
        new_phone = "9777123456"
        new_email = "newfarmcustomer@test.com"

        # Register new customer
        self.app.post('/register', data={
            'name': 'Kavitha Farm Buyer',
            'email': new_email,
            'phone': new_phone
        }, follow_redirects=True)

        # Login as this new customer
        self.app.post('/login', data={'login_type': 'customer', 'phone': new_phone}, follow_redirects=True)

        # Place an order
        res_order = self.app.post('/api/checkout', json={
            'items': [
                {'product_id': 1, 'quantity': 3}, # 3 Tomatoes
                {'product_id': 2, 'quantity': 2}  # 2 Onions
            ],
            'delivery_address': 'Plot 42, Jubilee Hills, Hyderabad',
            'delivery_date': '2026-09-16',
            'delivery_slot': 'Morning (8:00 AM - 11:00 AM)'
        })
        self.assertEqual(res_order.status_code, 200)
        new_order_id = res_order.get_json()['order_id']

        # Now login as admin
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # 1. Verify /api/admin/orders returns this new order at the very top (first item)
        res_admin_api = self.app.get('/api/admin/orders')
        self.assertEqual(res_admin_api.status_code, 200)
        api_orders = res_admin_api.get_json()['orders']
        self.assertEqual(api_orders[0]['order_id'], new_order_id)
        self.assertEqual(api_orders[0]['customer_name'], 'Kavitha Farm Buyer')
        self.assertEqual(api_orders[0]['customer_phone'], new_phone)
        self.assertIn('Plot 42, Jubilee Hills', api_orders[0]['delivery_address'])

        # 2. Verify /admin HTML page renders the order
        res_admin_html = self.app.get('/admin')
        self.assertEqual(res_admin_html.status_code, 200)
        html = res_admin_html.data.decode('utf-8')
        self.assertIn(new_order_id, html)
        self.assertIn('Kavitha Farm Buyer', html)
        self.assertIn(new_phone, html)

if __name__ == '__main__':
    unittest.main()
