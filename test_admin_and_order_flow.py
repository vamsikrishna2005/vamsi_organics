import unittest
import json
from app import app
from database import init_db, get_db_connection

class TestAdminAndOrderFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_01_checkout_saves_and_updates_default_address(self):
        """Verify checkout persists the delivery address as is_default = 1."""
        # Customer login
        login_res = self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        test_addr = 'Flat 502, Green Acres, Gachibowli, Hyderabad 500032'
        order_payload = {
            'items': [{'product_id': 1, 'quantity': 1}],
            'delivery_date': '2026-09-12',
            'delivery_slot': 'Morning (8:00 AM - 11:00 AM)',
            'delivery_address': test_addr
        }
        res = self.app.post('/api/checkout', json=order_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        order_id = data['order_id']

        # Verify database address persistence and default flag
        conn = get_db_connection()
        user = conn.execute('SELECT id FROM users WHERE phone = ?', ('8888888888',)).fetchone()
        user_id = user['id']
        addr_row = conn.execute('SELECT * FROM user_addresses WHERE user_id = ? AND address = ?', (user_id, test_addr)).fetchone()
        self.assertIsNotNone(addr_row)
        self.assertEqual(addr_row['is_default'], 1)

        # Check other addresses for this user have is_default = 0
        other_addrs = conn.execute('SELECT * FROM user_addresses WHERE user_id = ? AND id != ?', (user_id, addr_row['id'])).fetchall()
        for oa in other_addrs:
            self.assertEqual(oa['is_default'], 0)
        conn.close()

    def test_02_save_address_api_sets_default(self):
        """Verify /api/user/save-address sets is_default = 1 when requested."""
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        new_addr = 'Villa 12, Palm Meadows, Jubilee Hills, Hyderabad 500033'
        res = self.app.post('/api/user/save-address', json={
            'address': new_addr,
            'label': 'Office',
            'is_default': True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])

        conn = get_db_connection()
        user = conn.execute('SELECT id FROM users WHERE phone = ?', ('8888888888',)).fetchone()
        user_id = user['id']
        saved = conn.execute('SELECT * FROM user_addresses WHERE user_id = ? AND address = ?', (user_id, new_addr)).fetchone()
        conn.close()
        self.assertIsNotNone(saved)
        self.assertEqual(saved['is_default'], 1)

    def test_03_admin_get_order_details(self):
        """Verify admin can retrieve comprehensive order details for slide-over drawer."""
        # Place order first
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        order_payload = {
            'items': [{'product_id': 1, 'quantity': 2}, {'product_id': 2, 'quantity': 1}],
            'delivery_date': '2026-09-15',
            'delivery_slot': 'Evening (4:00 PM - 7:00 PM)',
            'delivery_address': 'Flat 101, Test Tower, Hyderabad'
        }
        res = self.app.post('/api/checkout', json=order_payload)
        order_id = res.get_json()['order_id']

        # Admin login
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        detail_res = self.app.get(f'/api/admin/order-details/{order_id}')
        self.assertEqual(detail_res.status_code, 200)
        data = detail_res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['order']['order_id'], order_id)
        self.assertIn('customer', data)
        self.assertEqual(data['customer']['phone'], '8888888888')
        self.assertIn('items', data)
        self.assertGreaterEqual(len(data['items']), 2)
        # item['name'] contains vegetable name
        self.assertTrue(any('Tomato' in item['name'] for item in data['items']))

    def test_04_admin_order_actions_lifecycle(self):
        """Verify admin order actions accept, dispatch, deliver."""
        # Place an order
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        res = self.app.post('/api/checkout', json={
            'items': [{'product_id': 1, 'quantity': 1}],
            'delivery_date': '2026-09-16',
            'delivery_slot': 'Morning (8:00 AM - 11:00 AM)',
            'delivery_address': 'Plot 44, HiTech City, Hyderabad'
        })
        order_id = res.get_json()['order_id']

        # Admin login
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # 1. Accept Order
        res_accept = self.app.post('/api/admin/order-action', json={'order_id': order_id, 'action': 'accept'})
        self.assertEqual(res_accept.status_code, 200)
        self.assertTrue(res_accept.get_json()['success'])
        self.assertEqual(res_accept.get_json()['status'], 'Packed at Farm')

        # 2. Dispatch Order
        res_dispatch = self.app.post('/api/admin/order-action', json={'order_id': order_id, 'action': 'dispatch'})
        self.assertEqual(res_dispatch.status_code, 200)
        self.assertTrue(res_dispatch.get_json()['success'])
        self.assertEqual(res_dispatch.get_json()['status'], 'Out for Delivery')

        # 3. Deliver Order
        res_deliver = self.app.post('/api/admin/order-action', json={'order_id': order_id, 'action': 'deliver'})
        self.assertEqual(res_deliver.status_code, 200)
        self.assertTrue(res_deliver.get_json()['success'])
        self.assertEqual(res_deliver.get_json()['status'], 'Delivered')

        # 4. Verify in DB purchases table
        conn = get_db_connection()
        order_row = conn.execute('SELECT status FROM purchases WHERE order_id = ?', (order_id,)).fetchone()
        conn.close()
        self.assertEqual(order_row['status'], 'Delivered')

    def test_05_admin_order_action_update_address(self):
        """Verify admin can modify the delivery address directly."""
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        res = self.app.post('/api/checkout', json={
            'items': [{'product_id': 1, 'quantity': 1}],
            'delivery_date': '2026-09-17',
            'delivery_slot': 'Morning (8:00 AM - 11:00 AM)',
            'delivery_address': 'Original Address'
        })
        order_id = res.get_json()['order_id']

        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        updated_addr = 'Corrected Farm Delivery Bay 9, Kondapur, Hyderabad'
        res_up = self.app.post('/api/admin/order-action', json={
            'order_id': order_id,
            'action': 'update_address',
            'delivery_address': updated_addr
        })
        self.assertEqual(res_up.status_code, 200)

        conn = get_db_connection()
        row = conn.execute('SELECT delivery_address FROM purchases WHERE order_id = ?', (order_id,)).fetchone()
        conn.close()
        self.assertEqual(row['delivery_address'], updated_addr)

    def test_06_admin_customer_wallet_adjustment(self):
        """Verify admin can adjust buyer wallet balance."""
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        conn = get_db_connection()
        user = conn.execute('SELECT id, wallet_balance FROM users WHERE phone = ?', ('8888888888',)).fetchone()
        conn.close()
        initial_bal = user['wallet_balance']

        res = self.app.post('/api/admin/customer/update-wallet', json={
            'user_id': user['id'],
            'amount': 75.50,
            'note': 'Loyalty harvest bonus'
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        conn = get_db_connection()
        user_after = conn.execute('SELECT wallet_balance FROM users WHERE id = ?', (user['id'],)).fetchone()
        conn.close()
        self.assertAlmostEqual(user_after['wallet_balance'], initial_bal + 75.50, places=2)

    def test_07_admin_customer_role_toggle(self):
        """Verify admin can change customer role."""
        # Register a temporary test customer
        self.app.get('/logout')
        self.app.post('/register', data={
            'name': 'Role Switch User',
            'email': 'roleuser@example.com',
            'phone': '9876500011'
        }, follow_redirects=True)

        conn = get_db_connection()
        user = conn.execute('SELECT id, role FROM users WHERE phone = ?', ('9876500011',)).fetchone()
        conn.close()
        self.assertEqual(user['role'], 'customer')

        # Admin login & toggle role
        self.app.get('/logout')
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        res = self.app.post('/api/admin/customer/update-role', json={
            'user_id': user['id'],
            'role': 'admin'
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        conn = get_db_connection()
        user_after = conn.execute('SELECT role FROM users WHERE id = ?', (user['id'],)).fetchone()
        conn.close()
        self.assertEqual(user_after['role'], 'admin')

    def test_08_admin_coupon_crud(self):
        """Verify admin can create, list, and delete discount coupons."""
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Create coupon
        coupon_code = 'HARVEST80'
        res_create = self.app.post('/api/admin/coupon/create', json={
            'code': coupon_code,
            'min_order': 399.0,
            'type': 'percent',
            'value': 30.0,
            'max_discount': 150.0,
            'description': '30% off test coupon'
        })
        self.assertEqual(res_create.status_code, 200)
        self.assertTrue(res_create.get_json()['success'])

        # List coupons
        res_list = self.app.get('/api/admin/coupons')
        self.assertEqual(res_list.status_code, 200)
        coupons = res_list.get_json()['coupons']
        found = [c for c in coupons if c['code'] == coupon_code]
        self.assertEqual(len(found), 1)
        coupon_id = found[0]['id']

        # Delete coupon
        res_del = self.app.post(f'/api/admin/coupon/delete/{coupon_id}')
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()['success'])

        # Verify deletion
        res_list2 = self.app.get('/api/admin/coupons')
        codes2 = [c['code'] for c in res_list2.get_json()['coupons']]
        self.assertNotIn(coupon_code, codes2)

    def test_09_admin_product_create_and_delete(self):
        """Verify admin can add new vegetable and remove produce from catalog."""
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)

        # Add vegetable
        res_add = self.app.post('/api/admin/create-product', json={
            'name': 'Organic Yellow Capsicum',
            'category': 'Gourds & Roots',
            'price': 65.0,
            'unit': '500g',
            'stock': 40,
            'image_url': 'https://images.unsplash.com/photo-1563565375-f3fdfdbefa83?w=500&q=80',
            'tags': 'capsicum, yellow, sweet, organic',
            'description': 'Crisp farm-fresh organic yellow capsicum.'
        })
        self.assertEqual(res_add.status_code, 200)
        self.assertTrue(res_add.get_json()['success'])

        # Verify in DB
        conn = get_db_connection()
        prod = conn.execute('SELECT * FROM products WHERE name = ?', ('Organic Yellow Capsicum',)).fetchone()
        self.assertIsNotNone(prod)
        pid = prod['id']
        conn.close()

        # Delete vegetable
        res_del = self.app.post(f'/api/admin/delete-product/{pid}')
        self.assertEqual(res_del.status_code, 200)
        self.assertTrue(res_del.get_json()['success'])

        # Verify deletion
        conn = get_db_connection()
        prod_after = conn.execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()
        conn.close()
        self.assertIsNone(prod_after)

    def test_10_celebratory_popup_modal_present_in_dashboard(self):
        """Verify celebratory popup modal and message are rendered in dashboard HTML."""
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)
        res = self.app.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('order-success-modal', html)
        self.assertIn('Thank you for ordering with', html)
        self.assertTrue('PPM Organic Farms' in html or 'Vamsi Organic Farms' in html)
        self.assertIn('will deliver soon', html)

if __name__ == '__main__':
    unittest.main()
