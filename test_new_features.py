import unittest
from app import app
from database import init_db, get_db_connection

class TestProductionImprovements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Login as customer Vamsi Vegi (Phone 8888888888)
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

    def test_01_coupon_validation(self):
        """Verify coupon rules: minimum basket, flat vs percent discounts."""
        # 1. Invalid coupon
        res = self.app.post('/api/coupon/validate', json={'coupon_code': 'INVALID', 'subtotal': 300.0})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()['success'])

        # 2. Below minimum order
        res = self.app.post('/api/coupon/validate', json={'coupon_code': 'FARM50', 'subtotal': 100.0})
        self.assertEqual(res.status_code, 400)
        self.assertIn("minimum basket", res.get_json()['error'])

        # 3. Valid flat coupon (FARM50 on ₹250 subtotal -> ₹50 off)
        res = self.app.post('/api/coupon/validate', json={'coupon_code': 'FARM50', 'subtotal': 250.0})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['discount'], 50.0)
        self.assertEqual(data['new_total'], 200.0)

        # 4. Valid percentage coupon (VAMSI10 on ₹200 subtotal -> 10% = ₹20 off)
        res = self.app.post('/api/coupon/validate', json={'coupon_code': 'VAMSI10', 'subtotal': 200.0})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['discount'], 20.0)

    def test_02_checkout_with_coupon_and_invoice(self):
        """Verify checkout records discount and invoice reflects discount."""
        checkout_payload = {
            "items": [{"product_id": 1, "quantity": 6}], # 6 * 35 = ₹210
            "delivery_date": "2026-09-12",
            "delivery_slot": "Morning (8:00 AM - 11:00 AM)",
            "delivery_address": "Plot 99, Jubilee Hills, Hyderabad",
            "coupon_code": "FARM50",
            "discount_amount": 50.0
        }
        res = self.app.post('/api/checkout', json=checkout_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['grand_total'], 160.0) # 210 - 50 = 160
        order_id = data['order_id']

        # Check invoice
        inv_res = self.app.get(f'/api/order/invoice/{order_id}')
        self.assertEqual(inv_res.status_code, 200)
        inv = inv_res.get_json()['invoice']
        self.assertEqual(inv['coupon_code'], 'FARM50')
        self.assertEqual(inv['discount_amount'], 50.0)
        self.assertEqual(inv['grand_total'], 160.0)

    def test_03_order_cancellation_and_stock_restoration(self):
        """Verify customer can cancel a Placed order and stock is returned."""
        # 1. Check initial stock of product 2 (Nashik Red Onions)
        conn = get_db_connection()
        initial_stock = conn.execute("SELECT stock FROM products WHERE id = 2").fetchone()['stock']
        conn.close()

        # 2. Place order for 5 units
        order_res = self.app.post('/api/checkout', json={
            "items": [{"product_id": 2, "quantity": 5}],
            "delivery_date": "2026-09-12",
            "delivery_slot": "Evening (5:00 PM - 8:00 PM)",
            "delivery_address": "Villa 12, Gachibowli, Hyderabad"
        })
        order_id = order_res.get_json()['order_id']

        # Verify stock decreased by 5
        conn = get_db_connection()
        stock_after_order = conn.execute("SELECT stock FROM products WHERE id = 2").fetchone()['stock']
        self.assertEqual(stock_after_order, initial_stock - 5)
        conn.close()

        # 3. Cancel order
        cancel_res = self.app.post('/api/order/cancel', json={"order_id": order_id})
        self.assertEqual(cancel_res.status_code, 200)
        self.assertTrue(cancel_res.get_json()['success'])

        # 4. Verify stock restored back to initial
        conn = get_db_connection()
        stock_after_cancel = conn.execute("SELECT stock FROM products WHERE id = 2").fetchone()['stock']
        self.assertEqual(stock_after_cancel, initial_stock)
        
        # Verify status is Cancelled
        status = conn.execute("SELECT status FROM purchases WHERE order_id = ?", (order_id,)).fetchone()['status']
        self.assertEqual(status, 'Cancelled')
        conn.close()

    def test_04_admin_export_dispatch_csv(self):
        """Verify delivery dispatch CSV export endpoint."""
        # Non-admin is rejected
        res_guest = self.app.get('/api/admin/export-dispatch-csv')
        self.assertEqual(res_guest.status_code, 403)

        # Admin login
        self.app.post('/login', data={'login_type': 'admin', 'username': 'admin', 'password': 'admin123'})
        res_admin = self.app.get('/api/admin/export-dispatch-csv')
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn("text/csv", res_admin.content_type)
        self.assertIn(b"Order ID,Customer Name,Customer Phone", res_admin.data)

if __name__ == '__main__':
    unittest.main()
